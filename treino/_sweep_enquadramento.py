import collections, itertools
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage
W = 160
def check(img, pct=12, opening=0, sclera=True, fill_min=0.45, aspect_min=0.45, min_diam=0.10, max_diam=0.60, tol=0.28, dbg=False):
    im = img.convert("L"); s = W / max(im.size); w, h = max(16, int(im.width * s)), max(16, int(im.height * s))
    g = np.asarray(im.resize((w, h), Image.BILINEAR), dtype=np.float32)
    g = ndimage.gaussian_filter(g, 1.0)
    dark = np.percentile(g, pct); bright = np.percentile(g, 75)
    mask = g <= dark
    if opening: mask = ndimage.binary_opening(mask, iterations=opening)
    lab, n = ndimage.label(mask); mn = min(w, h); blobs = []; rej = collections.Counter()
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k); cnt = len(xs); area = cnt / (w * h)
        if area < 0.003 or area > 0.35: rej["area"] += 1; continue
        bw, bh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
        if min(bw, bh) / max(bw, bh) < aspect_min: rej["aspect"] += 1; continue
        circ = cnt / (np.pi * (max(bw, bh) / 2) ** 2)
        if circ < fill_min: rej["fill"] += 1; continue
        diam = np.sqrt(cnt / np.pi) * 2 / mn
        cx, cy = int(xs.mean()), int(ys.mean()); r = max(2, int(diam * mn / 2))
        if sclera:
            def br(x, y): return 0 <= x < w and 0 <= y < h and g[y, x] >= bright
            side = sum(br(cx - int(r * 1.7), cy + dy) + br(cx + int(r * 1.7), cy + dy) for dy in range(-r // 2, r // 2 + 1, max(1, r // 4)))
            if side == 0: rej["sclera"] += 1; continue
        blobs.append((cnt, cx / w, cy / h, diam))
    if dbg: print("  rejeitados:", dict(rej), "candidatos:", len(blobs))
    if not blobs: return "NOT_FOUND", 0.0
    blobs.sort(reverse=True); _, cx, cy, diam = blobs[0]
    for _, bx, by, bd in blobs[1:]:
        if bd >= diam * 0.55 and abs(bx - cx) * (w / mn) >= diam * 1.5 and abs(by - cy) * (h / mn) <= diam * 1.2: return "TWO_EYES", diam
    off = max(abs(cx - 0.5), abs(cy - 0.5))
    if diam < min_diam: return "TOO_FAR", diam
    if diam > max_diam: return "TOO_CLOSE", diam
    if off > tol: return "OFF_CENTER", diam
    return "OK", diam
base = Path(__file__).resolve().parents[1] / "dados" / "crops"
sets = {s: sorted((base / s).glob("*.jpg"))[:120] for s in ["slid", "cfd", "hf_jaundice", "conj_seg", "eye_diseases"]}
print("debug slid/1.jpg:"); check(Image.open(base / "slid/1.jpg"), dbg=True); check(Image.open(base / "cfd/0_cfd_l.jpg"), dbg=True)
print("pct opening sclera fill | OK% por fonte (slid cfd hfj conj eyed) | NOT_FOUND% medio")
for pct, op, sc, fm in itertools.product([8, 12, 18, 25], [0, 1], [True, False], [0.35, 0.5]):
    oks = []; nfs = []
    for s, files in sets.items():
        c = collections.Counter(check(Image.open(f), pct, op, sc, fm)[0] for f in files)
        t = sum(c.values()); oks.append(c["OK"] / t); nfs.append(c["NOT_FOUND"] / t)
    print(f"{pct:3d} {op:7d} {str(sc):6s} {fm:.2f} | " + " ".join(f"{o:4.0%}" for o in oks) + f" | {np.mean(nfs):.0%}")
