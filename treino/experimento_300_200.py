"""Uso: EXP_MODELO=convnext_tiny.fb_in22k_ft_in1k EXP_WEB=1 .venv/bin/python treino/experimento_300_200.py
EXP_WEB=1: fotos da busca de imagens (metade A) entram no pool de treino; metade B vira um SEGUNDO teste ("Google").
Experimento simples e honesto: 4 classes (normal, conjuntivite, pterigio, catarata), 300 fotos por classe no treino,
200 por classe separadas por paciente (nunca vistas). Classificador unico (softmax), MobileNetV3 como no app.
Reporta ACURACIA (fracao de fotos com a classe certa) e matriz de confusao. Uso: .venv/bin/python treino/experimento_300_200.py
"""
import os, random, hashlib, time, numpy as np, pandas as pd, torch, torch.nn as nn, timm, torchvision.transforms as T
from pathlib import Path
from PIL import Image, ImageOps
from torch.utils.data import Dataset, DataLoader
BASE = Path(__file__).resolve().parents[1]; D = BASE / "dados"; DEV = "mps" if torch.backends.mps.is_available() else "cpu"
CL = ["normal", "conjuntivite", "pterigio", "catarata_leucocoria"]; random.seed(0); torch.manual_seed(0)
p = pd.read_csv(D / "pool_multiclasse.csv"); p = p[p.classe.isin(CL)]; p = p[p.source != "busca_web"]
MODELO = os.environ.get("EXP_MODELO", "mobilenetv3_large_100"); WEB = os.environ.get("EXP_WEB") == "1"
w = pd.read_csv(D / "externos/labels_busca_web.csv").drop_duplicates("file"); w["classe"] = w["classe"]; w = w[w.classe.isin(CL)]
webB = w[w.metade == "B"]
if WEB: p = pd.concat([p, w[w.metade == "A"]], ignore_index=True)
p["grupo"] = p["subject_id"].astype(str).map(lambda s: int(hashlib.md5(s.encode()).hexdigest(), 16))
tr, te = [], []
for c in CL:
    d = p[p.classe == c].sample(frac=1, random_state=0); grupos = list(dict.fromkeys(d.grupo)); random.Random(1).shuffle(grupos)
    teste_g, n = set(), 0
    for g in grupos:
        if n >= 200: break
        teste_g.add(g); n += int((d.grupo == g).sum())
    dt_ = d[d.grupo.isin(teste_g)].head(200); dr_ = d[~d.grupo.isin(teste_g)]
    if WEB: dr_ = pd.concat([dr_[dr_.source == "busca_web"], dr_[dr_.source != "busca_web"]])   # garante as fotos web no treino
    te.append(dt_); tr.append(dr_.head(300))
tr, te = pd.concat(tr), pd.concat(te); print("treino", tr.classe.value_counts().to_dict(), "| teste", te.classe.value_counts().to_dict())
print("fontes no teste:", te.groupby("classe").source.apply(lambda s: dict(s.value_counts())).to_dict())
M, S = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
ttr = T.Compose([T.RandomResizedCrop(320, scale=(0.4, 1)), T.RandomHorizontalFlip(), T.RandomRotation(15), T.ColorJitter(0.3, 0.3, 0.2, 0.02), T.ToTensor(), T.Normalize(M, S)])
tte = T.Compose([T.Resize(352), T.CenterCrop(320), T.ToTensor(), T.Normalize(M, S)])
class DS(Dataset):
    def __init__(s, d, tf): s.d, s.tf = d.reset_index(drop=True), tf
    def __len__(s): return len(s.d)
    def __getitem__(s, i):
        r = s.d.iloc[i]; im = ImageOps.exif_transpose(Image.open(D / r.file)).convert("RGB"); return s.tf(im), CL.index(r.classe)
dl = DataLoader(DS(tr, ttr), batch_size=32, shuffle=True, num_workers=0); dt = DataLoader(DS(te, tte), batch_size=32, num_workers=0)
m = timm.create_model(MODELO, pretrained=True, num_classes=len(CL)).to(DEV); opt = torch.optim.AdamW(m.parameters(), 3e-4, weight_decay=1e-4)
E = 15; sch = torch.optim.lr_scheduler.OneCycleLR(opt, 1e-3, total_steps=E * len(dl))
for ep in range(E):
    m.train(); t0 = time.time()
    for x, y in dl:
        x, y = x.to(DEV), y.to(DEV); loss = nn.functional.cross_entropy(m(x), y, label_smoothing=0.1); opt.zero_grad(); loss.backward(); opt.step(); sch.step()
    print(f"ep {ep+1}/{E} loss {loss.item():.3f} ({time.time()-t0:.0f}s)", flush=True)
m.eval(); P, Y = [], []
with torch.no_grad():
    for x, y in dt: P.append(m(x.to(DEV)).argmax(1).cpu()); Y.append(y)
P, Y = torch.cat(P).numpy(), torch.cat(Y).numpy()
print(f"\nACURACIA no teste separado (800 fotos, 200 por classe; acaso = 25%): {(P == Y).mean():.1%}")
cm = pd.crosstab(pd.Series([CL[i] for i in Y], name="verdade"), pd.Series([CL[i] for i in P], name="previsto")); print(cm.to_string())
for i, c in enumerate(CL): print(f"  acerto em {c}: {(P[Y == i] == i).mean():.1%}")
torch.save(m.state_dict(), BASE / f"saida/exp_300_200_{MODELO.split('.')[0]}_{'web' if WEB else 'base'}.pt")
P2, Y2 = [], []
with torch.no_grad():
    for x, y in DataLoader(DS(webB, tte), batch_size=32): P2.append(m(x.to(DEV)).argmax(1).cpu()); Y2.append(y)
P2, Y2 = torch.cat(P2).numpy(), torch.cat(Y2).numpy()
print(f"\nACURACIA nas fotos de busca do Google NUNCA vistas (metade B, {len(Y2)} fotos): {(P2 == Y2).mean():.1%}")
for i, c in enumerate(CL):
    if (Y2 == i).sum(): print(f"  {c}: {(P2[Y2 == i] == i).mean():.1%} de {(Y2 == i).sum()}")
for f in ("/Users/Vinicius/Desktop/blog-donato-1.png", str(BASE / "validacao/casos/pterigio_usuario_01.jpg")):
    x = tte(ImageOps.exif_transpose(Image.open(f)).convert("RGB"))[None].to(DEV); pr = torch.softmax(m(x), 1)[0].detach().cpu().numpy()
    print(Path(f).name, "->", CL[pr.argmax()], {c: round(float(v), 2) for c, v in zip(CL, pr)})
torch.save(m.state_dict(), BASE / "saida/exp_300_200.pt")
