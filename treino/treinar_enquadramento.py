"""Detector de enquadramento do olho (gate da captura), treinado por sintese a partir de geometria anotada:
- SLID: circulo da pupila/cornea (iris) em ~1.400 fotos de lampada de fenda;
- CFD (periorbital): caixas de iris dos dois olhos em 300 faixas de rosto, dominio parecido com foto de celular.
Para cada imagem geramos janelas com a iris num tamanho/posicao que define a classe:
  OK (iris 14-55% do lado, centralizada), TOO_FAR (<9%), TOO_CLOSE (>62%), OFF_CENTER (perto da borda),
  TWO_EYES (faixa com os dois olhos), NOT_FOUND (janela sem iris: pele, sobrancelha, ruido).
Sai um MobileNetV3-small de 160 px em escala de cinza (o app usa o canal Y do preview) exportado em ONNX,
com cartao (classes, normalizacao) e uma avaliacao em imagens separadas por sujeito.
"""
import os, json, csv, random, math, datetime
from pathlib import Path
import numpy as np, torch, torch.nn as nn, timm
import torch.multiprocessing as _tmp
_tmp.set_start_method("fork", force=True)   # macOS: workers do DataLoader sem reimportar o modulo
from PIL import Image, ImageOps, ImageFilter
Image.MAX_IMAGE_PIXELS = None   # alguns PNG do SLID sao enormes; filtramos por tamanho de arquivo abaixo
from torch.utils.data import Dataset, DataLoader

BASE = Path(__file__).resolve().parents[1]; RAW = BASE / "dados/raw"; OUT = BASE / "saida"
CLASSES = ["OK", "TOO_FAR", "TOO_CLOSE", "TWO_EYES", "OFF_CENTER", "NOT_FOUND"]
SIZE = 160; SEED = 7; EPOCHS = int(os.environ.get("ENQ_EPOCHS", 8)); PER_EPOCH = int(os.environ.get("ENQ_PER_EPOCH", 4000))
DEVICE = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)

# ---------------- geometria anotada ----------------
def _cache_one(j):
    fn, src, dst = j
    if dst.exists(): return fn, dst
    try:
        im = Image.open(src).convert("RGB"); sc = min(1.0, 900 / max(im.size))
        if sc < 1: im = im.resize((round(im.width * sc), round(im.height * sc)), Image.BILINEAR)
        im.save(dst, "JPEG", quality=92); return fn, dst
    except Exception: return fn, None

def slid_items():
    rows = list(csv.DictReader(open(RAW / "slid/Annotations.csv", encoding="utf-8-sig")))
    by = {}
    for r in rows:
        a = json.loads(r["attributes"]) if r["attributes"].startswith("{") else {}
        s = json.loads(r["shape_coordinates"]) if r["shape_coordinates"].startswith("{") else {}
        if s.get("name") == "circle" and a.get("region") in ("Pupil", "Cornea"):
            by.setdefault(r["filename"], {})[a["region"]] = (s["cx"], s["cy"], s["r"])
    pngs = {p.name: p for p in (RAW / "slid/extract").rglob("*.png")}
    ratios = [v["Cornea"][2] / v["Pupil"][2] for v in by.values() if "Cornea" in v and "Pupil" in v and v["Pupil"][2] > 0]
    ratio = float(np.median(ratios)) if ratios else 2.5
    # cache: PNG grandes (ate 5 MP) viram JPEG com lado maior 900 px, com as coordenadas escaladas; sintese fica 10x mais rapida
    cache = BASE / "dados/cache_enq/slid"; cache.mkdir(parents=True, exist_ok=True)
    jobs = []
    for fn, v in by.items():
        if fn not in pngs or pngs[fn].stat().st_size > 25_000_000: continue   # pula arquivos gigantes
        jobs.append((fn, pngs[fn], cache / (Path(fn).stem + ".jpg")))
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(6) as ex: cached = dict(ex.map(_cache_one, jobs, chunksize=8))
    items = []
    for fn, v in by.items():
        dst = cached.get(fn)
        if not dst: continue
        with Image.open(pngs[fn]) as im0: sc = min(1.0, 900 / max(im0.size))
        if "Cornea" in v: cx, cy, r = v["Cornea"]
        else: cx, cy, r = v["Pupil"]; r = r * ratio
        items.append({"path": dst, "irises": [(cx * sc, cy * sc, r * sc)], "subject": "slid_" + fn, "domain": "slit_lamp"})
    print(f"SLID: {len(items)} imagens (razao cornea/pupila {ratio:.2f})")
    return items

def cfd_items():
    base = RAW / "periorbital/extract/periorbital_dataset"
    imgs = {p.name: p for p in base.rglob("*.jpg")}
    items = []
    for j in sorted((base / "coco_annotations/cfd_annotations_coco").glob("*.json")):
        d = json.load(open(j)); cats = {c["id"]: c["name"] for c in d["categories"]}
        anns = {}
        for a in d["annotations"]: anns.setdefault(a["image_id"], {})[cats[a["category_id"]]] = a["bbox"]
        for im in d["images"]:
            if im["file_name"] not in imgs: continue
            a = anns.get(im["id"], {}); ir = []
            for k in ("l_iris", "r_iris"):
                if k in a: x, y, w, h = a[k]; ir.append((x + w / 2, y + h / 2, max(w, h) / 2))
            if len(ir) == 2: items.append({"path": imgs[im["file_name"]], "irises": ir, "subject": "cfd_" + im["file_name"].split("-")[2] if "-" in im["file_name"] else im["file_name"], "domain": "face_camera"})
    print(f"CFD: {len(items)} faixas com as duas iris")
    return items

# ---------------- sintese de janelas ----------------
def window(img, cx, cy, side, angle=0.0):
    """Quadrado de lado `side` centrado em (cx, cy), ja reamostrado para SIZE. Fora da imagem, preenche por reflexao
    simetrica (parece pele/fundo continuando), calculado numa copia reduzida: barato mesmo com janelas enormes."""
    sc = SIZE / side
    small = img.resize((max(1, int(round(img.width * sc))), max(1, int(round(img.height * sc)))), Image.BILINEAR)
    arr = np.asarray(small)
    if arr.ndim == 2: arr = arr[..., None].repeat(3, 2)
    x0 = int(round((cx - side / 2) * sc)); y0 = int(round((cy - side / 2) * sc))
    padL = max(0, -x0); padT = max(0, -y0); padR = max(0, x0 + SIZE - arr.shape[1]); padB = max(0, y0 + SIZE - arr.shape[0])
    if padL or padT or padR or padB:
        arr = np.pad(arr, ((padT, padB), (padL, padR), (0, 0)), mode="symmetric"); x0 += padL; y0 += padT
    w = Image.fromarray(np.ascontiguousarray(arr[y0:y0 + SIZE, x0:x0 + SIZE]))
    if w.size != (SIZE, SIZE): w = w.resize((SIZE, SIZE), Image.BILINEAR)
    if angle: w = w.rotate(angle, resample=Image.BILINEAR, fillcolor=(128, 128, 128))
    return w

def synth(item, cls, rng):
    img = Image.open(item["path"]).convert("RGB")
    ir = item["irises"]; (cx, cy, r) = ir[rng.integers(len(ir))]
    ang = float(rng.uniform(-15, 15))
    if cls == "OK":
        d = rng.uniform(0.14, 0.55); side = 2 * r / d; off = rng.uniform(-0.18, 0.18, 2) * side
        return window(img, cx + off[0], cy + off[1], side, ang)
    if cls == "TOO_FAR":
        d = rng.uniform(0.04, 0.09); side = 2 * r / d; off = rng.uniform(-0.25, 0.25, 2) * side
        return window(img, cx + off[0], cy + off[1], side, ang)
    if cls == "TOO_CLOSE":
        d = rng.uniform(0.62, 0.95); side = 2 * r / d; off = rng.uniform(-0.12, 0.12, 2) * side
        return window(img, cx + off[0], cy + off[1], side, ang)
    if cls == "OFF_CENTER":
        d = rng.uniform(0.14, 0.5); side = 2 * r / d
        ox = rng.choice([-1, 1]) * rng.uniform(0.32, 0.46) * side; oy = rng.uniform(-0.2, 0.2) * side
        if rng.random() < 0.4: ox, oy = oy, rng.choice([-1, 1]) * rng.uniform(0.32, 0.46) * side
        return window(img, cx + ox, cy + oy, side, ang)
    if cls == "TWO_EYES":
        if len(ir) < 2:   # SLID: monta dois olhos lado a lado a partir de dois recortes OK
            d = rng.uniform(0.28, 0.5); side = 2 * r / d
            a = window(img, cx, cy, side, 0); b = ImageOps.mirror(a)
            out = Image.new("RGB", (2 * SIZE, SIZE)); out.paste(a, (0, 0)); out.paste(b, (SIZE, 0))
            return out.resize((SIZE, SIZE), Image.BILINEAR)
        (x1, y1, r1), (x2, y2, r2) = ir
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2; dist = abs(x2 - x1)
        side = dist * rng.uniform(1.4, 2.6); off = rng.uniform(-0.1, 0.1, 2) * side
        return window(img, mx + off[0], my + off[1], side, ang)
    # NOT_FOUND: janela longe de qualquer iris, ou ruido/gradiente
    p = rng.random()
    if p < 0.15:
        arr = (rng.uniform(0, 255, (SIZE, SIZE, 3)) if rng.random() < 0.5 else np.tile(np.linspace(0, 255, SIZE), (SIZE, 1))[..., None].repeat(3, 2)).astype(np.uint8)
        return Image.fromarray(arr)
    for _ in range(30):
        side = rng.uniform(0.6, 2.5) * 2 * r
        wx = rng.uniform(0, img.width); wy = rng.uniform(0, img.height)
        if all(math.hypot(wx - ix, wy - iy) > (iw + side / 2) * 1.05 for ix, iy, iw in ir):
            return window(img, wx, wy, side, ang)
    return window(img, cx + 3 * r + side / 2, cy, side, ang)   # ao lado do olho, fora da iris

class Synth(Dataset):
    def __init__(self, items, n, seed):
        self.items, self.n, self.seed = items, n, seed
    def __len__(self): return self.n
    def __getitem__(self, i):
        rng = np.random.default_rng(self.seed * 100003 + i)
        cls = CLASSES[rng.integers(len(CLASSES))]
        im = None
        for _ in range(5):   # imagem corrompida/gigante: tenta outra
            item = self.items[rng.integers(len(self.items))]
            try: im = synth(item, cls, rng).convert("L"); break
            except Exception: continue
        if im is None: im = Image.fromarray(rng.uniform(0, 255, (SIZE, SIZE)).astype(np.uint8)); cls = "NOT_FOUND"
        # fotometria: contraste/brilho/ruido/desfoque leves; o app manda luminancia do preview
        arr = np.asarray(im, dtype=np.float32)
        arr = (arr - 128) * rng.uniform(0.7, 1.3) + 128 + rng.uniform(-30, 30)
        if rng.random() < 0.3: arr = arr + rng.normal(0, 6, arr.shape)
        im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        if rng.random() < 0.25: im = im.filter(ImageFilter.GaussianBlur(rng.uniform(0.5, 2.0)))
        if rng.random() < 0.5: im = ImageOps.mirror(im)
        x = torch.from_numpy(np.asarray(im, dtype=np.float32) / 255.0)[None].repeat(3, 1, 1)
        x = (x - 0.45) / 0.25
        return x, CLASSES.index(cls)

def split(items, frac=0.15):
    subs = sorted({it["subject"] for it in items}); rng = random.Random(SEED); rng.shuffle(subs)
    val = set(subs[: int(len(subs) * frac)])
    return [it for it in items if it["subject"] not in val], [it for it in items if it["subject"] in val]

items = slid_items() + cfd_items()
train_items, val_items = split(items)
print(f"treino {len(train_items)} imagens | validacao {len(val_items)} imagens (por sujeito)")
dl_train = DataLoader(Synth(train_items, PER_EPOCH, 1), batch_size=64, shuffle=True, num_workers=4)
dl_val = DataLoader(Synth(val_items, 1200, 999), batch_size=64, num_workers=4)

model = timm.create_model("mobilenetv3_small_100", pretrained=True, num_classes=len(CLASSES)).to(DEVICE)
opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=1e-3, total_steps=EPOCHS * len(dl_train))
crit = nn.CrossEntropyLoss(label_smoothing=0.05)

@torch.no_grad()
def evaluate(dl):
    model.eval(); P, Y = [], []
    for x, y in dl: P.append(model(x.to(DEVICE)).argmax(1).cpu()); Y.append(y)
    P, Y = torch.cat(P).numpy(), torch.cat(Y).numpy()
    conf = np.zeros((len(CLASSES), len(CLASSES)), int)
    for p, y in zip(P, Y): conf[y, p] += 1
    return float((P == Y).mean()), conf

best = (0.0, None)
for ep in range(EPOCHS):
    model.train(); tot = 0.0; t0 = datetime.datetime.now()
    for x, y in dl_train:
        x, y = x.to(DEVICE), y.to(DEVICE)
        opt.zero_grad(); loss = crit(model(x), y); loss.backward(); opt.step(); sched.step(); tot += loss.item() * len(x)
    acc, conf = evaluate(dl_val)
    if acc > best[0]: best = (acc, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()})
    print(f"ep {ep+1}/{EPOCHS} loss {tot/PER_EPOCH:.3f} val_acc {acc:.3f} ({(datetime.datetime.now()-t0).seconds}s)", flush=True)
model.load_state_dict(best[1]); model.eval()
acc, conf = evaluate(dl_val)
print("melhor val_acc", round(acc, 3)); print("confusao (linha = verdadeiro, coluna = previsto):", CLASSES)
for i, c in enumerate(CLASSES): print(f"  {c:11s}", conf[i].tolist(), f"recall {conf[i, i] / max(conf[i].sum(), 1):.2f}")
torch.save(best[1], OUT / "enquadramento_v1.pt")

# ---------------- avaliacao em recortes reais (sem sintese): distribuicao de decisoes por fonte ----------------
@torch.no_grad()
def predict_file(p):
    im = Image.open(p).convert("L"); s = min(im.size); im = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width - s) // 2 + s, (im.height - s) // 2 + s)).resize((SIZE, SIZE), Image.BILINEAR)
    x = ((torch.from_numpy(np.asarray(im, dtype=np.float32) / 255.0)[None].repeat(3, 1, 1) - 0.45) / 0.25)[None].to(DEVICE)
    return CLASSES[int(model(x).argmax(1))]
crops = BASE / "dados/crops"; natural = {}
for src in ["slid", "cfd", "hf_jaundice", "conj_seg", "eye_diseases"]:
    files = sorted((crops / src).glob("*.jpg"))[:200]
    if not files: continue
    c = {}
    for f in files: k = predict_file(f); c[k] = c.get(k, 0) + 1
    natural[src] = {k: round(v / len(files), 2) for k, v in sorted(c.items(), key=lambda kv: -kv[1])}
    print(f"  {src:13s} n={len(files)}", natural[src])

# ---------------- export ----------------
model.to("cpu"); dummy = torch.randn(1, 3, SIZE, SIZE)
onnx_path = OUT / "enquadramento_v1.onnx"
try: torch.onnx.export(model, dummy, str(onnx_path), input_names=["image"], output_names=["logits"], opset_version=17, dynamo=False)
except TypeError: torch.onnx.export(model, dummy, str(onnx_path), input_names=["image"], output_names=["logits"], opset_version=17)
import onnxruntime as ort
sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
print("onnx ok, diff", float(np.abs(sess.run(None, {"image": dummy.numpy()})[0] - model(dummy).detach().numpy()).max()), "| MB", round(onnx_path.stat().st_size / 1e6, 1))
card = {"name": "enquadramento_v1", "file": onnx_path.name, "created": datetime.date.today().isoformat(),
        "input": {"size": SIZE, "gray": True, "crop": "quadrado central", "mean": 0.45, "std": 0.25, "note": "canal de luminancia replicado em 3 canais"},
        "classes": CLASSES, "val_accuracy": round(acc, 3), "confusion": conf.tolist(), "natural_sets": natural,
        "train_images": len(train_items), "val_images": len(val_items), "sources": ["slid (circulos de pupila/cornea)", "cfd periorbital (caixas de iris)"]}
(OUT / "enquadramento_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False))
print("salvo", onnx_path.name, "e enquadramento_card.json")
