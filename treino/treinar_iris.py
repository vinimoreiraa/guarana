"""Localizador de iris: regressao (cx, cy, r) normalizados numa janela quadrada em torno do olho. Treina com as mesmas
anotacoes do gate de enquadramento (SLID circulos, CFD caixas) mais, se existirem, as mascaras sinteticas do MPFB
(canal G = iris). Serve para alinhar fotos reais na geometria (sintese/embrulhar.py) e para colar lesoes.
Uso: .venv/bin/python treino/treinar_iris.py   -> saida/iris_v1.onnx + iris_card.json
"""
import os, json, math, random, glob, datetime
from pathlib import Path
import numpy as np, torch, torch.nn as nn, timm
from PIL import Image, ImageOps
from torch.utils.data import Dataset, DataLoader
BASE = Path(__file__).resolve().parents[1]; RAW = BASE / "dados/raw"; OUT = BASE / "saida"
SIZE = 224; EPOCHS = int(os.environ.get("IRIS_EPOCHS", 10)); PER_EPOCH = int(os.environ.get("IRIS_PER_EPOCH", 3000)); DEV = "mps" if torch.backends.mps.is_available() else "cpu"
MEAN, STD = np.array([0.485, 0.456, 0.406], np.float32), np.array([0.229, 0.224, 0.225], np.float32)
# reaproveita os carregadores do gate (o modulo treina ao importar; executa so a parte dos carregadores)
src = (BASE / "treino/treinar_enquadramento.py").read_text(); ns = {"__name__": "carregadores", "__file__": str(BASE / "treino/treinar_enquadramento.py")}
src = src.replace("with ProcessPoolExecutor(6) as ex: cached = dict(ex.map(_cache_one, jobs, chunksize=8))", "cached = dict(map(_cache_one, jobs))")   # cache ja existe; sem pool (funcao nao e picklable aqui)
exec(src[:src.index("# ---------------- sintese de janelas")], ns)
def mpfb_items():
    items = []
    for m in glob.glob(str(BASE / "sintese/render/mpfb*/**/*_mask.png"), recursive=True):
        img = m.replace("_mask.png", ".jpg")
        if not os.path.exists(img): continue
        a = np.asarray(Image.open(m).convert("RGB")); g = a[:, :, 1] > 128
        if g.sum() < 200: continue
        ys, xs = np.nonzero(g); cx, cy = xs.mean(), ys.mean(); r = math.sqrt(g.sum() / math.pi)
        # iris parcialmente coberta pela palpebra: raio pela largura horizontal (mais robusto)
        r = max(r, (xs.max() - xs.min()) / 2)
        items.append({"path": Path(img), "irises": [(cx, cy, r)], "subject": "mpfb", "domain": "synthetic"})
    print(f"MPFB: {len(items)} imagens com mascara de iris"); return items

class IrisDS(Dataset):
    def __init__(self, items, n, seed): self.items, self.n, self.rng = items, n, random.Random(seed)
    def __len__(self): return self.n
    def __getitem__(self, i):
        it = self.rng.choice(self.items); cx, cy, r = self.rng.choice(it["irises"])
        img = ImageOps.exif_transpose(Image.open(it["path"])).convert("RGB")
        # janela: iris ocupa 15-70% do lado, centro deslocado ate 35% do lado
        side = 2 * r / self.rng.uniform(0.15, 0.70); ox, oy = self.rng.uniform(-0.35, 0.35) * side, self.rng.uniform(-0.35, 0.35) * side
        x0, y0 = cx + ox - side / 2, cy + oy - side / 2
        crop = img.crop((int(x0), int(y0), int(x0 + side), int(y0 + side))).resize((SIZE, SIZE), Image.BILINEAR)
        if self.rng.random() < 0.5: crop = ImageOps.mirror(crop); cxn = 1 - (cx - x0) / side
        else: cxn = (cx - x0) / side
        cyn = (cy - y0) / side; rn = r / side
        a = np.asarray(crop, np.float32) / 255
        # cor/exposicao/borrao leves
        a = np.clip(a * self.rng.uniform(0.6, 1.4) + self.rng.uniform(-0.1, 0.1), 0, 1)
        x = torch.tensor(((a - MEAN) / STD).transpose(2, 0, 1)); y = torch.tensor([cxn, cyn, rn], dtype=torch.float32)
        return x, y

def main():
    items = ns["slid_items"]() + ns["cfd_items"]() + mpfb_items()
    rng = random.Random(0); rng.shuffle(items); n_val = max(50, len(items) // 10); val, train = items[:n_val], items[n_val:]
    print("treino", len(train), "val", len(val), "| dominios", {d: sum(1 for i in items if i["domain"] == d) for d in set(i["domain"] for i in items)})
    torch.multiprocessing.set_start_method("fork", force=True)
    dl = DataLoader(IrisDS(train, PER_EPOCH, 1), batch_size=48, num_workers=4); dv = DataLoader(IrisDS(val, 600, 2), batch_size=48, num_workers=2)
    m = timm.create_model("mobilenetv3_small_100", pretrained=True, num_classes=3).to(DEV); opt = torch.optim.AdamW(m.parameters(), 1e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 2e-3, total_steps=EPOCHS * math.ceil(PER_EPOCH / 48)); best = (9, None)
    for ep in range(EPOCHS):
        m.train(); tl = 0
        for x, y in dl:
            x, y = x.to(DEV), y.to(DEV); loss = nn.functional.smooth_l1_loss(torch.sigmoid(m(x)), y, beta=0.02); opt.zero_grad(); loss.backward(); opt.step(); sched.step(); tl += loss.item()
        m.eval(); err = []
        with torch.no_grad():
            for x, y in dv: p = torch.sigmoid(m(x.to(DEV))).cpu(); err.append((p - y).abs())
        e = torch.cat(err).mean(0); score = float(e.sum())
        print(f"ep {ep+1}/{EPOCHS} loss {tl/len(dl):.4f} | erro medio val (fracao do lado) cx {e[0]:.3f} cy {e[1]:.3f} r {e[2]:.3f}", flush=True)
        if score < best[0]: best = (score, {k: v.detach().cpu().clone() for k, v in m.state_dict().items()})
    m.load_state_dict(best[1]); m.eval().cpu()
    class Wrap(nn.Module):
        def __init__(s, m): super().__init__(); s.m = m
        def forward(s, x): return torch.sigmoid(s.m(x))
    torch.onnx.export(Wrap(m), torch.zeros(1, 3, SIZE, SIZE), OUT / "iris_v1.onnx", input_names=["image"], output_names=["cxcyr"], opset_version=17, dynamo=False)
    json.dump({"name": "iris_v1", "created": datetime.datetime.now().isoformat(timespec="seconds"), "input": {"size": SIZE, "mean": MEAN.tolist(), "std": STD.tolist()}, "output": "cx, cy, r como fracao do lado da janela quadrada", "val_err": {"cx": float(e[0]), "cy": float(e[1]), "r": float(e[2])}, "file": "iris_v1.onnx"}, open(OUT / "iris_card.json", "w"), indent=1)
    print("salvo saida/iris_v1.onnx")
if __name__ == "__main__":
    main()
