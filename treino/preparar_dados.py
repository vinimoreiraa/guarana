"""Gera dados/labels_<fonte>.csv e recortes normalizados em dados/crops/<fonte>/ a partir de dados/raw/.

Uso: .venv/bin/python treino/preparar_dados.py [fonte ...]      (sem args = todas as disponiveis)

Framing: o modelo espera um olho (ou os dois) ocupando a maior parte da imagem. Fotos de rosto inteiro sao
recortadas na regiao dos olhos com Haar (OpenCV); close-ups ficam como estao; CFD usa as caixas COCO por olho;
conj_seg usa a mascara da conjuntiva.
"""
import csv, json, re, sys, zipfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps

BASE = Path(__file__).resolve().parents[1]
RAW, CROPS, DADOS = BASE / "dados" / "raw", BASE / "dados" / "crops", BASE / "dados"
LABELS = ["hiperemia", "ictericia", "pterigio", "pinguecula", "catarata_leucocoria", "hemorragia_subconjuntival",
          "lesao_pigmentada", "opacidade_corneana", "tumor_superficie_ocular", "ceratite", "cisto_conjuntival",
          "lente_intraocular", "conjuntivite", "uveite", "alteracao_palpebral"]
COLS = ["file", "subject_id", "source", "domain", *LABELS, "revisar"]
MAX_SIDE = 640
MIN_SIDE = 96
EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# ---------------- utilidades ----------------
def load(p):
    return ImageOps.exif_transpose(Image.open(p)).convert("RGB")

def expand(box, w, h, fx, fy, min_side=None, min_ratio=0.75):
    x0, y0, x1, y1 = box
    cx, cy, bw, bh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) * fx, (y1 - y0) * fy
    if min_side:
        bw, bh = max(bw, min_side), max(bh, min_side)
    side_w, side_h = bw, max(bh, bw * min_ratio)   # nao deixa virar uma tira muito achatada
    return (int(max(0, cx - side_w / 2)), int(max(0, cy - side_h / 2)), int(min(w, cx + side_w / 2)), int(min(h, cy + side_h / 2)))

def save(img, box, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    im = img.crop(box) if box else img
    if min(im.size) < MIN_SIDE:
        return None                               # recorte pequeno demais para valer como amostra
    s = MAX_SIDE / max(im.size)
    if s < 1:
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    im.save(out, "JPEG", quality=92)
    return str(out.relative_to(DADOS))

def row(file, subject, source, domain, pos=(), revisar=""):
    r = {"file": file, "subject_id": subject, "source": source, "domain": domain, "revisar": revisar}
    for l in LABELS:
        r[l] = int(l in pos)
    return r

def write_csv(source, rows):
    p = DADOS / f"labels_{source}.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(rows)
    pos = {l: sum(r[l] for r in rows) for l in LABELS if sum(r[l] for r in rows)}
    print(f"  {source}: {len(rows)} linhas -> {p.name} | positivos {pos}")

# ---------------- OpenCV Haar: regiao dos olhos em fotos de rosto ----------------
_CASC = None

def cascades():
    global _CASC
    if _CASC is None:
        import cv2
        _CASC = (cv2, cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml"),
                 cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml"))
    return _CASC

def eyes_box(img):
    """Caixa (x0,y0,x1,y1) cobrindo os olhos detectados, ou None se a foto ja e um close-up."""
    cv2, face, eye = cascades()
    g = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2GRAY)
    s = min(1.0, 800 / max(g.shape))
    g2 = cv2.resize(g, None, fx=s, fy=s) if s < 1 else g
    faces = face.detectMultiScale(g2, 1.1, 5)
    eyes = eye.detectMultiScale(g2, 1.1, 8, minSize=(24, 24))
    if len(faces):
        fx0, fy0, fw, fh = max(faces, key=lambda b: b[2] * b[3])
        eyes = [e for e in eyes if fx0 <= e[0] and e[0] + e[2] <= fx0 + fw and fy0 <= e[1] <= fy0 + fh * 0.6]
    if len(eyes) == 0:
        return None
    # fica com o melhor par (mesma altura, tamanho parecido, lado a lado); senao, o maior
    eyes = sorted(eyes, key=lambda e: -e[2] * e[3])[:5]
    best = None
    for i in range(len(eyes)):
        for j in range(i + 1, len(eyes)):
            a, b = eyes[i], eyes[j]
            same_row = abs((a[1] + a[3] / 2) - (b[1] + b[3] / 2)) < 0.6 * max(a[3], b[3])
            similar = 0.5 < (a[2] / b[2]) < 2.0
            apart = abs((a[0] + a[2] / 2) - (b[0] + b[2] / 2)) > 0.8 * max(a[2], b[2])
            if same_row and similar and apart:
                score = a[2] * a[3] + b[2] * b[3]
                if best is None or score > best[0]:
                    best = (score, [a, b])
    eyes = best[1] if best else [eyes[0]]
    xs0 = [e[0] for e in eyes]; ys0 = [e[1] for e in eyes]
    xs1 = [e[0] + e[2] for e in eyes]; ys1 = [e[1] + e[3] for e in eyes]
    box = tuple(v / s for v in (min(xs0), min(ys0), max(xs1), max(ys1)))
    exp = expand(box, img.width, img.height, fx=1.3, fy=1.4, min_ratio=0.42)   # faixa dos dois olhos
    if (exp[2] - exp[0]) > 0.9 * img.width and (exp[3] - exp[1]) > 0.9 * img.height:
        return None                               # a faixa dos olhos ja e a foto inteira
    return exp

def crop_generic(src, p, out_name):
    img = load(p)
    return save(img, eyes_box(img), CROPS / src / out_name)

# ---------------- fontes ----------------
SOURCES = {}
def src(name):
    def deco(fn): SOURCES[name] = fn; return fn
    return deco

@src("cfd")
def _():
    base = RAW / "periorbital/extract/periorbital_dataset"
    rows = []
    for j in sorted((base / "coco_annotations/cfd_annotations_coco").glob("*.json")):
        start = int(j.stem.split("_")[1]); d = json.load(j.open())
        cats = {c["id"]: c["name"] for c in d["categories"]}
        anns = {}
        for a in d["annotations"]:
            anns.setdefault(a["image_id"], {})[cats[a["category_id"]]] = a["bbox"]
        for im in d["images"]:
            f = base / "cfd_final_data/cfd_output_images" / f"{start + im['id'] - 1}_cfd.jpg"
            subj = "-".join(im["file_name"].split("-")[:3])          # CFD-AF-200
            img = load(f)
            for side in ("l", "r"):
                sc, ir = anns.get(im["id"], {}).get(f"{side}_sclera"), anns.get(im["id"], {}).get(f"{side}_iris")
                if not sc: continue
                x, y, w, h = sc
                box = expand((x, y, x + w, y + h), img.width, img.height, fx=1.8, fy=3.0, min_side=120)
                rel = save(img, box, CROPS / "cfd" / f"{f.stem}_{side}.jpg")
                if rel: rows.append(row(rel, subj, "cfd", "face_crop"))
    write_csv("cfd", rows)

@src("conj_seg")
def _():
    imgs, masks = RAW / "conj_seg/Images", RAW / "conj_seg/Masks Annotator 1"
    rows = []
    for p in sorted(imgs.iterdir()):
        if p.suffix.lower() not in EXTS: continue
        m = next((q for q in masks.glob(p.stem + ".*") if q.suffix.lower() in EXTS), None)
        img = load(p)
        box = None
        if m and m.exists():
            mk = np.asarray(Image.open(m).convert("L")) > 0
            ys, xs = np.where(mk)
            if len(xs):
                box = expand((xs.min(), ys.min(), xs.max(), ys.max()), img.width, img.height, fx=2.6, fy=4.5)
        if box is None:
            box = eyes_box(img)
        rel = save(img, box, CROPS / "conj_seg" / f"{p.stem}.jpg")
        if rel: rows.append(row(rel, f"conjseg_{p.stem}", "conj_seg", "phone_closeup"))
    write_csv("conj_seg", rows)

@src("hf_jaundice")
def _():
    rows = []
    for split in ("train", "test"):
        for cls, pos in (("Healthy", ()), ("Jaundice", ("ictericia",))):
            d = RAW / "hf_jaundice" / split / cls
            if not d.exists(): continue
            for p in sorted(d.iterdir()):
                if p.suffix.lower() not in EXTS: continue
                try:
                    rel = crop_generic("hf_jaundice", p, f"{split}_{cls}_{p.stem[:40]}.jpg")
                except Exception as e:
                    print("   pulando", p.name, e); continue
                if rel: rows.append(row(rel, f"hfj_{p.stem[:40]}", "hf_jaundice", "web", pos))
    write_csv("hf_jaundice", rows)

@src("eye_diseases")
def _():
    # v2: conjuntivite e uveite viram rotulos proprios (alem do sinal hiperemia); "Eyelid" e a pasta de alteracoes palpebrais
    mapping = {"Cataract": ("catarata_leucocoria",), "Conjunctivitis": ("conjuntivite", "hiperemia"), "Uveitis": ("uveite", "hiperemia"),
               "Eyelid": ("alteracao_palpebral",), "Normal": ()}
    synth = re.compile(r"smote|aug|synthetic|_gen", re.I)
    rows = []
    for folder, pos in mapping.items():
        d = RAW / "eye_diseases" / folder
        if not d.exists(): continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() not in EXTS or synth.search(p.name): continue
            try:
                rel = crop_generic("eye_diseases", p, f"{folder}_{p.stem[:40]}.jpg")
            except Exception as e:
                print("   pulando", p.name, e); continue
            if rel: rows.append(row(rel, f"eyed_{folder}_{p.stem[:40]}", "eye_diseases", "web", pos))
    write_csv("eye_diseases", rows)

@src("faridpur")
def _():
    z = RAW / "faridpur" / "Original Dataset.zip"
    out = RAW / "faridpur" / "pterygium"
    if not out.exists():
        with zipfile.ZipFile(z) as zf:
            names = [n for n in zf.namelist() if "pteryg" in n.lower() and not n.endswith("/")]
            print(f"   extraindo {len(names)} arquivos de pterigio")
            out.mkdir(parents=True)
            for n in names:
                (out / Path(n).name).write_bytes(zf.read(n))
    rows = []
    for p in sorted(out.iterdir()):
        if p.suffix.lower() not in EXTS: continue
        rel = crop_generic("faridpur", p, f"{p.stem[:40]}.jpg")
        if rel: rows.append(row(rel, f"farid_{p.stem[:40]}", "faridpur", "external_camera", ("pterigio",)))
    write_csv("faridpur", rows)

@src("hf_pterygium")
def _():
    """HF mostafasmart/pterygium2class: 975+245 fotos de olho externo (web/celular) rotuladas pterygium x notPtery.
    Os negativos entram sem rotulo (olho externo sem pterigio); dominio 'web'."""
    rows = []
    for folder, pos in (("pterygium", ("pterigio",)), ("notPtery", ())):
        d = RAW / "hf_pterygium" / folder
        if not d.exists(): continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() not in EXTS: continue
            try: rel = crop_generic("hf_pterygium", p, f"{folder}_{p.stem}.jpg")
            except Exception as e: print("   pulando", p.name, e); continue
            if rel: rows.append(row(rel, f"hfpt_{folder}_{p.stem}", "hf_pterygium", "web", pos))
    write_csv("hf_pterygium", rows)

@src("slid")
def _():
    import pandas as pd
    d = pd.read_csv(RAW / "slid/Annotations.csv")
    att = d["attributes"].apply(lambda s: json.loads(s) if isinstance(s, str) and s.startswith("{") else {})
    d["lesion"] = att.apply(lambda a: a.get("lesion", ""))
    # v2: cada lesao pode virar mais de um rotulo (ceratite tambem e opacidade); tumor, cisto e LIO entram como rotulos
    MAP = {"Subconjunctival hemorrhage": ("hemorragia_subconjuntival",), "Pigmented nevus": ("lesao_pigmentada",),
           "Pinguecula": ("pinguecula",), "Pterygium": ("pterigio",), "Conjunctival injection": ("hiperemia",),
           "Cataract": ("catarata_leucocoria",), "Lens dislocation/Cataract": ("catarata_leucocoria",),
           "Corneal scarring": ("opacidade_corneana",), "Corneal dystrophy": ("opacidade_corneana",),
           "Keratitis": ("ceratite", "opacidade_corneana"), "Corneal / Conjunctival tumor": ("tumor_superficie_ocular",),
           "Conjunctival cyst": ("cisto_conjuntival",), "Intraocular lens": ("lente_intraocular",)}
    EXCL = {"Lens dislocation"}   # 36 imagens: poucas para um rotulo
    pngs = list((RAW / "slid/extract").rglob("*.png"))
    if not pngs:
        raise FileNotFoundError("extraia Original_Slit-lamp_Images.zip em dados/raw/slid/extract")
    imgdir = {p.name: p for p in pngs}
    rows, skipped = [], 0
    for fn, grp in d.groupby("filename"):
        les = {l for l in grp["lesion"] if l}
        if les & EXCL or fn not in imgdir:
            skipped += 1; continue
        pos = {x for l in les if l in MAP for x in MAP[l]}
        rel = save(load(imgdir[fn]), None, CROPS / "slid" / f"{Path(fn).stem}.jpg")   # lampada de fenda ja e close-up
        if rel: rows.append(row(rel, f"slid_{Path(fn).stem}", "slid", "slit_lamp", pos))
    print(f"   slid: {skipped} imagens excluidas (tumor/cisto/LIO/ceratite ou ausentes)")
    write_csv("slid", rows)

def main():
    names = sys.argv[1:] or list(SOURCES)
    for n in names:
        print("==", n, flush=True)
        try:
            SOURCES[n]()
        except Exception as e:
            print(f"  {n} FALHOU: {type(e).__name__}: {e}", flush=True)

if __name__ == "__main__":
    main()
