# GERADO por build_notebook.py a partir das celulas do notebook. Edite build_notebook.py.
import sys, subprocess, os
IN_COLAB = "google.colab" in sys.modules
if IN_COLAB:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "timm>=1.0", "onnx", "onnxruntime", "onnxscript",
                    "scikit-learn", "pandas", "pillow"], check=True)
import torch
if torch.cuda.is_available():
    DEVICE = "cuda"
elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
    DEVICE = "mps"
else:
    DEVICE = "cpu"
print("torch", torch.__version__, "| device:", DEVICE)
if IN_COLAB:
    from google.colab import drive
    drive.mount("/content/drive")

# %% ---------------------------------------------
from pathlib import Path
_BASE = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path("..").resolve()
DATA_DIR = Path("/content/drive/MyDrive/ocular-ia/dados") if IN_COLAB else _BASE / "dados"
OUT_DIR  = Path("/content/drive/MyDrive/ocular-ia/saida") if IN_COLAB else _BASE / "saida"
OUT_DIR.mkdir(parents=True, exist_ok=True)
SMOKE = os.environ.get("OCULAR_SMOKE") == "1"     # teste rapido do pipeline: poucas imagens, 1 epoca

# Sinais treinaveis na v1. Os demais do PDF (arco, esclera azul, Bitot, ocronose, telangiectasia)
# ficam no CSV para coleta, mas so entram aqui quando houver >= MIN_POS exemplos.
LABELS = ["hiperemia", "ictericia", "pterigio", "pinguecula", "catarata_leucocoria", "hemorragia_subconjuntival",
          "lesao_pigmentada", "opacidade_corneana", "tumor_superficie_ocular", "ceratite", "cisto_conjuntival",
          "lente_intraocular", "conjuntivite", "uveite", "alteracao_palpebral"]
# palidez_conjuntival fica fora do CNN: os dados publicos (CP-AnemiC) sao recortes de conjuntiva em fundo branco,
# outro dominio; entra pela regra de cor calibrada nesses recortes.

MODEL_NAME  = os.environ.get("OCULAR_MODEL", "mobilenetv3_large_100")   # ex.: convnext_tiny.fb_in22k_ft_in1k, vit_small_patch14_dinov2.lvd142m   # ~5.5M params, ~22 MB fp32, ~6 MB int8
IMG_SIZE    = int(os.environ.get("OCULAR_IMG_SIZE", 320))
BATCH       = 32
EPOCHS_HEAD = int(os.environ.get("OCULAR_EPOCHS_HEAD", 3))    # fase 1: so a cabeca
EPOCHS_FULL = int(os.environ.get("OCULAR_EPOCHS_FULL", 15))   # fase 2: rede inteira
if SMOKE: EPOCHS_HEAD, EPOCHS_FULL = 1, 1
LR_HEAD, LR_FULL = 1e-3, 2e-4
SEED        = 42
TARGET_SENS = 0.90   # sensibilidade alvo para escolher o limiar de cada sinal
MIN_POS     = 15     # minimo de positivos no treino para considerar o sinal confiavel
VERSION     = "ocular_v21"   # v2.1 = mesmos rotulos, mais pterigio em foto comum (HF), recorte mais forte, limiares com TTA

# %% ---------------------------------------------
import pandas as pd, numpy as np
from PIL import Image, ImageOps
EXTS = {".jpg", ".jpeg", ".png", ".webp"}

def rows_from_folders(root, mapping, source):
    # root/<pasta>/*.jpg ; mapping = {"pasta": ["hiperemia"], "normal": []}
    root = Path(root); rows = []
    for folder, labs in mapping.items():
        for p in sorted((root / folder).glob("*")):
            if p.suffix.lower() not in EXTS:
                continue
            rel = p.relative_to(DATA_DIR) if DATA_DIR in p.parents else p
            r = {"file": str(rel), "subject_id": f"{source}_{p.stem}", "source": source}
            for l in LABELS:
                r[l] = int(l in labs)
            rows.append(r)
    return pd.DataFrame(rows)

# exemplo (descomente e ajuste):
# extra = rows_from_folders(DATA_DIR / "kaggle_pterigio", {"pterygium": ["pterigio_pinguecula"], "normal": []}, "kaggle_pterigio")
# extra.to_csv(DATA_DIR / "labels_kaggle_pterigio.csv", index=False)

# Teste externo: CSVs que NUNCA entram no treino (fonte nova = regua de campo). Sintese entra so quando pedida.
EXTERNAL_CSVS = [x for x in os.environ.get("OCULAR_EXTERNAL_CSVS", "labels_pubmed_limpo.csv,labels_commons.csv").split(",") if x]
NEVER_TRAIN = ("labels_pubmed", "labels_commons", "exemplo")
USE_SINTESE = os.environ.get("OCULAR_USE_SINTESE") == "1"
TAG = os.environ.get("OCULAR_TAG", "")
if TAG: VERSION = VERSION + "_" + TAG
csvs = sorted(DATA_DIR.glob("labels*.csv"))
csvs = [c for c in csvs if not any(k in c.name for k in NEVER_TRAIN) and (USE_SINTESE or "sintese" not in c.name)]
print("CSVs de treino:", [c.name for c in csvs])
assert csvs, f"nenhum labels*.csv em {DATA_DIR}"
df = pd.concat([pd.read_csv(c) for c in csvs], ignore_index=True)
for l in LABELS:
    if l not in df.columns:
        df[l] = 0
df[LABELS] = df[LABELS].fillna(0).astype(int)
exists = df["file"].apply(lambda f: (DATA_DIR / f).exists())
print("arquivos ausentes (ignorados):", int((~exists).sum()))
df = df[exists].drop_duplicates("file").reset_index(drop=True)
if SMOKE: df = df.sample(min(400, len(df)), random_state=SEED).reset_index(drop=True)
if "domain" not in df.columns: df["domain"] = "desconhecido"
# validacao "fonte de fora" (leave-one-source-out): OCULAR_EXCLUDE_SOURCES=hf_pterygium treina sem essa fonte e a usa
# inteira como teste no fim. Mede o que o modelo faz numa base que nunca viu, o substituto honesto de "vai funcionar no tablet".
EXCL = [x for x in os.environ.get("OCULAR_EXCLUDE_SOURCES", "").split(",") if x]
holdout = df[df["source"].isin(EXCL)].copy() if EXCL else None
if EXCL:
    df = df[~df["source"].isin(EXCL)].copy(); VERSION = VERSION + "_sem_" + "_".join(EXCL)
    print("fonte(s) de fora:", EXCL, "|", len(holdout), "imagens de teste externo")
LABEL_MASK = os.environ.get("OCULAR_LABEL_MASK") == "1"
COMPLETAS = ("colagem", "sintese_")   # rotulo completo: base normal + sinal colado / sintese com todos os rotulos
for l in LABELS: df["k_" + l] = 1
if LABEL_MASK:
    for src, d in df.groupby("source"):
        if src.startswith(COMPLETAS) or d[LABELS].sum().sum() == 0: continue   # normais puros e fontes completas: tudo conhecido
        conhecidos = [l for l in LABELS if d[l].sum() > 0]
        for l in LABELS:
            if l not in conhecidos: df.loc[d.index, "k_" + l] = 0
    print("mascara de rotulos por fonte: fracao conhecida por rotulo", {l: round(float(df["k_" + l].mean()), 2) for l in LABELS})
print(len(df), "imagens |", int((df[LABELS].sum(axis=1) == 0).sum()), "negativas")
print(df.groupby("source")[LABELS].sum().assign(n=df.groupby("source").size()).to_string())
print(df[LABELS].sum().to_string())

# %% ---------------------------------------------
from sklearn.model_selection import GroupShuffleSplit

def split_groups(d, test_size, seed):
    gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    a, b = next(gss.split(d, groups=d["subject_id"]))
    return d.iloc[a].reset_index(drop=True), d.iloc[b].reset_index(drop=True)

trainval, test = split_groups(df, 0.15, SEED)
train, val = split_groups(trainval, 0.15, SEED)
for name, d in [("train", train), ("val", val), ("test", test)]:
    print(f"{name:5s} {len(d):5d}", d[LABELS].sum().to_dict())
few = [l for l in LABELS if train[l].sum() < MIN_POS]
if few:
    print("\nAVISO: poucos positivos no treino para", few, "-> marcados como nao confiaveis no model_card")

# %% ---------------------------------------------
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as T

MEAN, STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
AUG = os.environ.get("OCULAR_AUG", "normal")
class BorraoPIL:
    def __init__(self, p=0.3): self.p = p
    def __call__(self, im):
        import random as _r
        from PIL import ImageFilter
        return im.filter(ImageFilter.GaussianBlur(_r.uniform(0.3, 2.0))) if _r.random() < self.p else im
class TelaPIL:
    """simula fotografar a imagem exibida numa TELA (o jeito de testar com fotos do Google): grade de subpixels, moire,
    brilho especular, tela azulada e leve borrao. p = fracao das imagens."""
    def __init__(self, p=0.3): self.p = p
    def __call__(self, im):
        import random as _r
        if _r.random() > self.p: return im
        from PIL import ImageFilter as _IF
        a = np.asarray(im).astype(np.float32); h, w = a.shape[:2]; yy, xx = np.mgrid[:h, :w]; per = _r.choice([2, 3, 4])
        grade = 1 - _r.uniform(0.08, 0.22) * (((xx % per) == 0) | ((yy % per) == 0)); moire = 1 + _r.uniform(0.02, 0.08) * np.sin(2 * np.pi * (xx * _r.uniform(0.03, 0.09) + yy * _r.uniform(0.03, 0.09)))
        brilho = 1 + _r.uniform(0.1, 0.45) * np.exp(-(((xx - _r.uniform(0.1, 0.9) * w) / (_r.uniform(0.2, 0.5) * w)) ** 2 + ((yy - _r.uniform(0.1, 0.9) * h) / (_r.uniform(0.2, 0.5) * h)) ** 2))
        a = a * (grade * moire * brilho)[..., None] * np.array([_r.uniform(0.95, 1.05), 1.0, _r.uniform(1.0, 1.3)]); a = np.clip(a * _r.uniform(0.75, 1.15) + _r.uniform(0, 25), 0, 255).astype(np.uint8)
        return Image.fromarray(a).filter(_IF.GaussianBlur(_r.uniform(0.4, 1.6)))
class Reamostra:
    """simula camera pior: reduz para 96-256 px e volta (borrao + serrilhado), com prob p"""
    def __init__(self, p=0.35): self.p = p
    def __call__(self, im):
        import random as _r
        if _r.random() > self.p: return im
        s = _r.randint(96, 256); w, h = im.size; return im.resize((s, int(s * h / w)), Image.BILINEAR).resize((w, h), Image.BILINEAR)
if AUG == "forte":
    train_tf = T.Compose([
        T.RandomResizedCrop(IMG_SIZE, scale=(0.35, 1.0), ratio=(0.75, 1.33)),
        T.RandomHorizontalFlip(), T.RandomRotation(18),
        T.RandomApply([T.ColorJitter(brightness=0.45, contrast=0.45, saturation=0.35, hue=0.03)], p=0.9),
        BorraoPIL(0.3),   # PIL, nao torch: T.GaussianBlur roda conv2d no worker forkado e trava (OpenMP apos fork)
        Reamostra(0.35),
        TelaPIL(float(os.environ.get("OCULAR_TELA_P", "0.0"))),   # OCULAR_TELA_P=0.3 liga a simulacao de tela
        T.RandomAutocontrast(p=0.2), T.RandomAdjustSharpness(2.0, p=0.2),
        T.ToTensor(), T.Normalize(MEAN, STD), T.RandomErasing(p=0.25, scale=(0.02, 0.12)),
    ])
else:
    train_tf = T.Compose([
        T.RandomResizedCrop(IMG_SIZE, scale=(0.45, 1.0), ratio=(0.8, 1.25)),   # v2.1: recortes menores/deslocados; lesao na borda (pterigio) aparece em mais posicoes
        T.RandomHorizontalFlip(),
        T.RandomRotation(12),
        T.ColorJitter(brightness=0.25, contrast=0.25),   # sem hue/saturation de proposito
        T.ToTensor(), T.Normalize(MEAN, STD),
    ])
print("aumento:", AUG)
eval_tf = T.Compose([T.Resize(int(IMG_SIZE * 1.1)), T.CenterCrop(IMG_SIZE), T.ToTensor(), T.Normalize(MEAN, STD)])

class EyeDS(Dataset):
    def __init__(self, d, tf):
        self.d, self.tf = d.reset_index(drop=True), tf
    def __len__(self):
        return len(self.d)
    def __getitem__(self, i):
        r = self.d.iloc[i]
        im = ImageOps.exif_transpose(Image.open(DATA_DIR / r["file"])).convert("RGB")
        y = torch.tensor(r[LABELS].to_numpy(dtype="float32")); k = torch.tensor(r[["k_" + l for l in LABELS]].to_numpy(dtype="float32"))
        return self.tf(im), y, k

NW = 2 if IN_COLAB else 0
if not IN_COLAB and sys.platform == "darwin" and "__file__" in globals():
    import torch.multiprocessing as _tmp
    _tmp.set_start_method("fork", force=True); NW = 4     # Mac, rodando como script: workers via fork
NW = int(os.environ.get("OCULAR_WORKERS", NW))   # 0 = sem workers (evita travar com transformadas que usam torch apos fork)
# Avaliacao com as mesmas vistas do app (TTA): recorte central, esquerdo e direito (ou superior e inferior) da imagem
# no zoom do treino, cada um com espelho; a probabilidade do rotulo e o MAXIMO entre as vistas. Os limiares sao
# escolhidos ja com isso, para o app e a avaliacao offline concordarem.
from PIL import Image as _PILImage
def load_img(f): return ImageOps.exif_transpose(Image.open(DATA_DIR / f)).convert("RGB")
eval_views_tf = T.Compose([T.ToTensor(), T.Normalize(MEAN, STD)])
def tta_views(img):
    w, h = img.size; side = int(round(min(w, h) * IMG_SIZE / (IMG_SIZE * 1.1)))
    boxes = [((w - side) // 2, (h - side) // 2)]
    if w > h: boxes += [(0, (h - side) // 2), (w - side, (h - side) // 2)]
    elif h > w: boxes += [((w - side) // 2, 0), ((w - side) // 2, h - side)]
    out = []
    for x0, y0 in boxes:
        c = img.crop((x0, y0, x0 + side, y0 + side)).resize((IMG_SIZE, IMG_SIZE), _PILImage.BILINEAR)
        out += [c, c.transpose(_PILImage.FLIP_LEFT_RIGHT)]
    return out

class EyeViewsDS(Dataset):
    def __init__(self, df): self.df = df.reset_index(drop=True)
    def __len__(self): return len(self.df)
    def __getitem__(self, i):
        r = self.df.iloc[i]; img = load_img(r["file"])
        vs = tta_views(img); x = torch.stack([eval_views_tf(v) for v in vs])
        while x.shape[0] < 6: x = torch.cat([x, x[-1:]])   # imagem quadrada: repete para empilhar
        return x, torch.tensor(r[LABELS].to_numpy(dtype="float32"))


BALANCE = os.environ.get("OCULAR_BALANCE_SOURCE") == "1"
if BALANCE:
    from torch.utils.data import WeightedRandomSampler
    cnt = train["source"].value_counts(); wsrc = train["source"].map(lambda s_: (len(train) / cnt[s_]) ** 0.5).to_numpy()
    sampler = WeightedRandomSampler(torch.tensor(wsrc, dtype=torch.double), num_samples=len(train), replacement=True)
    dl_train = DataLoader(EyeDS(train, train_tf), batch_size=BATCH, sampler=sampler, num_workers=NW); print("amostragem balanceada por fonte (raiz):", {k: round(float((len(train) / v) ** 0.5), 2) for k, v in cnt.items()})
else:
    dl_train = DataLoader(EyeDS(train, train_tf), batch_size=BATCH, shuffle=True, num_workers=NW)
dl_val   = DataLoader(EyeViewsDS(val), batch_size=BATCH // 2, num_workers=NW)
dl_test  = DataLoader(EyeViewsDS(test), batch_size=BATCH // 2, num_workers=NW)
x0, y0, k0 = next(iter(dl_train)); print("batch", tuple(x0.shape), tuple(y0.shape), "| rotulos conhecidos no lote", f"{float(k0.mean()):.2f}")

# %% ---------------------------------------------
import timm, torch.nn as nn
torch.manual_seed(SEED); np.random.seed(SEED)
model = timm.create_model(MODEL_NAME, pretrained=True, num_classes=len(LABELS), **({"img_size": IMG_SIZE} if "vit" in MODEL_NAME else {})).to(DEVICE)

pos = train[LABELS].sum().to_numpy().astype("float64")
neg = len(train) - pos
pos_weight = torch.tensor(np.clip(neg / np.maximum(pos, 1), 1, 20), dtype=torch.float32).to(DEVICE)
criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
criterion_none = nn.BCEWithLogitsLoss(pos_weight=pos_weight, reduction="none")
print("pos_weight:", dict(zip(LABELS, pos_weight.cpu().numpy().round(1))))

# %% ---------------------------------------------
from sklearn.metrics import roc_auc_score
import copy, time

@torch.no_grad()
def predict(dl):
    model.eval(); P, Y = [], []
    for x, y in dl:
        if x.dim() == 5:   # [B, V, C, H, W] -> max sobre as vistas
            B, V = x.shape[:2]
            p = torch.sigmoid(model(x.view(B * V, *x.shape[2:]).to(DEVICE))).float().cpu().view(B, V, -1).amax(1)
        else:
            p = torch.sigmoid(model(x.to(DEVICE))).float().cpu()
        P.append(p); Y.append(y)
    return torch.cat(P).numpy(), torch.cat(Y).numpy()

def macro_auc(P, Y):
    aucs = {}
    for j, l in enumerate(LABELS):
        if 0 < Y[:, j].sum() < len(Y):
            aucs[l] = float(roc_auc_score(Y[:, j], P[:, j]))
    return (float(np.mean(list(aucs.values()))) if aucs else float("nan")), aucs

best = {"auc": -1.0, "state": None}
AMP = (DEVICE == "cuda")

def run(epochs, lr, params):
    opt = torch.optim.AdamW(params, lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=epochs * len(dl_train))
    scaler = torch.amp.GradScaler("cuda", enabled=AMP)
    for ep in range(epochs):
        model.train(); t0 = time.time(); tot = 0.0
        for x, y, k in dl_train:
            x, y, k = x.to(DEVICE), y.to(DEVICE), k.to(DEVICE)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda" if AMP else "cpu", enabled=AMP):
                loss = (criterion_none(model(x), y) * k).sum() / k.sum().clamp(min=1.0)   # so os rotulos que a fonte conhece
            scaler.scale(loss).backward(); scaler.step(opt); scaler.update(); sched.step()
            tot += loss.item() * len(x)
        auc, _ = macro_auc(*predict(dl_val))
        if auc > best["auc"]:
            best["auc"], best["state"] = auc, copy.deepcopy(model.state_dict())
        print(f"ep {ep+1:2d}/{epochs} loss {tot/len(train):.4f} val_auc {auc:.3f} best {best['auc']:.3f} ({time.time()-t0:.0f}s)")

RESUME = os.environ.get("OCULAR_RESUME") == "1" and (OUT_DIR / f"{VERSION}.pt").exists()
if RESUME:   # so reavaliar/exportar um modelo ja treinado
    model.load_state_dict(torch.load(OUT_DIR / f"{VERSION}.pt", map_location=DEVICE))
    best["auc"], _ = macro_auc(*predict(dl_val))
    print("pesos carregados de", OUT_DIR / f"{VERSION}.pt", "| val_auc", round(best["auc"], 3))
else:
    # fase 1: congela o backbone, treina so a cabeca
    head_prefix = model.default_cfg.get("classifier", "classifier")
    for n, p in model.named_parameters():
        p.requires_grad = n.startswith(head_prefix)
    run(EPOCHS_HEAD, LR_HEAD, [p for p in model.parameters() if p.requires_grad])

    # fase 2: rede inteira
    for p in model.parameters():
        p.requires_grad = True
    run(EPOCHS_FULL, LR_FULL, model.parameters())

    model.load_state_dict(best["state"])
    torch.save(best["state"], OUT_DIR / f"{VERSION}.pt")
    print("melhor val_auc:", round(best["auc"], 3))

# %% ---------------------------------------------
from sklearn.metrics import roc_curve
Pv, Yv = predict(dl_val); Pt, Yt = predict(dl_test)

thr = {}
for j, l in enumerate(LABELS):
    npos = Yv[:, j].sum()
    if npos == 0 or npos == len(Yv):
        thr[l] = 0.5; continue
    fpr, tpr, t = roc_curve(Yv[:, j], Pv[:, j])
    ok = np.where(tpr >= TARGET_SENS)[0]
    # piso 0.08: com poucos positivos na validacao o limiar para sens 0.90 cai a quase zero e vira falso positivo em serie (icteria na v2)
    # teto 0.90: quando o modelo separa muito bem na validacao, o limiar para sens 0.90 sobe a 0.98 e fica fragil em caso real menos obvio
    thr[l] = float(np.clip(t[ok[0]] if len(ok) else 0.5, 0.08, 0.90))

_, auc_t = macro_auc(Pt, Yt)
rows = []
for j, l in enumerate(LABELS):
    y, p = Yt[:, j], (Pt[:, j] >= thr[l])
    tp = int(((y == 1) & p).sum()); fn = int(((y == 1) & ~p).sum())
    tn = int(((y == 0) & ~p).sum()); fp = int(((y == 0) & p).sum())
    rows.append({"sinal": l, "n_pos_teste": int(y.sum()), "auroc": round(auc_t.get(l, float("nan")), 3),
                 "limiar": round(thr[l], 3), "sensibilidade": round(tp / max(tp + fn, 1), 2),
                 "especificidade": round(tn / max(tn + fp, 1), 2), "confiavel": l not in few})
metrics = pd.DataFrame(rows); print(metrics.to_string(index=False))
# split e predicoes para a avaliacao offline reprodutivel (treino/avaliar.py) e para o harness no aparelho
for name, d in (("train", train), ("val", val), ("test", test)):
    d.assign(split=name).to_csv(OUT_DIR / f"split_{VERSION}_{name}.csv", index=False)
pd.DataFrame(Pt, columns=[f"p_{l}" for l in LABELS]).assign(file=test["file"].to_numpy()).to_csv(OUT_DIR / f"pred_{VERSION}_test.csv", index=False)

import json as _json
externos = {}
if holdout is not None and len(holdout): externos["loso_" + "_".join(EXCL)] = holdout
for name in EXTERNAL_CSVS:
    pth = DATA_DIR / name
    if not pth.exists(): continue
    de = pd.read_csv(pth)
    for l in LABELS:
        if l not in de.columns: de[l] = 0
    if "metade" in de.columns: de = de[de["metade"] == "B"]   # metade A pode ter virado treino (embrulho/colagem); B e teste para sempre
    de[LABELS] = de[LABELS].fillna(0).astype(int); de = de[de["file"].apply(lambda f: (DATA_DIR / f).exists())].reset_index(drop=True)
    if len(de): externos[pth.stem] = de
ext_res = {}
for name, de in externos.items():
    dl_h = DataLoader(EyeViewsDS(de), batch_size=BATCH // 2, num_workers=NW)
    Ph, Yh = predict(dl_h); print(f"\nTESTE EXTERNO {name} (n={len(de)}):"); ext_res[name] = {}
    for j, l in enumerate(LABELS):
        yh = Yh[:, j]
        if 0 < yh.sum() < len(yh):
            ph = Ph[:, j] >= thr[l]; tp = int(((yh == 1) & ph).sum()); fn = int(((yh == 1) & ~ph).sum()); tn = int(((yh == 0) & ~ph).sum()); fp = int(((yh == 0) & ph).sum())
            auc = roc_auc_score(yh, Ph[:, j]); ext_res[name][l] = dict(n=int(yh.sum()), auroc=round(float(auc), 3), sens=round(tp / max(tp + fn, 1), 3), esp=round(tn / max(tn + fp, 1), 3))
            print(f"  {l:26s} n_pos {int(yh.sum()):4d} auroc {auc:.3f} sens {tp/max(tp+fn,1):.2f} esp {tn/max(tn+fp,1):.2f} (limiar {thr[l]:.2f})")
    anyp = (Ph >= np.array([thr[l] for l in LABELS])).any(axis=1); haspos = Yh.sum(axis=1) > 0
    if haspos.any(): perd = float((~anyp & haspos).sum() / haspos.sum()); ext_res[name]["_positivos_perdidos"] = round(perd, 3); print(f"  positivos que sairiam 'sem sinais': {perd:.0%}")
    if (~haspos).any(): alar = float((anyp & ~haspos).sum() / (~haspos).sum()); ext_res[name]["_negativos_com_alarme"] = round(alar, 3); print(f"  negativos com algum alarme: {alar:.0%}")
    aucs = [v["auroc"] for k, v in ext_res[name].items() if not k.startswith("_")]
    if aucs: ext_res[name]["_auroc_medio"] = round(float(np.mean(aucs)), 3); print(f"  AUROC medio: {np.mean(aucs):.3f}")
_json.dump(ext_res, open(OUT_DIR / f"externo_{VERSION}.json", "w"), indent=1)

# desempenho por dominio de imagem (o que importa e o dominio do app: phone_closeup / web / external_camera)
print("\nAUROC por dominio (so onde ha positivos e negativos no teste):")
for dom, idx in test.groupby("domain").indices.items():
    _, a = macro_auc(Pt[idx], Yt[idx])
    if a: print(f"  {dom:16s} n={len(idx):4d}", {k: round(v, 2) for k, v in a.items()})

# %% ---------------------------------------------
import json, datetime, onnx, onnxruntime as ort
from onnxruntime.quantization import quantize_dynamic, QuantType

model.eval().to("cpu")

class WithCam(nn.Module):
    """Saida extra "cam": a cabeca do classificador aplicada em cada posicao do mapa de caracteristicas (10x10),
    como se aquela posicao fosse o vetor pooled. Mostra ONDE na foto cada rotulo foi visto. Custo ~zero."""
    def __init__(self, m): super().__init__(); self.m = m
    def forward(self, x):
        f = self.m.forward_features(x)                       # [B, C, H, W]
        logits = self.m.forward_head(f)                      # pool -> conv_head -> act -> classifier
        h = self.m.act2(self.m.conv_head(f))                 # conv 1x1 aplicada espacialmente: [B, 1280, H, W]
        w = self.m.classifier.weight; b = self.m.classifier.bias
        cam = torch.nn.functional.conv2d(h, w.view(w.shape[0], w.shape[1], 1, 1), b)   # classificador como conv 1x1: exporta limpo
        return logits, cam

wc = WithCam(model).eval()
dummy = torch.randn(1, 3, IMG_SIZE, IMG_SIZE)
onnx_path = OUT_DIR / f"{VERSION}.onnx"
try:
    torch.onnx.export(wc, dummy, str(onnx_path), input_names=["image"], output_names=["logits", "cam"], opset_version=17, dynamo=False)
except TypeError:   # torch antigo sem o argumento dynamo
    torch.onnx.export(wc, dummy, str(onnx_path), input_names=["image"], output_names=["logits", "cam"], opset_version=17)
onnx.checker.check_model(onnx.load(str(onnx_path)))

sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
with torch.no_grad():
    ref = model(dummy).numpy()
outs = sess.run(None, {"image": dummy.numpy()}); out = outs[0]
print("diferenca max torch vs onnx fp32:", float(np.abs(ref - out).max()), "| cam:", tuple(outs[1].shape))
CAM_SHAPE = [int(v) for v in outs[1].shape]

q_path = OUT_DIR / f"{VERSION}_int8.onnx"
quantize_dynamic(str(onnx_path), str(q_path), weight_type=QuantType.QInt8, per_channel=True)
sq = ort.InferenceSession(str(q_path), providers=["CPUExecutionProvider"])
# compara em imagens reais de validacao, nao em ruido: o que importa e a probabilidade final
xb, _ = next(iter(dl_val)); xb = xb[:8]
if xb.dim() == 5: xb = xb[:, 0]   # dl_val traz as vistas [B, V, C, H, W]; para a paridade int8 basta a vista central
with torch.no_grad(): p32 = torch.sigmoid(model(xb)).numpy()
p8 = np.concatenate([1 / (1 + np.exp(-sq.run(None, {"image": xb[i:i+1].numpy()})[0])) for i in range(len(xb))])  # batch fixo = 1; [0] = logits
int8_diff = float(np.abs(p32 - p8).max())
print("diferenca max de probabilidade fp32 vs int8 (8 imagens reais):", round(int8_diff, 4), "-> use o fp32 se > 0.05")
print("tamanhos MB: fp32", round(onnx_path.stat().st_size / 1e6, 1), "| int8", round(q_path.stat().st_size / 1e6, 1))

card = {
    "name": VERSION,
    "task": "multirrotulo de sinais no olho externo; triagem experimental, sem validacao clinica",
    "created": datetime.date.today().isoformat(),
    "backbone": MODEL_NAME,
    "input": {"name": "image", "shape": [1, 3, IMG_SIZE, IMG_SIZE], "layout": "NCHW", "color": "RGB",
              "preprocess": f"resize lado menor para {int(IMG_SIZE*1.1)}, center crop {IMG_SIZE}, /255, normalizar",
              "mean": MEAN, "std": STD},
    "output": {"name": "logits", "activation": "sigmoid", "labels": LABELS},
    "explain": {"name": "cam", "shape": CAM_SHAPE, "note": "logit local por posicao (cabeca aplicada a cada celula do mapa 10x10); softmax espacial nao se aplica, compare celulas pelo valor"},
    "files": {"fp32": onnx_path.name, "int8": q_path.name, "int8_max_prob_diff": round(int8_diff, 4),
              "recommended": q_path.name if int8_diff <= 0.05 else onnx_path.name},
    "thresholds": thr, "target_sensitivity": TARGET_SENS,
    "unreliable_labels": few,
    "counts": {"train": int(len(train)), "val": int(len(val)), "test": int(len(test)),
               "train_positives": {l: int(train[l].sum()) for l in LABELS}},
    "test_metrics": rows,
    "sources": sorted(df["source"].astype(str).unique().tolist()),
    "license_note": "conferir a licenca de cada fonte antes de qualquer uso alem de pesquisa/competicao",
}
# corrida de teste externo (OCULAR_EXCLUDE_SOURCES) nao substitui o cartao de producao: vai para <versao>_card.json
(OUT_DIR / (f"{VERSION}_card.json" if (EXCL or TAG) else "model_card.json")).write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
print("salvo em", OUT_DIR, "->", sorted(p.name for p in OUT_DIR.iterdir()))
