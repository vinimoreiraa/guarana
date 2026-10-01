"""Segmentador da fenda ocular e da iris (2 canais) em janela 256 px: codificador MobileNetV3-small (timm, features_only)
+ decodificador leve. Treina no indice de treino/preparar_periorbital.py (CFD + CelebA reais + MPFB sintetico).
Saida: saida/fenda_v1.onnx (entrada 1x3x256x256 normalizada ImageNet; saida 1x2x256x256 logits) + fenda_card.json.
Uso: .venv/bin/python treino/treinar_segmentador.py [SEG_EPOCHS=12]
"""
import os, json, random, datetime, math
from pathlib import Path
import numpy as np, pandas as pd, torch, torch.nn as nn, torch.nn.functional as F, timm
from PIL import Image, ImageOps, ImageFilter
from torch.utils.data import Dataset, DataLoader
BASE = Path(__file__).resolve().parents[1]; OUT = BASE / "saida"; SIZE = 256; EPOCHS = int(os.environ.get("SEG_EPOCHS", 12)); DEV = "mps" if torch.backends.mps.is_available() else "cpu"
MEAN, STD = np.array([0.485, 0.456, 0.406], np.float32), np.array([0.229, 0.224, 0.225], np.float32)
class DS(Dataset):
    def __init__(self, df, train): self.df, self.train = df.reset_index(drop=True), train
    def __len__(self): return len(self.df)
    def __getitem__(self, i):
        r = self.df.iloc[i]; im = Image.open(BASE / r["file"]).convert("RGB"); mk = Image.open(BASE / r["mask"]).convert("RGB")
        if self.train:
            rng = random.Random()
            # re-janela: zoom 0.7-1.3 e deslocamento, mesmo corte para imagem e mascara
            z = rng.uniform(0.4, 1.35); S = int(SIZE * z); ox, oy = rng.randint(-45, 45), rng.randint(-45, 45)   # zoom forte: iris pode ocupar ate ~80% da janela (macro de celular)
            box = ((SIZE - S) // 2 + ox, (SIZE - S) // 2 + oy, (SIZE - S) // 2 + ox + S, (SIZE - S) // 2 + oy + S)
            im = im.crop(box).resize((SIZE, SIZE), Image.BILINEAR); mk = mk.crop(box).resize((SIZE, SIZE), Image.NEAREST)
            if rng.random() < 0.5: im, mk = ImageOps.mirror(im), ImageOps.mirror(mk)
            ang = rng.uniform(-15, 15); im = im.rotate(ang, Image.BILINEAR); mk = mk.rotate(ang, Image.NEAREST)
            if rng.random() < 0.3: im = im.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.5)))
            a = np.asarray(im, np.float32) / 255; a = np.clip(a * rng.uniform(0.6, 1.4) + rng.uniform(-0.12, 0.12), 0, 1)
            if rng.random() < 0.5:   # troca leve de matiz/saturacao por canal
                a = np.clip(a * np.array([rng.uniform(0.85, 1.15), rng.uniform(0.85, 1.15), rng.uniform(0.85, 1.15)], np.float32), 0, 1)
        else: a = np.asarray(im, np.float32) / 255
        m = (np.asarray(mk)[:, :, :2] > 128).astype(np.float32).transpose(2, 0, 1)
        return torch.tensor(((a - MEAN) / STD).transpose(2, 0, 1)), torch.tensor(m)
class Seg(nn.Module):
    def __init__(self):
        super().__init__(); self.enc = timm.create_model("mobilenetv3_small_100", pretrained=True, features_only=True, out_indices=(0, 1, 2, 3, 4))
        ch = self.enc.feature_info.channels()   # ex.: [16, 16, 24, 48, 576] em strides 2,4,8,16,32
        self.up = nn.ModuleList(); prev = ch[-1]
        for c in reversed(ch[:-1]):
            self.up.append(nn.Sequential(nn.Conv2d(prev + c, c * 2, 3, padding=1), nn.BatchNorm2d(c * 2), nn.ReLU(inplace=True), nn.Conv2d(c * 2, c * 2, 3, padding=1), nn.BatchNorm2d(c * 2), nn.ReLU(inplace=True))); prev = c * 2
        self.head = nn.Conv2d(prev, 2, 1)
    def forward(self, x):
        fs = self.enc(x); y = fs[-1]
        for up, f in zip(self.up, reversed(fs[:-1])):
            y = F.interpolate(y, size=f.shape[-2:], mode="bilinear", align_corners=False); y = up(torch.cat([y, f], 1))
        return F.interpolate(self.head(y), size=x.shape[-2:], mode="bilinear", align_corners=False)
def dice(p, t):
    p = torch.sigmoid(p); return 1 - ((2 * (p * t).sum((2, 3)) + 1) / (p.sum((2, 3)) + t.sum((2, 3)) + 1)).mean()
def main():
    df = pd.read_csv(BASE / "dados/cache_seg/indice.csv"); rng = np.random.RandomState(0); val_mask = rng.rand(len(df)) < 0.1
    tr, va = df[~val_mask], df[val_mask]; print("treino", len(tr), "val", len(va), dict(df["source"].value_counts()))
    torch.multiprocessing.set_start_method("fork", force=True)
    dl = DataLoader(DS(tr, True), batch_size=32, shuffle=True, num_workers=4, drop_last=True); dv = DataLoader(DS(va, False), batch_size=32, num_workers=2)
    m = Seg().to(DEV); opt = torch.optim.AdamW(m.parameters(), 5e-4, weight_decay=1e-4); sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, EPOCHS * len(dl)); best = (0, None)
    for ep in range(EPOCHS):
        m.train(); tl = 0
        for x, y in dl:
            x, y = x.to(DEV), y.to(DEV); p = m(x); loss = F.binary_cross_entropy_with_logits(p, y) + dice(p, y); opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(m.parameters(), 2.0); opt.step(); sched.step(); tl += loss.item()
        m.eval(); inter = np.zeros(2); uni = np.zeros(2)
        with torch.no_grad():
            for x, y in dv:
                p = (torch.sigmoid(m(x.to(DEV))) > 0.5).float().cpu(); inter += (p * y).sum((0, 2, 3)).numpy(); uni += ((p + y) > 0).float().sum((0, 2, 3)).numpy()
        iou = inter / np.maximum(uni, 1); print(f"ep {ep+1}/{EPOCHS} loss {tl/len(dl):.3f} | IoU val fenda {iou[0]:.3f} iris {iou[1]:.3f}", flush=True)
        if iou.mean() > best[0]: best = (iou.mean(), {k: v.detach().cpu().clone() for k, v in m.state_dict().items()})
    m.load_state_dict(best[1]); m.eval().cpu()
    torch.onnx.export(m, torch.zeros(1, 3, SIZE, SIZE), OUT / "fenda_v1.onnx", input_names=["image"], output_names=["logits"], opset_version=17, dynamo=False)
    json.dump({"name": "fenda_v1", "created": datetime.datetime.now().isoformat(timespec="seconds"), "input": {"size": SIZE, "mean": MEAN.tolist(), "std": STD.tolist()}, "output": "logits 2 canais: 0 = fenda (esclera+iris), 1 = iris; sigmoide > 0.5", "iou_val": {"fenda": float(iou[0]), "iris": float(iou[1])}, "file": "fenda_v1.onnx"}, open(OUT / "fenda_card.json", "w"), indent=1)
    print("salvo saida/fenda_v1.onnx")
if __name__ == "__main__":
    main()
