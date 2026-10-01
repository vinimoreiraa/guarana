"""E3: codificador congelado + sonda linear. Extrai caracteristicas (DINOv2 ViT-S/14 ou SigLIP) de todas as imagens
de treino/val/teste e dos CSVs externos, treina uma regressao logistica por rotulo nas caracteristicas do treino
e mede nos externos. Pouco dado + codificador forte costuma transferir melhor que ajustar a MobileNet inteira.
Uso: .venv/bin/python treino/sonda_dinov2.py [--modelo vit_small_patch14_dinov2.lvd142m] [--size 224]
Saida: saida/sonda_<modelo>.json/.md, saida/feats_<modelo>.npz
"""
import argparse, json, time
from pathlib import Path
import numpy as np, pandas as pd, torch, timm
from PIL import Image, ImageOps
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
BASE = Path(__file__).resolve().parents[1]; DATA = BASE / "dados"; OUT = BASE / "saida"
LABELS = ["hiperemia","ictericia","pterigio","pinguecula","catarata_leucocoria","hemorragia_subconjuntival","lesao_pigmentada","opacidade_corneana",
          "tumor_superficie_ocular","ceratite","cisto_conjuntival","lente_intraocular","conjuntivite","uveite","alteracao_palpebral"]
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--modelo", default="vit_small_patch14_dinov2.lvd142m"); ap.add_argument("--size", type=int, default=224); ap.add_argument("--versao", default="ocular_v21"); a = ap.parse_args()
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    m = timm.create_model(a.modelo, pretrained=True, num_classes=0, img_size=a.size).eval().to(dev)
    cfg = timm.data.resolve_data_config({}, model=m); mean, std = np.array(cfg["mean"], np.float32), np.array(cfg["std"], np.float32)
    def feats(files):
        X = []
        for i in range(0, len(files), 32):
            xs = []
            for f in files[i:i + 32]:
                im = ImageOps.exif_transpose(Image.open(DATA / f)).convert("RGB"); w, h = im.size; s = min(w, h)
                im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).resize((a.size, a.size), Image.BILINEAR)
                xs.append(((np.asarray(im, np.float32) / 255 - mean) / std).transpose(2, 0, 1))
            with torch.no_grad(): X.append(m(torch.tensor(np.stack(xs)).to(dev)).float().cpu().numpy())
            if (i // 32) % 20 == 0: print(f"  {i}/{len(files)}", flush=True)
        return np.concatenate(X)
    sets = {k: pd.read_csv(OUT / f"split_{a.versao}_{k}.csv") for k in ("train", "val", "test")}
    for name in ("labels_pubmed_limpo", "labels_commons"):
        d = pd.read_csv(DATA / f"{name}.csv")
        for l in LABELS:
            if l not in d.columns: d[l] = 0
        sets[name] = d
    F = {}; t0 = time.time()
    for k, d in sets.items():
        d = d[d["file"].map(lambda f: (DATA / f).exists())].reset_index(drop=True); sets[k] = d
        print(k, len(d), flush=True); F[k] = feats(d["file"].tolist())
    print(f"caracteristicas em {time.time()-t0:.0f}s"); tag = a.modelo.replace("/", "_").replace(".", "_")
    np.savez_compressed(OUT / f"feats_{tag}.npz", **{k: F[k] for k in F})
    Xtr = np.concatenate([F["train"], F["val"]]); Ytr = pd.concat([sets["train"], sets["val"]])[LABELS].to_numpy()
    res = {}; lines = [f"# Sonda linear sobre {a.modelo} (congelado) · treino {len(Xtr)} imagens\n", "| sinal | teste interno AUROC | PubMed limpo AUROC (n) | Commons AUROC (n) |", "|---|---:|---:|---:|"]
    for j, l in enumerate(LABELS):
        y = Ytr[:, j]
        if y.sum() < 5: continue
        clf = LogisticRegression(C=0.5, max_iter=2000, class_weight="balanced").fit(Xtr, y); res[l] = {}
        cells = []
        for k in ("test", "labels_pubmed_limpo", "labels_commons"):
            yk = sets[k][l].to_numpy(); 
            if 0 < yk.sum() < len(yk):
                auc = roc_auc_score(yk, clf.predict_proba(F[k])[:, 1]); res[l][k] = dict(n=int(yk.sum()), auroc=round(float(auc), 3)); cells.append(f"{auc:.2f} ({int(yk.sum())})")
            else: cells.append("–")
        lines.append(f"| {l} | " + " | ".join(cells) + " |")
    for k in ("test", "labels_pubmed_limpo", "labels_commons"):
        aucs = [v[k]["auroc"] for v in res.values() if k in v]
        if aucs: lines.append(f"\nAUROC médio {k}: {np.mean(aucs):.3f} ({len(aucs)} sinais)")
    md = "\n".join(lines); print(md); (OUT / f"sonda_{tag}.md").write_text(md); json.dump(res, open(OUT / f"sonda_{tag}.json", "w"), indent=1)
if __name__ == "__main__":
    main()
