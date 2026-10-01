"""Periorbital (CFD + CelebA) -> janelas por olho com mascara de 2 canais (fenda = esclera+iris+pupila; iris = iris+pupila)
e circulo da iris, mais as mascaras sinteticas do MPFB. Saida: dados/cache_seg/<fonte>/<id>.jpg + <id>_m.png (R=fenda, G=iris)
e dados/cache_seg/indice.csv (file, mask, cx, cy, r, source). Uso: .venv/bin/python treino/preparar_periorbital.py
"""
import json, glob, os, csv, math, random
from pathlib import Path
import numpy as np
from PIL import Image
BASE = Path(__file__).resolve().parents[1]; B = BASE / "dados/raw/periorbital/extract/periorbital_dataset"; OUT = BASE / "dados/cache_seg"; OUT.mkdir(exist_ok=True)
def rle_decode(seg, h, w):
    """RLE nao comprimido do COCO (contagens alternadas 0/1, ordem por coluna)"""
    counts = seg["counts"]; m = np.zeros(h * w, np.uint8); pos = 0; val = 0
    for c in counts:
        m[pos:pos + c] = val; pos += c; val = 1 - val
    return m.reshape((w, h)).T
def main():
    imgs = {os.path.basename(p): p for p in glob.glob(str(B / "**/*.jpg"), recursive=True)}
    rows = []; seen = set()
    jsons = sorted(glob.glob(str(B / "coco_annotations/cfd_annotations_coco/*.json"))) + [str(B / "coco_annotations/celeb_annotations_coco/coco_celeb_0-1500.json"), str(B / "coco_annotations/celeb_annotations_coco/coco_celeb_1500-2100.json")]
    for j in jsons:
        d = json.load(open(j)); cats = {c["id"]: c["name"] for c in d["categories"]}; by = {}
        for a in d["annotations"]: by.setdefault(a["image_id"], {})[cats[a["category_id"]]] = a
        fonte = "cfd" if "cfd" in j else "celeb"; (OUT / fonte).mkdir(exist_ok=True); n = 0
        for im in d["images"]:
            fn = im["file_name"]
            if fn not in imgs or fn in seen: continue
            a = by.get(im["id"], {}); h, w = im["height"], im["width"]
            try: pil = Image.open(imgs[fn]).convert("RGB")
            except Exception: continue
            if pil.size != (w, h): continue
            for side in ("r", "l"):
                if f"{side}_sclera" not in a or f"{side}_iris" not in a: continue
                sc = rle_decode(a[f"{side}_sclera"]["segmentation"], h, w); ir = rle_decode(a[f"{side}_iris"]["segmentation"], h, w)
                pu = rle_decode(a[f"{side}_pupil"]["segmentation"], h, w) if f"{side}_pupil" in a else np.zeros_like(ir)
                fenda = (sc | ir | pu) > 0; iris = (ir | pu) > 0
                if iris.sum() < 30 or fenda.sum() < 60: continue
                ys, xs = np.nonzero(iris); cx, cy = xs.mean(), ys.mean(); r = max((xs.max() - xs.min()) / 2, math.sqrt(iris.sum() / math.pi))
                # janela: iris a 15-40% do lado, centro deslocado ate 25%
                rng = random.Random(hash((fn, side)) & 0xffff); side_px = 2 * r / rng.uniform(0.15, 0.40); ox, oy = rng.uniform(-0.25, 0.25) * side_px, rng.uniform(-0.25, 0.25) * side_px
                x0, y0 = int(round(cx + ox - side_px / 2)), int(round(cy + oy - side_px / 2)); S = int(round(side_px))
                if S < 24: continue
                crop = pil.crop((x0, y0, x0 + S, y0 + S)).resize((256, 256), Image.BILINEAR)
                mk = np.zeros((h, w, 3), np.uint8); mk[:, :, 0] = fenda * 255; mk[:, :, 1] = iris * 255
                mcrop = Image.fromarray(mk).crop((x0, y0, x0 + S, y0 + S)).resize((256, 256), Image.NEAREST)
                sid = f"{Path(fn).stem[:40]}_{side}"; crop.save(OUT / fonte / f"{sid}.jpg", "JPEG", quality=92); mcrop.save(OUT / fonte / f"{sid}_m.png")
                sc_ = 256 / S; rows.append({"file": str((OUT / fonte / f"{sid}.jpg").relative_to(BASE)), "mask": str((OUT / fonte / f"{sid}_m.png").relative_to(BASE)), "cx": (cx - x0) * sc_, "cy": (cy - y0) * sc_, "r": r * sc_, "source": fonte, "res_iris_px": 2 * r}); n += 1
            seen.add(fn)
        print(os.path.basename(j), "->", n, "olhos", flush=True)
    # CelebA (mapas de rotulo prontos: 1 sobrancelha, 2 esclera, 3 iris, 4 caruncula, 5 palpebra): um olho por componente de iris
    C = B / "celeb_final_data"; (OUT / "celeb").mkdir(exist_ok=True); n = 0
    for mp in sorted(glob.glob(str(C / "celeb_output_masks/*.png"))):
        ip = mp.replace("celeb_output_masks", "celeb_output_images").replace(".png", ".jpg")
        if not os.path.exists(ip): continue
        lab = np.asarray(Image.open(mp)); pil = Image.open(ip).convert("RGB")
        if lab.shape[:2] != (pil.size[1], pil.size[0]): continue
        iris_all = lab == 3; fenda_all = (lab == 2) | iris_all
        # separa os dois olhos pela metade da largura (faixa horizontal dos dois olhos)
        w = lab.shape[1]
        for side, sl in (("l", slice(0, w // 2)), ("r", slice(w // 2, w))):
            iris = np.zeros_like(iris_all); iris[:, sl] = iris_all[:, sl]; fenda = np.zeros_like(fenda_all); fenda[:, sl] = fenda_all[:, sl]
            if iris.sum() < 25 or fenda.sum() < 50: continue
            ys, xs = np.nonzero(iris); cx, cy = xs.mean(), ys.mean(); r = max((xs.max() - xs.min()) / 2, math.sqrt(iris.sum() / math.pi))
            rng = random.Random(hash((mp, side)) & 0xffff); side_px = 2 * r / rng.uniform(0.15, 0.40); ox, oy = rng.uniform(-0.25, 0.25) * side_px, rng.uniform(-0.25, 0.25) * side_px
            x0, y0 = int(round(cx + ox - side_px / 2)), int(round(cy + oy - side_px / 2)); S = int(round(side_px))
            if S < 20: continue
            crop = pil.crop((x0, y0, x0 + S, y0 + S)).resize((256, 256), Image.BILINEAR)
            mk = np.zeros((*lab.shape[:2], 3), np.uint8); mk[:, :, 0] = fenda * 255; mk[:, :, 1] = iris * 255
            mcrop = Image.fromarray(mk).crop((x0, y0, x0 + S, y0 + S)).resize((256, 256), Image.NEAREST)
            sid = f"{Path(ip).stem[:40]}_{side}"; crop.save(OUT / "celeb" / f"{sid}.jpg", "JPEG", quality=92); mcrop.save(OUT / "celeb" / f"{sid}_m.png")
            sc_ = 256 / S; rows.append({"file": str((OUT / "celeb" / f"{sid}.jpg").relative_to(BASE)), "mask": str((OUT / "celeb" / f"{sid}_m.png").relative_to(BASE)), "cx": (cx - x0) * sc_, "cy": (cy - y0) * sc_, "r": r * sc_, "source": "celeb", "res_iris_px": 2 * r}); n += 1
    print("celeb ->", n, "olhos", flush=True)
    # MPFB: imagem inteira 512 -> 256 (iris ja em escala de close-up)
    (OUT / "mpfb").mkdir(exist_ok=True); n = 0
    for m in glob.glob(str(BASE / "sintese/render/mpfb*/**/*_mask.png"), recursive=True):
        img = m.replace("_mask.png", ".jpg")
        if not os.path.exists(img): continue
        a = np.asarray(Image.open(m).convert("RGB")); g = a[:, :, 1] > 128; fenda = (a[:, :, 0] > 128) | g | (a[:, :, 2] > 128)
        if g.sum() < 200: continue
        ys, xs = np.nonzero(g); cx, cy = xs.mean(), ys.mean(); r = (xs.max() - xs.min()) / 2
        sid = Path(img).stem; Image.open(img).convert("RGB").resize((256, 256), Image.BILINEAR).save(OUT / "mpfb" / f"{sid}.jpg", "JPEG", quality=92)
        mk = np.zeros(a.shape, np.uint8); mk[:, :, 0] = fenda * 255; mk[:, :, 1] = g * 255; Image.fromarray(mk).resize((256, 256), Image.NEAREST).save(OUT / "mpfb" / f"{sid}_m.png")
        sc_ = 256 / a.shape[1]; rows.append({"file": str((OUT / "mpfb" / f"{sid}.jpg").relative_to(BASE)), "mask": str((OUT / "mpfb" / f"{sid}_m.png").relative_to(BASE)), "cx": cx * sc_, "cy": cy * sc_, "r": r * sc_, "source": "mpfb", "res_iris_px": 2 * r}); n += 1
    print("mpfb ->", n)
    with (OUT / "indice.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "mask", "cx", "cy", "r", "source", "res_iris_px"]); w.writeheader(); w.writerows(rows)
    import collections; print("total", len(rows), dict(collections.Counter(r["source"] for r in rows)))
if __name__ == "__main__":
    main()
