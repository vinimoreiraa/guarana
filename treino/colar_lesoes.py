"""Cola lesoes REAIS em olhos normais REAIS. Para cada foto-fonte com sinal, o segmentador (saida/fenda_v1.onnx) da a fenda e a iris;
a lesao e isolada por regra de cor dentro da esclera (hemorragia: vermelho saturado; pterigio: tecido rosado encostado no limbo;
lesao pigmentada: mancha escura); icterícia e conjuntivite nao usam mascara: transferem cor da esclera. A lesao e transportada
para o olho-alvo alinhando pelas iris (escala e translacao), com borda suavizada e ajuste da cor media da esclera.
Uso: .venv/bin/python treino/colar_lesoes.py --fontes dados/externos/labels_mendeley_conj.csv ... --alvos dados/externos/labels_zenodo_normais.csv --n 400 --out dados/crops/colagem
Saida: imagens + dados/labels_colagem.csv (source=colagem, domain=phone_closeup). NUNCA usar como teste.
"""
import argparse, csv, json, math, random, hashlib
from pathlib import Path
import numpy as np, pandas as pd, onnxruntime as ort
from PIL import Image, ImageOps, ImageFilter
BASE = Path(__file__).resolve().parents[1]; DATA = BASE / "dados"; OUT_DEF = DATA / "crops/colagem"
LABELS = ["hiperemia","ictericia","pterigio","pinguecula","catarata_leucocoria","hemorragia_subconjuntival","lesao_pigmentada","opacidade_corneana","tumor_superficie_ocular","ceratite","cisto_conjuntival","lente_intraocular","conjuntivite","uveite","alteracao_palpebral"]
card = json.load(open(BASE / "saida/fenda_card.json")); S = card["input"]["size"]; MEAN, STD = np.array(card["input"]["mean"], np.float32), np.array(card["input"]["std"], np.float32)
sess = ort.InferenceSession(str(BASE / "saida/fenda_v1.onnx"), providers=["CPUExecutionProvider"])
def segmenta(im):
    """retorna (fenda bool, iris bool) na resolucao da imagem, e circulo da iris (cx, cy, r)"""
    w, h = im.size; x = ((np.asarray(im.resize((S, S), Image.BILINEAR), np.float32) / 255 - MEAN) / STD).transpose(2, 0, 1)[None]
    lg = sess.run(None, {"image": x})[0][0]; pr = 1 / (1 + np.exp(-lg))
    fen = np.asarray(Image.fromarray((pr[0] * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)) > 128
    iri = np.asarray(Image.fromarray((pr[1] * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)) > 128
    if iri.sum() < 50: return None
    ys, xs = np.nonzero(iri); cx, cy = xs.mean(), ys.mean(); r = max((xs.max() - xs.min()) / 2, math.sqrt(iri.sum() / math.pi))
    return fen, iri, (cx, cy, r)
def hsv(a):
    from PIL import Image as _I
    return np.asarray(_I.fromarray(a).convert("HSV")).astype(np.float32)
def mascara_lesao(a, fen, iri, circ, sinal):
    """mascara bool da lesao dentro da esclera (fenda - iris dilatada)"""
    esc = fen & ~dilata(iri, 3); H = hsv(a); h, s, v = H[..., 0] / 255 * 360, H[..., 1] / 255, H[..., 2] / 255
    if sinal == "hemorragia_subconjuntival": m = esc & (s > 0.45) & ((h < 20) | (h > 335)) & (v > 0.25)
    elif sinal in ("pterigio", "pinguecula"):
        # setor geometrico: o pterigio vive sempre entre o limbo e o canto (quase sempre nasal). Levamos o setor da fenda do lado
        # em que ha mais tecido rosado/amarelado, do limbo (0,8 r) ate o canto (3,5 r), com angulo de +-40 graus do eixo horizontal.
        cx, cy, r = circ; yy, xx = np.mgrid[:a.shape[0], :a.shape[1]]; d = np.hypot(xx - cx, yy - cy); ang = np.abs(np.degrees(np.arctan2(yy - cy, np.abs(xx - cx))))
        rosado = fen & (s > 0.15) & (v > 0.3) & (((h < 40) | (h > 330)) if sinal == "pterigio" else ((h > 25) & (h < 75)))
        lado = 1 if rosado[:, int(cx):].sum() >= rosado[:, :int(cx)].sum() else -1
        setor = fen & (d > 0.8 * r) & (d < 3.5 * r) & (ang < 40) & (((xx - cx) * lado) > 0)
        m = setor | (iri & (d > 0.7 * r) & (ang < 30) & (((xx - cx) * lado) > 0) & rosado)   # inclui a parte da asa que ja invadiu a cornea
        return m if m.sum() > 0.02 * max(fen.sum(), 1) else None
    elif sinal == "lesao_pigmentada": m = esc & (v < 0.45) & (s > 0.15)
    else: return None
    m = abre(m, 2); m = maior_componente(m)
    return m if m.sum() > 0.01 * max(esc.sum(), 1) else None
def dilata(m, k):
    im = Image.fromarray(m.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(2 * k + 1)); return np.asarray(im) > 128
def abre(m, k):
    im = Image.fromarray(m.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(2 * k + 1)).filter(ImageFilter.MaxFilter(2 * k + 1)); return np.asarray(im) > 128
def maior_componente(m):
    from collections import deque
    h, w = m.shape; lab = np.zeros((h, w), np.int32); best = None; cur = 0
    for y0 in range(0, h, 1):
        for x0 in range(0, w, 1):
            if m[y0, x0] and lab[y0, x0] == 0:
                cur += 1; q = deque([(y0, x0)]); lab[y0, x0] = cur; n = 0
                while q:
                    y, x = q.popleft(); n += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        yy, xx = y + dy, x + dx
                        if 0 <= yy < h and 0 <= xx < w and m[yy, xx] and lab[yy, xx] == 0: lab[yy, xx] = cur; q.append((yy, xx))
                if best is None or n > best[1]: best = (cur, n)
    return lab == best[0] if best else m
def cor_media(a, m): return a[m].reshape(-1, 3).mean(0) if m.sum() else np.array([200, 200, 200], np.float32)
def cola(src, m_src, circ_src, dst, fen_dst, iri_dst, circ_dst, rng, lado_troca=False, permite_iris=False):
    """transporta a regiao m_src de src para dst alinhando iris; devolve (imagem colada, mascara colada)"""
    sx, sy, sr = circ_src; dx, dy, dr = circ_dst; esc = dr / sr
    if lado_troca: src = np.ascontiguousarray(src[:, ::-1]); m_src = np.ascontiguousarray(m_src[:, ::-1]); sx = src.shape[1] - 1 - sx
    A = np.zeros_like(dst); M = np.zeros(dst.shape[:2], bool)
    ys, xs = np.nonzero(m_src)
    if len(ys) == 0: return None
    # amostragem inversa: para cada pixel destino dentro da caixa da lesao transformada
    bx0, bx1 = int(dx + (xs.min() - sx) * esc) - 2, int(dx + (xs.max() - sx) * esc) + 3; by0, by1 = int(dy + (ys.min() - sy) * esc) - 2, int(dy + (ys.max() - sy) * esc) + 3
    bx0, by0 = max(bx0, 0), max(by0, 0); bx1, by1 = min(bx1, dst.shape[1]), min(by1, dst.shape[0])
    if bx1 <= bx0 or by1 <= by0: return None
    yy, xx = np.mgrid[by0:by1, bx0:bx1]; sxx = np.clip(((xx - dx) / esc + sx).round().astype(int), 0, src.shape[1] - 1); syy = np.clip(((yy - dy) / esc + sy).round().astype(int), 0, src.shape[0] - 1)
    Mm = m_src[syy, sxx] & fen_dst[by0:by1, bx0:bx1]
    if not permite_iris: Mm &= ~dilata(iri_dst, 2)[by0:by1, bx0:bx1]
    if Mm.sum() < 30: return None
    # ajuste de cor: esclera fonte -> esclera destino (media multiplicativa), lesao mantem a diferenca relativa
    esc_src = cor_media(src, dilata(m_src, 12) & ~m_src); esc_dst = cor_media(dst, fen_dst & ~dilata(iri_dst, 3)); ganho = np.clip(esc_dst / np.maximum(esc_src, 1), 0.6, 1.6)
    patch = np.clip(src[syy, sxx].astype(np.float32) * ganho, 0, 255)
    alpha = np.asarray(Image.fromarray(Mm.astype(np.uint8) * 255).filter(ImageFilter.GaussianBlur(float(max(1.5, dr * 0.04)))), np.float32) / 255 * Mm.max()
    alpha = np.where(Mm, np.maximum(alpha, 0.85), alpha)[..., None]
    out = dst.astype(np.float32).copy(); out[by0:by1, bx0:bx1] = out[by0:by1, bx0:bx1] * (1 - alpha) + patch * alpha
    M[by0:by1, bx0:bx1] = Mm; return np.clip(out, 0, 255).astype(np.uint8), M
def tinge_esclera(dst, fen, iri, sinal, rng):
    """icterícia: esclera para amarelo; conjuntivite/hiperemia: rosa + vasos reforcados (sem mascara de lesao)"""
    esc = fen & ~dilata(iri, 3); out = dst.astype(np.float32).copy(); a = np.asarray(Image.fromarray(esc.astype(np.uint8) * 255).filter(ImageFilter.GaussianBlur(3)), np.float32)[..., None] / 255
    if sinal == "ictericia": alvo = np.array([rng.uniform(0.95, 1.0), rng.uniform(0.82, 0.92), rng.uniform(0.35, 0.6)]); k = rng.uniform(0.5, 0.9)
    else: alvo = np.array([1.0, rng.uniform(0.55, 0.8), rng.uniform(0.55, 0.8)]); k = rng.uniform(0.35, 0.7)
    tint = out * alvo; out = out * (1 - a * k) + tint * a * k
    return np.clip(out, 0, 255).astype(np.uint8)
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--fontes", nargs="+", required=True); ap.add_argument("--alvos", required=True); ap.add_argument("--n", type=int, default=300); ap.add_argument("--out", default=str(OUT_DEF)); ap.add_argument("--seed", type=int, default=0); a = ap.parse_args()
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True); rng = random.Random(a.seed)
    src = pd.concat([pd.read_csv(f) for f in a.fontes], ignore_index=True); alvos = pd.read_csv(a.alvos)
    if "metade" in src.columns: src = src[src["metade"] == "A"]   # metade B fica como teste
    src = src[src[LABELS].sum(axis=1) > 0]; sinais_ok = ["hemorragia_subconjuntival", "pterigio", "lesao_pigmentada", "pinguecula", "ictericia", "conjuntivite", "hiperemia"]
    # cache de segmentacao dos alvos
    print("segmentando alvos...", flush=True); alvo_cache = []
    for _, r in alvos.sample(min(400, len(alvos)), random_state=a.seed).iterrows():
        im = ImageOps.exif_transpose(Image.open(DATA / r["file"])).convert("RGB")
        if max(im.size) > 1024: im.thumbnail((1024, 1024))
        sg = segmenta(im)
        if sg and sg[2][2] > 40 and sg[0].sum() > 4 * sg[1].sum() * 0.3:
            fen, iri, (cx, cy, r) = sg; ys, xs = np.nonzero(fen); half = int(max(xs.max() - xs.min(), ys.max() - ys.min()) * rng.uniform(0.9, 1.4))
            x0, y0 = int(max(0, cx - half)), int(max(0, cy - half)); x1, y1 = int(min(im.size[0], cx + half)), int(min(im.size[1], cy + half))
            crop = im.crop((x0, y0, x1, y1)); sg2 = segmenta(crop)
            if sg2 and sg2[2][2] > 40: alvo_cache.append((np.asarray(crop), *sg2))
    print("alvos utilizaveis:", len(alvo_cache), flush=True)
    rows = []; feitas = 0; falhas = 0; por_sinal = {}; CAP = {"conjuntivite": 70, "hiperemia": 50, "ictericia": 50}   # transferencia de cor nunca falha: limitar
    src = src.sample(frac=1, random_state=a.seed); fila = list(src.index); voltas = 0
    while feitas < a.n and fila:
        idx = fila.pop(0); r = src.loc[idx]
        sinal = next((l for l in sinais_ok if r.get(l, 0) == 1), None)
        if sinal is None: continue
        if por_sinal.get(sinal, 0) >= CAP.get(sinal, 10 ** 9): continue
        por_sinal[sinal] = por_sinal.get(sinal, 0) + 1
        try: im = ImageOps.exif_transpose(Image.open(DATA / r["file"])).convert("RGB")
        except Exception: por_sinal[sinal] -= 1; continue
        if max(im.size) > 1024: im.thumbnail((1024, 1024))
        sg = segmenta(im)
        if not sg: por_sinal[sinal] -= 1; continue
        fen_s, iri_s, circ_s = sg; A = np.asarray(im)
        dst_img, fen_d, iri_d, circ_d = rng.choice(alvo_cache)
        if rng.random() < 0.3:
            # colagem negativa: transporta um setor de esclera de OUTRO olho normal (mesma costura, sem sinal)
            src2, fen2, iri2, circ2 = rng.choice(alvo_cache); A2 = np.asarray(src2) if not isinstance(src2, np.ndarray) else src2
            m2 = mascara_lesao(A2, fen2, iri2, circ2, "pterigio")
            colado = cola(A2, m2, circ2, dst_img, fen_d, iri_d, circ_d, rng, lado_troca=rng.random() < 0.5, permite_iris=True) if m2 is not None else None
            if colado is None: continue
            res, _ = colado; labs = []; sinal_out = "normal"
        elif sinal in ("ictericia", "conjuntivite", "hiperemia"):
            res = tinge_esclera(dst_img, fen_d, iri_d, sinal, rng); labs = [sinal] + (["hiperemia"] if sinal == "conjuntivite" else []); sinal_out = sinal
        else:
            m = mascara_lesao(A, fen_s, iri_s, circ_s, sinal)
            if m is None: falhas += 1; por_sinal[sinal] -= 1; continue
            # lado: hemorragia/pterigio podem ir para qualquer lado; pterigio prefere nasal -> mantemos lado da fonte (espelha 50%)
            colado = cola(A, m, circ_s, dst_img, fen_d, iri_d, circ_d, rng, lado_troca=rng.random() < 0.5, permite_iris=(sinal in ("pterigio", "pinguecula")))
            if colado is None: falhas += 1; por_sinal[sinal] -= 1; continue
            res, _ = colado; labs = [sinal]; sinal_out = sinal
        name = f"col_{hashlib.md5((r['file'] + str(feitas)).encode()).hexdigest()[:10]}_{sinal_out}.jpg"; Image.fromarray(res).save(out / name, "JPEG", quality=92)
        if sinal not in CAP and rng.random() < 0.7: fila.append(idx)   # reaproveita a mesma lesao em outro alvo
        rows.append({"file": str((out / name).relative_to(DATA)), "subject_id": "col_" + Path(r["file"]).stem[:40], "source": "colagem", "domain": "phone_closeup", **{l: int(l in labs) for l in LABELS}, "sinal": sinal_out, "fonte": r["file"]}); feitas += 1
        if feitas % 50 == 0: print(f"  {feitas} coladas, {falhas} falhas", flush=True)
    with (DATA / "labels_colagem.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "subject_id", "source", "domain", *LABELS, "sinal", "fonte"]); w.writeheader(); w.writerows(rows)
    import collections; print("coladas:", len(rows), dict(collections.Counter(r["sinal"] for r in rows)), "| falhas", falhas)
if __name__ == "__main__":
    main()
