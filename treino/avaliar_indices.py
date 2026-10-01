"""Ramo A com dados da internet: quanto os indices de cor da esclera (ROI pelo segmentador) separam icterícia e hiperemia de olho
normal, SEM controle de luz (fotos aleatorias). Variantes: bruto e normalizado pela pele periocular da mesma foto (referencia
de conveniencia que cancela parte do iluminante). E o piso do ramo A; com flash+ambiente subtraido e cartao branco so melhora.
Saida: saida/avaliacao_indices.md. Uso: .venv/bin/python treino/avaliar_indices.py
"""
import json, math, hashlib
from pathlib import Path
import numpy as np, pandas as pd, onnxruntime as ort
from PIL import Image, ImageOps, ImageFilter
from sklearn.metrics import roc_auc_score
BASE = Path(__file__).resolve().parents[1]; D = BASE / "dados"; OUT = BASE / "saida"
card = json.load(open(OUT / "fenda_card.json")); S = card["input"]["size"]; MEAN, STD = np.array(card["input"]["mean"], np.float32), np.array(card["input"]["std"], np.float32)
sess = ort.InferenceSession(str(OUT / "fenda_v1.onnx"), providers=["CPUExecutionProvider"])
def masks(im):
    w, h = im.size; x = ((np.asarray(im.resize((S, S), Image.BILINEAR), np.float32) / 255 - MEAN) / STD).transpose(2, 0, 1)[None]
    pr = 1 / (1 + np.exp(-sess.run(None, {"image": x})[0][0]))
    fen = np.asarray(Image.fromarray((pr[0] * 255).astype(np.uint8)).resize((w, h))) > 128; iri = np.asarray(Image.fromarray((pr[1] * 255).astype(np.uint8)).resize((w, h))) > 128
    return fen, iri
from scipy.ndimage import distance_transform_edt
def dil(m, k):
    if k <= 0 or not m.any(): return m.copy()
    return distance_transform_edt(~m) <= k   # dilatacao por transformada de distancia: rapida mesmo com k grande
def indices(im):
    a = np.asarray(im).astype(np.float32); fen, iri = masks(im)
    if iri.sum() < 50 or fen.sum() < 200: return None
    esc = fen & ~dil(iri, 4) & (a.max(axis=2) < 245) & (a.min(axis=2) > 15)      # esclera sem brilho estourado nem sombra
    if esc.sum() < 100: return None
    pele = dil(fen, int(math.sqrt(fen.sum()) * 0.6)) & ~dil(fen, 6); pele &= (a.max(axis=2) < 245)
    e = a[esc].mean(0) + 1e-3; p = a[pele].mean(0) + 1e-3 if pele.sum() > 100 else None
    r = {"ict_lnRB": math.log(e[0] / e[2]), "hip_Rfrac": e[0] / e.sum(), "pal_lnRG": math.log(e[0] / e[1]), "n_esclera": int(esc.sum())}
    if p is not None: r.update({"ict_lnRB_pele": math.log((e[0] / p[0]) / (e[2] / p[2])), "hip_Rfrac_pele": (e[0] / p[0]) / ((e / p).sum()), "pal_lnRG_pele": math.log((e[0] / p[0]) / (e[1] / p[1]))})
    return r
def carrega(csvs, cond, n_max, seed):
    rows = []
    for c in csvs:
        d = pd.read_csv(D / c); d = d[cond(d)]; rows.append(d)
    d = pd.concat(rows); return d.sample(min(n_max, len(d)), random_state=seed)
def medir(df):
    out = []
    for _, r in df.iterrows():
        try: im = ImageOps.exif_transpose(Image.open(D / r["file"])).convert("RGB")
        except Exception: continue
        if max(im.size) > 640: im.thumbnail((640, 640))
        v = indices(im)
        if v: out.append(v)
        if len(out) % 50 == 0 and v: print(f"  {len(out)}", flush=True)
    return pd.DataFrame(out)
def main():
    normais = carrega(["externos/labels_zenodo_normais.csv", "labels_commons.csv"], lambda d: (d[[c for c in d.columns if c in ("hiperemia", "ictericia", "conjuntivite")]].sum(axis=1) == 0) & (d.get("normal", 1) == 1) if "normal" in d.columns else (d[["hiperemia", "ictericia", "conjuntivite"]].sum(axis=1) == 0), 300, 0)
    ict = carrega(["labels_commons.csv", "labels_hf_jaundice.csv"], lambda d: d["ictericia"] == 1, 120, 0)
    hip = carrega(["externos/labels_pinkeye.csv", "labels_commons.csv"], lambda d: d["hiperemia"] == 1, 200, 0)
    N, I, H = medir(normais), medir(ict), medir(hip); print(f"medidos: normais {len(N)} | icterícia {len(I)} | hiperemia {len(H)}")
    lines = ["# Índices do ramo A em fotos da internet (ROI = segmentador; sem controle de luz)\n", f"normais {len(N)} · icterícia {len(I)} · hiperemia {len(H)}\n", "| tarefa | índice | AUROC bruto | AUROC normalizado pela pele |", "|---|---|---:|---:|"]
    for nome, P, idx in (("icterícia vs normal", I, "ict_lnRB"), ("hiperemia vs normal", H, "hip_Rfrac"), ("icterícia vs normal (ln R/G)", I, "pal_lnRG")):
        y = np.r_[np.ones(len(P)), np.zeros(len(N))]
        def auc(col):
            v = pd.concat([P, N])[col]; ok = v.notna().to_numpy(); return roc_auc_score(y[ok], v.to_numpy()[ok]) if ok.sum() > 10 else float("nan")
        lines.append(f"| {nome} | {idx} | {auc(idx):.2f} | {auc(idx + '_pele'):.2f} |")
    md = "\n".join(lines); (OUT / "avaliacao_indices.md").write_text(md); print(md)
if __name__ == "__main__":
    main()
