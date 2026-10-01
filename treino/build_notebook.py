import json, sys
from pathlib import Path

cells = []
def md(s): cells.append({"cell_type": "markdown", "metadata": {}, "source": s.strip("\n")})
def code(s): cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s.strip("\n")})

md('''
# Guaraná, treino do classificador local (v1)

Treina um classificador **multirrótulo** de sinais no olho externo (foto comum, sem lente) e exporta para **ONNX** para rodar offline no tablet Android com ONNX Runtime.

**Entrada esperada** em `DATA_DIR`:

- `labels.csv` com as colunas `file, subject_id, source` e uma coluna 0/1 por sinal (veja `dados/labels.exemplo.csv`).
- As imagens nos caminhos relativos indicados em `file`.

**Regras que este notebook aplica e que não devem ser removidas:**

1. Divisão treino/validação/teste **por pessoa** (`subject_id`), nunca por foto. Fotos da mesma pessoa em conjuntos diferentes inflam a métrica.
2. Sem *hue/saturation jitter* nas augmentations: cor é o sinal clínico (icterícia, esclera azul, hiperemia).
3. Limiar por sinal escolhido na validação para **sensibilidade alvo** (triagem prefere falso positivo a falso negativo).
4. Sinais com menos de `MIN_POS` positivos no treino são marcados como não confiáveis no `model_card.json`.

Custo: roda na GPU gratuita do Colab (T4) em minutos, ou no Mac com Apple Silicon (`DEVICE = mps`).
''')

code('''
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
''')

code('''
from pathlib import Path
_BASE = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path("..").resolve()
DATA_DIR = Path("/content/drive/MyDrive/guarana/dados") if IN_COLAB else _BASE / "dados"
OUT_DIR  = Path("/content/drive/MyDrive/guarana/saida") if IN_COLAB else _BASE / "saida"
OUT_DIR.mkdir(parents=True, exist_ok=True)
SMOKE = os.environ.get("OCULAR_SMOKE") == "1"     # teste rapido do pipeline: poucas imagens, 1 epoca

# Sinais treinaveis na v1. Os demais do PDF (arco, esclera azul, Bitot, ocronose, telangiectasia)
# ficam no CSV para coleta, mas so entram aqui quando houver >= MIN_POS exemplos.
LABELS = ["hiperemia", "ictericia", "pterigio_pinguecula", "catarata_leucocoria",
          "hemorragia_subconjuntival", "lesao_pigmentada", "opacidade_corneana"]
# palidez_conjuntival fica fora do CNN: os dados publicos (CP-AnemiC) sao recortes de conjuntiva em fundo branco,
# outro dominio; entra pela regra de cor calibrada nesses recortes.

MODEL_NAME  = "mobilenetv3_large_100"   # ~5.5M params, ~22 MB fp32, ~6 MB int8
IMG_SIZE    = 320
BATCH       = 32
EPOCHS_HEAD = int(os.environ.get("OCULAR_EPOCHS_HEAD", 3))    # fase 1: so a cabeca
EPOCHS_FULL = int(os.environ.get("OCULAR_EPOCHS_FULL", 15))   # fase 2: rede inteira
if SMOKE: EPOCHS_HEAD, EPOCHS_FULL = 1, 1
LR_HEAD, LR_FULL = 1e-3, 2e-4
SEED        = 42
TARGET_SENS = 0.90   # sensibilidade alvo para escolher o limiar de cada sinal
MIN_POS     = 15     # minimo de positivos no treino para considerar o sinal confiavel
VERSION     = "ocular_v1"
''')

md('''
## Dados

Se você tiver datasets em pastas por classe, use `rows_from_folders` para gerar linhas e concatenar ao `labels.csv`. O `subject_id` de datasets públicos sem identificação de pessoa vira o nome do arquivo, o que é o melhor possível.
''')

code('''
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

csvs = sorted(DATA_DIR.glob("labels*.csv"))
csvs = [c for c in csvs if "exemplo" not in c.name]
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
print(len(df), "imagens |", int((df[LABELS].sum(axis=1) == 0).sum()), "negativas")
print(df.groupby("source")[LABELS].sum().assign(n=df.groupby("source").size()).to_string())
print(df[LABELS].sum().to_string())
''')

code('''
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
    print("\\nAVISO: poucos positivos no treino para", few, "-> marcados como nao confiaveis no model_card")
''')

md('''
## Dataset e augmentations
''')

code('''
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as T

MEAN, STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
train_tf = T.Compose([
    T.RandomResizedCrop(IMG_SIZE, scale=(0.6, 1.0), ratio=(0.85, 1.18)),
    T.RandomHorizontalFlip(),
    T.RandomRotation(12),
    T.ColorJitter(brightness=0.25, contrast=0.25),   # sem hue/saturation de proposito
    T.ToTensor(), T.Normalize(MEAN, STD),
])
eval_tf = T.Compose([T.Resize(int(IMG_SIZE * 1.1)), T.CenterCrop(IMG_SIZE), T.ToTensor(), T.Normalize(MEAN, STD)])

class EyeDS(Dataset):
    def __init__(self, d, tf):
        self.d, self.tf = d.reset_index(drop=True), tf
    def __len__(self):
        return len(self.d)
    def __getitem__(self, i):
        r = self.d.iloc[i]
        im = ImageOps.exif_transpose(Image.open(DATA_DIR / r["file"])).convert("RGB")
        y = torch.tensor(r[LABELS].to_numpy(dtype="float32"))
        return self.tf(im), y

NW = 2 if IN_COLAB else 0
if not IN_COLAB and sys.platform == "darwin" and "__file__" in globals():
    import torch.multiprocessing as _tmp
    _tmp.set_start_method("fork", force=True); NW = 4     # Mac, rodando como script: workers via fork
dl_train = DataLoader(EyeDS(train, train_tf), batch_size=BATCH, shuffle=True, num_workers=NW)
dl_val   = DataLoader(EyeDS(val, eval_tf), batch_size=BATCH, num_workers=NW)
dl_test  = DataLoader(EyeDS(test, eval_tf), batch_size=BATCH, num_workers=NW)
x0, y0 = next(iter(dl_train)); print("batch", tuple(x0.shape), tuple(y0.shape))
''')

md('''
## Modelo e treino (duas fases)
''')

code('''
import timm, torch.nn as nn
torch.manual_seed(SEED); np.random.seed(SEED)
model = timm.create_model(MODEL_NAME, pretrained=True, num_classes=len(LABELS)).to(DEVICE)

pos = train[LABELS].sum().to_numpy().astype("float64")
neg = len(train) - pos
pos_weight = torch.tensor(np.clip(neg / np.maximum(pos, 1), 1, 20), dtype=torch.float32).to(DEVICE)
criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
print("pos_weight:", dict(zip(LABELS, pos_weight.cpu().numpy().round(1))))
''')

code('''
from sklearn.metrics import roc_auc_score
import copy, time

@torch.no_grad()
def predict(dl):
    model.eval(); P, Y = [], []
    for x, y in dl:
        P.append(torch.sigmoid(model(x.to(DEVICE))).float().cpu()); Y.append(y)
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
        for x, y in dl_train:
            x, y = x.to(DEVICE), y.to(DEVICE)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda" if AMP else "cpu", enabled=AMP):
                loss = criterion(model(x), y)
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
''')

md('''
## Limiares por sinal e avaliação no teste

O limiar de cada sinal é escolhido na **validação** para atingir `TARGET_SENS`. Os números do teste abaixo são o que vale. Com poucos positivos, o intervalo de confiança é largo: apresente como "desempenho preliminar em conjunto pequeno", nunca como acurácia clínica.
''')

code('''
from sklearn.metrics import roc_curve
Pv, Yv = predict(dl_val); Pt, Yt = predict(dl_test)

thr = {}
for j, l in enumerate(LABELS):
    npos = Yv[:, j].sum()
    if npos == 0 or npos == len(Yv):
        thr[l] = 0.5; continue
    fpr, tpr, t = roc_curve(Yv[:, j], Pv[:, j])
    ok = np.where(tpr >= TARGET_SENS)[0]
    thr[l] = float(np.clip(t[ok[0]] if len(ok) else 0.5, 0.02, 0.98))

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

# desempenho por dominio de imagem (o que importa e o dominio do app: phone_closeup / web / external_camera)
print("\\nAUROC por dominio (so onde ha positivos e negativos no teste):")
for dom, idx in test.groupby("domain").indices.items():
    _, a = macro_auc(Pt[idx], Yt[idx])
    if a: print(f"  {dom:16s} n={len(idx):4d}", {k: round(v, 2) for k, v in a.items()})
''')

md('''
## Exportar para o tablet: ONNX + model card

O `model_card.json` é o "pacote do modelo": o app deve ler tamanho de entrada, normalização, rótulos e limiares **daqui**, nunca de constantes duplicadas no Kotlin.
''')

code('''
import json, datetime, onnx, onnxruntime as ort
from onnxruntime.quantization import quantize_dynamic, QuantType

model.eval().to("cpu")
dummy = torch.randn(1, 3, IMG_SIZE, IMG_SIZE)
onnx_path = OUT_DIR / f"{VERSION}.onnx"
try:
    torch.onnx.export(model, dummy, str(onnx_path), input_names=["image"], output_names=["logits"], opset_version=17, dynamo=False)
except TypeError:   # torch antigo sem o argumento dynamo
    torch.onnx.export(model, dummy, str(onnx_path), input_names=["image"], output_names=["logits"], opset_version=17)
onnx.checker.check_model(onnx.load(str(onnx_path)))

sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
with torch.no_grad():
    ref = model(dummy).numpy()
out = sess.run(None, {"image": dummy.numpy()})[0]
print("diferenca max torch vs onnx fp32:", float(np.abs(ref - out).max()))

q_path = OUT_DIR / f"{VERSION}_int8.onnx"
quantize_dynamic(str(onnx_path), str(q_path), weight_type=QuantType.QInt8, per_channel=True)
sq = ort.InferenceSession(str(q_path), providers=["CPUExecutionProvider"])
# compara em imagens reais de validacao, nao em ruido: o que importa e a probabilidade final
xb, _ = next(iter(dl_val)); xb = xb[:8]
with torch.no_grad(): p32 = torch.sigmoid(model(xb)).numpy()
p8 = np.concatenate([1 / (1 + np.exp(-sq.run(None, {"image": xb[i:i+1].numpy()})[0])) for i in range(len(xb))])  # batch fixo = 1
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
(OUT_DIR / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
print("salvo em", OUT_DIR, "->", sorted(p.name for p in OUT_DIR.iterdir()))
''')

md('''
## Próximo passo: integrar no app

Copie `ocular_v1_int8.onnx` (ou o fp32 se a diferença acima for grande) e `model_card.json` para `app/src/main/assets/`. No Kotlin, use `com.microsoft.onnxruntime:onnxruntime-android`, aplique exatamente o pré-processamento do card, aplique sigmoid nos logits e compare com `thresholds`. A saída deve ser montada no contrato `contrato/resultado.schema.json` com `engine = "local-model"` e `status = "provisional"`.
''')

nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
      "language_info": {"name": "python"}, "colab": {"provenance": []}, "accelerator": "GPU"},
      "nbformat": 4, "nbformat_minor": 5}
out = Path(__file__).with_name("ocular_treino.ipynb")
out.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
# versao script para rodar local (Mac/MPS): mesmas celulas, em ordem
script = "# GERADO por build_notebook.py a partir das celulas do notebook. Edite build_notebook.py.\n" + \
         "\n\n# %% ---------------------------------------------\n".join(c["source"] for c in cells if c["cell_type"] == "code") + "\n"
Path(__file__).with_name("treinar.py").write_text(script, encoding="utf-8")
# checagem de sintaxe de cada celula de codigo
for i, c in enumerate(cells):
    if c["cell_type"] == "code":
        compile(c["source"], f"cell{i}", "exec")
print("ok:", out.name, len(cells), "celulas")
