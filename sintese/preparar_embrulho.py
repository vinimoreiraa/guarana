"""Parte CPU do embrulho: para cada foto real com sinal (CSVs), roda o segmentador, filtra por plausibilidade e salva
mascara da fenda (PNG branco) + circulo da iris num JSON de trabalhos para o Blender (sintese/embrulhar_lote.sh).
Uso: .venv/bin/python sintese/preparar_embrulho.py --csvs a.csv b.csv --max-por-sinal 60 --out sintese/embrulho_jobs
"""
import argparse, json, math, hashlib, sys
from pathlib import Path
import numpy as np, pandas as pd, onnxruntime as ort
from PIL import Image, ImageOps
BASE = Path(__file__).resolve().parents[1]; DATA = BASE / "dados"
LABELS = ["hiperemia","ictericia","pterigio","pinguecula","catarata_leucocoria","hemorragia_subconjuntival","lesao_pigmentada","opacidade_corneana","tumor_superficie_ocular","ceratite","cisto_conjuntival","lente_intraocular","conjuntivite","uveite","alteracao_palpebral"]
card = json.load(open(BASE / "saida/fenda_card.json")); S = card["input"]["size"]; MEAN, STD = np.array(card["input"]["mean"], np.float32), np.array(card["input"]["std"], np.float32)
sess = ort.InferenceSession(str(BASE / "saida/fenda_v1.onnx"), providers=["CPUExecutionProvider"])
def segmenta(im):
    w, h = im.size; x = ((np.asarray(im.resize((S, S), Image.BILINEAR), np.float32) / 255 - MEAN) / STD).transpose(2, 0, 1)[None]
    pr = 1 / (1 + np.exp(-sess.run(None, {"image": x})[0][0]))
    fen = np.asarray(Image.fromarray((pr[0] * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)) > 128
    iri = np.asarray(Image.fromarray((pr[1] * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)) > 128
    return fen, iri
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--csvs", nargs="+", required=True); ap.add_argument("--max-por-sinal", type=int, default=60); ap.add_argument("--out", default="sintese/embrulho_jobs"); ap.add_argument("--com-normais", action="store_true"); a = ap.parse_args()
    out = BASE / a.out; out.mkdir(parents=True, exist_ok=True); jobs = []; por = {}
    df = pd.concat([pd.read_csv(c) for c in a.csvs], ignore_index=True)
    for l in LABELS:
        if l not in df.columns: df[l] = 0
    if "metade" in df.columns: df = df[df["metade"] == "A"]   # metade B fica como teste
    ap_norm = a.com_normais
    df = df[(df[LABELS].sum(axis=1) > 0) | ap_norm].sample(frac=1, random_state=0)
    for _, r in df.iterrows():
        sinais = [l for l in LABELS if r[l] == 1]; chave = sinais[0] if sinais else "normal"
        if por.get(chave, 0) >= a.max_por_sinal: continue
        try: im = ImageOps.exif_transpose(Image.open(DATA / r["file"])).convert("RGB")
        except Exception: continue
        if max(im.size) > 1024: im.thumbnail((1024, 1024))
        w, h = im.size; fen, iri = segmenta(im)
        if iri.sum() < 50: continue
        ys, xs = np.nonzero(iri); cx, cy = xs.mean(), ys.mean(); rr = max((xs.max() - xs.min()) / 2, math.sqrt(iri.sum() / math.pi))
        # plausibilidade: iris entre 6% e 40% do lado; fenda entre 1,5x e 8x a area da iris; iris dentro da fenda; centro nao na borda
        if not (0.10 * min(w, h) < rr < 0.40 * min(w, h)): continue
        # a fenda tem de caber no globo: raio maximo do contorno (em mm, 2r px = 12 mm) < 11.5 mm
        yy, xx = np.nonzero(fen); dmax = np.hypot(xx - cx, yy - cy).max() * 6.0 / rr
        if dmax > 11.5: continue
        if not (1.3 * iri.sum() < fen.sum() < 5 * iri.sum()): continue
        if (fen & iri).sum() < 0.8 * iri.sum(): continue
        if not (0.15 * w < cx < 0.85 * w and 0.15 * h < cy < 0.85 * h): continue
        sid = hashlib.md5(r["file"].encode()).hexdigest()[:10]; im.save(out / f"{sid}.jpg", "JPEG", quality=95); Image.fromarray((fen * 255).astype(np.uint8)).save(out / f"{sid}_fenda.png")
        jobs.append({"id": sid, "foto": str(out / f"{sid}.jpg"), "mascara": str(out / f"{sid}_fenda.png"), "iris": [round(cx, 1), round(cy, 1), round(rr, 1)], "rotulos": sinais, "origem": r["file"], "source": r.get("source", "")}); por[chave] = por.get(chave, 0) + 1
    json.dump(jobs, open(out / "jobs.json", "w"), indent=1); print("trabalhos:", len(jobs), por)
if __name__ == "__main__":
    main()
