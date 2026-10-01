"""Sonda linear sobre JEPA congelado (I-JEPA ViT-H/14 e V-JEPA 2 ViT-L) via transformers: caracteristicas (media dos tokens)
de treino/val/teste + fontes externas (metade B), regressao logistica por rotulo, AUROC. Mesmo protocolo de sonda_dinov2.py.
Uso: .venv/bin/python treino/sonda_jepa.py --modelo facebook/ijepa_vith14_1k [--size 224] [--max-treino 3000]
"""
import argparse, json, time
from pathlib import Path
import numpy as np, pandas as pd, torch
from PIL import Image, ImageOps
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
BASE = Path(__file__).resolve().parents[1]; DATA = BASE / "dados"; OUT = BASE / "saida"
LABELS = ["hiperemia","ictericia","pterigio","pinguecula","catarata_leucocoria","hemorragia_subconjuntival","lesao_pigmentada","opacidade_corneana","tumor_superficie_ocular","ceratite","cisto_conjuntival","lente_intraocular","conjuntivite","uveite","alteracao_palpebral"]
EXTERNOS = ["labels_pubmed_limpo", "labels_commons", "externos/labels_mendeley_conj", "externos/labels_pinkeye", "externos/labels_cekmate_leucocoria", "externos/labels_gh_eyedis5"]
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--modelo", default="facebook/ijepa_vith14_1k"); ap.add_argument("--size", type=int, default=224); ap.add_argument("--versao", default="ocular_v22"); ap.add_argument("--max-treino", type=int, default=3000); ap.add_argument("--lote", type=int, default=8); a = ap.parse_args()
    dev = "mps" if torch.backends.mps.is_available() else "cpu"; tag = a.modelo.split("/")[-1].replace(".", "_")
    from transformers import AutoModel, AutoImageProcessor
    vjepa = "vjepa" in a.modelo.lower()
    if vjepa:
        from transformers import AutoVideoProcessor
        proc = AutoVideoProcessor.from_pretrained(a.modelo); m = AutoModel.from_pretrained(a.modelo, torch_dtype=torch.float32).eval().to(dev)
    else:
        proc = AutoImageProcessor.from_pretrained(a.modelo); m = AutoModel.from_pretrained(a.modelo, torch_dtype=torch.float32).eval().to(dev)
    def feats(files):
        X = []
        for i in range(0, len(files), a.lote):
            ims = []
            for f in files[i:i + a.lote]:
                im = ImageOps.exif_transpose(Image.open(DATA / f)).convert("RGB"); w, h = im.size; s = min(w, h)
                ims.append(im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).resize((a.size, a.size), Image.BILINEAR))
            with torch.no_grad():
                if vjepa:
                    vids = [np.stack([np.asarray(im)] * 2) for im in ims]   # 2 quadros identicos (o modelo exige video)
                    inp = proc(vids, return_tensors="pt").to(dev); out = m.get_vision_features(**inp) if hasattr(m, "get_vision_features") else m(**inp).last_hidden_state
                    X.append((out if out.dim() == 2 else out.mean(1)).float().cpu().numpy())
                else:
                    inp = proc(images=ims, return_tensors="pt").to(dev); out = m(**inp).last_hidden_state; X.append(out.mean(1).float().cpu().numpy())
            if (i // a.lote) % 25 == 0: print(f"  {i}/{len(files)}", flush=True)
        return np.concatenate(X)
    sets = {k: pd.read_csv(OUT / f"split_{a.versao}_{k}.csv") for k in ("train", "val", "test")}
    if len(sets["train"]) > a.max_treino: sets["train"] = sets["train"].sample(a.max_treino, random_state=0)
    for name in EXTERNOS:
        d = pd.read_csv(DATA / f"{name}.csv")
        for l in LABELS:
            if l not in d.columns: d[l] = 0
        if "metade" in d.columns: d = d[d["metade"] == "B"]
        sets[Path(name).stem] = d
    F = {}; t0 = time.time()
    for k, d in sets.items():
        d = d[d["file"].map(lambda f: (DATA / f).exists())].reset_index(drop=True); sets[k] = d; print(k, len(d), flush=True); F[k] = feats(d["file"].tolist())
    print(f"caracteristicas em {time.time()-t0:.0f}s ({tag})"); np.savez_compressed(OUT / f"feats_{tag}.npz", **F)
    Xtr = np.concatenate([F["train"], F["val"]]); Ytr = pd.concat([sets["train"], sets["val"]])[LABELS].to_numpy(); res = {}
    lines = [f"# Sonda linear sobre {a.modelo} (congelado) · treino {len(Xtr)} imagens\n", "| sinal | " + " | ".join(k for k in sets if k not in ("train", "val")) + " |", "|---|" + "---:|" * (len(sets) - 2)]
    for j, l in enumerate(LABELS):
        y = Ytr[:, j]
        if y.sum() < 5: continue
        clf = LogisticRegression(C=0.5, max_iter=3000, class_weight="balanced").fit(Xtr, y); res[l] = {}; cells = []
        for k in sets:
            if k in ("train", "val"): continue
            yk = sets[k][l].to_numpy()
            if 0 < yk.sum() < len(yk): auc = roc_auc_score(yk, clf.predict_proba(F[k])[:, 1]); res[l][k] = dict(n=int(yk.sum()), auroc=round(float(auc), 3)); cells.append(f"{auc:.2f} ({int(yk.sum())})")
            else: cells.append("–")
        lines.append(f"| {l} | " + " | ".join(cells) + " |")
    med = []
    for k in sets:
        if k in ("train", "val"): continue
        aucs = [v[k]["auroc"] for v in res.values() if k in v and v[k]["n"] >= 5]; med.append(f"{np.mean(aucs):.3f}" if aucs else "–")
    lines.append("| **AUROC médio (n≥5)** | " + " | ".join(med) + " |")
    md = "\n".join(lines); print(md); (OUT / f"sonda_{tag}.md").write_text(md); json.dump(res, open(OUT / f"sonda_{tag}.json", "w"), indent=1)
if __name__ == "__main__":
    main()
