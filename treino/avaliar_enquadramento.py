"""Port em numpy do gate de enquadramento do app (core/EyeFraming.kt), para medir o comportamento em muitas imagens
sem fotografar nada: quantas de cada fonte passam (OK) e por que as outras sao recusadas.

Uso: .venv/bin/python treino/avaliar_enquadramento.py [--n 150] [fontes...]
"""
import argparse, collections
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

W = 160; MIN_DIAM, MAX_DIAM, CENTER_TOL = 0.10, 0.60, 0.28

def check(img):
    im = img.convert("L"); s = W / max(im.size); w, h = max(16, int(im.width * s)), max(16, int(im.height * s))
    g = np.asarray(im.resize((w, h), Image.BILINEAR), dtype=np.float32)
    dark = np.percentile(g, 12); bright = np.percentile(g, 80)
    lab, n = ndimage.label(g <= dark)
    blobs = []
    mn = min(w, h)
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k); cnt = len(xs)
        area = cnt / (w * h)
        if area < 0.004 or area > 0.35: continue
        bw, bh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
        if min(bw, bh) / max(bw, bh) < 0.45: continue
        if cnt / (bw * bh) < 0.45: continue
        diam = np.sqrt(cnt / np.pi) * 2 / mn
        cx, cy = int(xs.mean()), int(ys.mean()); r = max(2, int(diam * mn / 2))
        def br(x, y): return 0 <= x < w and 0 <= y < h and g[y, x] >= bright
        side = 0
        for dy in range(-r // 2, r // 2 + 1, max(1, r // 4)):
            side += br(cx - int(r * 1.6), cy + dy) + br(cx + int(r * 1.6), cy + dy)
        if side == 0: continue
        blobs.append((cnt, cx / w, cy / h, diam))
    if not blobs: return "NOT_FOUND", 0.0
    blobs.sort(reverse=True); _, cx, cy, diam = blobs[0]
    for _, bx, by, bd in blobs[1:]:
        if bd >= diam * 0.55 and abs(bx - cx) * (w / mn) >= diam * 1.5 and abs(by - cy) * (h / mn) <= diam * 1.2:
            return "TWO_EYES", diam
    off = max(abs(cx - 0.5), abs(cy - 0.5))
    if diam < MIN_DIAM: return "TOO_FAR", diam
    if diam > MAX_DIAM: return "TOO_CLOSE", diam
    if off > CENTER_TOL: return "OFF_CENTER", diam
    return "OK", diam

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=150); ap.add_argument("fontes", nargs="*", default=["slid", "eye_diseases", "cfd", "hf_jaundice", "conj_seg"])
    a = ap.parse_args()
    base = Path(__file__).resolve().parents[1] / "dados" / "crops"
    for src in a.fontes:
        files = sorted((base / src).glob("*.jpg"))[: a.n]
        if not files: print(src, "sem recortes"); continue
        c = collections.Counter(); diams = []
        for f in files:
            r, d = check(Image.open(f)); c[r] += 1; diams.append(d)
        tot = sum(c.values())
        print(f"{src:14s} n={tot:4d} " + "  ".join(f"{k}={v/tot:.0%}" for k, v in c.most_common()) + f"  | diam mediano {np.median(diams):.2f}")

if __name__ == "__main__":
    main()
