"""Ramo de cor, palidez/anemia com dados publicos: regressor de hemoglobina na foto da conjuntiva.
- CP-AnemiC (Gana, 710 criancas, Hb de laboratorio): recortes da conjuntiva palpebral em fundo branco.
  Validacao cruzada em 5 dobras (cada imagem e uma crianca). Metricas: MAE, Spearman, AUROC para anemia (Hb < 11 g/dL,
  criterio OMS 6-59 meses) e anemia grave (Hb < 7). Compara com a regra de cor linear (L, a, b, fracao de vermelho).
- anemia-eyes (HF, = Eyes-Defy-Anemia sem Hb, India/Italia, olho inteiro com palpebra puxada): teste de transferencia
  entre fontes, so classe. A conjuntiva e recortada por heuristica de cor (regiao rosada na metade inferior).
Saida: saida/palidez_v1.onnx + palidez_card.json se AUROC(CV) >= 0.75; sempre saida/avaliacao_palidez.md.
"""
import os, json, datetime
from pathlib import Path
import numpy as np, pandas as pd, torch, torch.nn as nn, timm
import torch.multiprocessing as _tmp; _tmp.set_start_method("fork", force=True)
from PIL import Image, ImageOps
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import roc_auc_score
from scipy.stats import spearmanr
BASE = Path(__file__).resolve().parents[1]; DS = BASE / "dados/raw/cp_anemic/extract/CP-AnemiC dataset"; OUT = BASE / "saida"
DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"; SIZE = 224; SEED = 3; EPOCHS = int(os.environ.get("PAL_EPOCHS", 14))
torch.manual_seed(SEED); np.random.seed(SEED)
MEAN, STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]

sheet = pd.read_excel(DS / "Anemia_Data_Collection_Sheet.xlsx")
sheet.columns = [str(c).strip() for c in sheet.columns]
col_img = next(c for c in sheet.columns if "image" in c.lower() or "id" in c.lower()); col_hb = next(c for c in sheet.columns if "hb" in c.lower() or "hemoglobin" in c.lower())
files = {p.stem: p for p in DS.rglob("*.png")} | {p.stem: p for p in DS.rglob("*.jpg")}
rows = []
for _, r in sheet.iterrows():
    k = str(r[col_img]).strip()
    p = files.get(k) or next((v for kk, v in files.items() if kk.lower() == k.lower()), None)
    if p is None or pd.isna(r[col_hb]): continue
    rows.append({"path": p, "hb": float(r[col_hb])})
df = pd.DataFrame(rows); print(f"CP-AnemiC: {len(df)} imagens com Hb | anemia (<11) {(df.hb < 11).mean():.0%} | grave (<7) {(df.hb < 7).mean():.1%}")

def load(p):
    im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
    # fundo branco do recorte: recorta a caixa da regiao nao-branca
    a = np.asarray(im); m = (a.min(2) < 235)
    ys, xs = np.nonzero(m)
    if len(xs) > 100: im = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    return im

class DS_(Dataset):
    def __init__(self, d, train): self.d = d.reset_index(drop=True); self.train = train
    def __len__(self): return len(self.d)
    def __getitem__(self, i):
        r = self.d.iloc[i]; im = load(r["path"]).resize((SIZE, SIZE), Image.BILINEAR)
        x = np.asarray(im, np.float32) / 255
        if self.train:
            rng = np.random.default_rng()
            if rng.random() < 0.5: x = x[:, ::-1]
            x = np.clip(x * rng.uniform(0.85, 1.15), 0, 1)          # brilho global apenas: nao mexe na cor relativa
        x = (x - MEAN) / STD
        return torch.from_numpy(np.ascontiguousarray(x.transpose(2, 0, 1))).float(), torch.tensor([r["hb"]], dtype=torch.float32)

def train_fold(tr, va):
    model = timm.create_model("mobilenetv3_small_100", pretrained=True, num_classes=1).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=5e-4, weight_decay=1e-4)
    dl = DataLoader(DS_(tr, True), batch_size=32, shuffle=True, num_workers=4); dv = DataLoader(DS_(va, False), batch_size=64, num_workers=4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=5e-4, total_steps=EPOCHS * len(dl))
    for ep in range(EPOCHS):
        model.train()
        for x, y in dl:
            x, y = x.to(DEVICE), y.to(DEVICE); opt.zero_grad(); loss = nn.functional.l1_loss(model(x), y); loss.backward(); opt.step(); sched.step()
    model.eval(); P = []
    with torch.no_grad():
        for x, _ in dv: P.append(model(x.to(DEVICE)).cpu().numpy().ravel())
    return model, np.concatenate(P)

idx = np.arange(len(df)); rng = np.random.default_rng(SEED); rng.shuffle(idx); folds = np.array_split(idx, 5)
pred = np.zeros(len(df)); models = []
for k, f in enumerate(folds):
    tr = df.iloc[np.setdiff1d(idx, f)]; va = df.iloc[f]
    m, p = train_fold(tr, va); pred[f] = p; models.append(m); print(f"dobra {k+1}: MAE {np.abs(p - va.hb.to_numpy()).mean():.2f}", flush=True)
y = df.hb.to_numpy()
rep = {"data": datetime.datetime.now().isoformat(timespec="seconds"), "n": int(len(df)),
       "cnn": {"mae": round(float(np.abs(pred - y).mean()), 2), "spearman": round(float(spearmanr(pred, y).correlation), 3),
               "auroc_anemia_hb_lt_11": round(float(roc_auc_score((y < 11).astype(int), -pred)), 3),
               "auroc_grave_hb_lt_7": round(float(roc_auc_score((y < 7).astype(int), -pred)), 3) if (y < 7).sum() > 3 else None}}
# baseline: regra de cor linear nas mesmas dobras (features do calibrar_palidez.py)
feat = pd.read_csv(BASE / "dados/calibracao_palidez.csv") if (BASE / "dados/calibracao_palidez.csv").exists() else None
if feat is not None:
    feat["stem"] = feat["image"].astype(str); df["stem"] = df["path"].apply(lambda p: p.stem)
    mm = df.merge(feat[["stem", "L", "a", "b", "r_frac"]], on="stem", how="inner")
    if len(mm) > 100:
        X = mm[["L", "a", "b", "r_frac"]].to_numpy(); yy = mm.hb.to_numpy(); pb = np.zeros(len(mm)); ii = np.arange(len(mm)); rng.shuffle(ii)
        for f in np.array_split(ii, 5):
            tr = np.setdiff1d(ii, f); A = np.c_[X[tr], np.ones(len(tr))]; w = np.linalg.lstsq(A, yy[tr], rcond=None)[0]; pb[f] = np.c_[X[f], np.ones(len(f))] @ w
        rep["regra_cor_linear"] = {"n": int(len(mm)), "mae": round(float(np.abs(pb - yy).mean()), 2), "spearman": round(float(spearmanr(pb, yy).correlation), 3),
                                   "auroc_anemia_hb_lt_11": round(float(roc_auc_score((yy < 11).astype(int), -pb)), 3)}
# transferencia: anemia-eyes (classe), ROI rosada na metade inferior
AE = BASE / "dados/raw/anemia_eyes"; ae = [(p, 1 if p.parent.name.lower().startswith("anemia") else 0) for p in list(AE.rglob("*.jpg")) + list(AE.rglob("*.png"))]
def roi_conj(im):
    a = np.asarray(im.convert("RGB"), np.float32); h, w, _ = a.shape; lower = a[h // 3:]
    r, g, b = lower[..., 0], lower[..., 1], lower[..., 2]
    m = (r > 120) & (r > g * 1.15) & (r > b * 1.15) & ((r - b) > 25)      # rosa/vermelho da conjuntiva
    ys, xs = np.nonzero(m)
    if len(xs) < 500: return im.crop((w // 4, h // 3, 3 * w // 4, h))
    y0, y1 = np.percentile(ys, 5), np.percentile(ys, 95); x0, x1 = np.percentile(xs, 5), np.percentile(xs, 95)
    return im.crop((int(x0), int(y0 + h // 3), int(x1), int(y1 + h // 3)))
if ae:
    scores = []; labels = []
    with torch.no_grad():
        for p, lab in ae:
            im = roi_conj(ImageOps.exif_transpose(Image.open(p))).resize((SIZE, SIZE), Image.BILINEAR)
            x = torch.from_numpy(np.ascontiguousarray(((np.asarray(im, np.float32) / 255 - MEAN) / STD).transpose(2, 0, 1))).float()[None].to(DEVICE)
            scores.append(float(np.mean([m(x).item() for m in models]))); labels.append(lab)
    rep["transferencia_anemia_eyes"] = {"n": len(ae), "auroc_classe_anemia": round(float(roc_auc_score(labels, -np.array(scores))), 3), "hb_prevista_media": round(float(np.mean(scores)), 1)}
(OUT / "avaliacao_palidez.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False))
md = [f"# Palidez / anemia com dados públicos · {rep['data']}", "", f"CP-AnemiC: {rep['n']} crianças com Hb. Validação cruzada em 5 dobras.", "",
      "| método | MAE (g/dL) | Spearman | AUROC anemia (Hb < 11) | AUROC grave (Hb < 7) |", "|---|---:|---:|---:|---:|",
      f"| CNN na conjuntiva (MobileNetV3-small) | {rep['cnn']['mae']} | {rep['cnn']['spearman']} | {rep['cnn']['auroc_anemia_hb_lt_11']} | {rep['cnn']['auroc_grave_hb_lt_7']} |"]
if "regra_cor_linear" in rep: md.append(f"| regra de cor linear (L, a, b, fração de vermelho) | {rep['regra_cor_linear']['mae']} | {rep['regra_cor_linear']['spearman']} | {rep['regra_cor_linear']['auroc_anemia_hb_lt_11']} | – |")
if "transferencia_anemia_eyes" in rep: md += ["", f"Transferência para anemia-eyes (Índia/Itália, outro dispositivo, só classe): AUROC {rep['transferencia_anemia_eyes']['auroc_classe_anemia']} em {rep['transferencia_anemia_eyes']['n']} fotos, com ROI por heurística de cor."]
(OUT / "avaliacao_palidez.md").write_text("\n".join(md)); print("\n".join(md))
if rep["cnn"]["auroc_anemia_hb_lt_11"] >= 0.75:
    best = models[0].eval().to("cpu"); dummy = torch.randn(1, 3, SIZE, SIZE)
    torch.onnx.export(best, dummy, str(OUT / "palidez_v1.onnx"), input_names=["image"], output_names=["hb"], opset_version=17, dynamo=False)
    json.dump({"name": "palidez_v1", "file": "palidez_v1.onnx", "input": {"size": SIZE, "mean": MEAN, "std": STD, "roi": "conjuntiva palpebral recortada"}, "output": "hb_g_dL",
               "validado_em": "CP-AnemiC (Gana, 6-59 meses); transferencia anemia-eyes so classe", "metrics": rep}, open(OUT / "palidez_card.json", "w"), indent=2)
    print("exportado palidez_v1.onnx")
