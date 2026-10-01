"""Fontes novas (30/09, grupo A) viram CSVs de TESTE EXTERNO em dados/externos/ (o treino so le dados/labels*.csv).
- mendeley_conj_lesoes: pterygium -> pterigio; nevus/melanosis -> lesao_pigmentada; melanoma -> lesao_pigmentada + tumor_superficie_ocular; normal -> negativo
- mendeley_blefarite: mgd -> alteracao_palpebral; normal -> negativo
- zenodo_eyearea_tr: 1.980 fotos normais de celular (amostra de 500) -> negativos
- hf_pinkeye: conjuntivite (viral/bacteriana/alergica/irritativa) + normal, DESDUPLICADO contra eye_diseases (md5 e dHash<=6), ate 500 por classe
Cada imagem passa pelo gate de enquadramento (OK/TOO_CLOSE/OFF_CENTER ficam). Uso: .venv/bin/python treino/preparar_novas_fontes.py
"""
import csv, hashlib, random, sys
from pathlib import Path
from PIL import Image, ImageOps
BASE = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(BASE / "treino"))
from preparar_pubmed import framing, LABELS
RAW = BASE / "dados/raw"; OUT = BASE / "dados/externos"; OUT.mkdir(exist_ok=True); CROPS = BASE / "dados/crops"
EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
def dhash(im, s=8):
    g = ImageOps.exif_transpose(im).convert("L").resize((s + 1, s), Image.BILINEAR); px = list(g.getdata())
    return sum(1 << (i * s + j) for i in range(s) for j in range(s) if px[i * (s + 1) + j] > px[i * (s + 1) + j + 1])
def ham(a, b): return bin(a ^ b).count("1")
def escreve(nome, itens, fonte, dominio, max_por_classe=None, seed=0):
    """itens: lista de (path, labels, classe). Recorta/gate e escreve dados/externos/labels_<nome>.csv"""
    rng = random.Random(seed); por = {}
    for p, labs, cls in itens: por.setdefault(cls, []).append((p, labs))
    rows = []; d = CROPS / nome; d.mkdir(parents=True, exist_ok=True); stats = {}
    for cls, lst in por.items():
        rng.shuffle(lst); lst = lst[:max_por_classe] if max_por_classe else lst; ok = 0
        for p, labs in lst:
            try: im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
            except Exception: continue
            if max(im.size) > 1600: im.thumbnail((1600, 1600))
            c, conf = framing(im)
            if c not in ("OK", "TOO_CLOSE", "OFF_CENTER") or conf < 0.5: continue
            out = d / (hashlib.md5(str(p).encode()).hexdigest()[:10] + "_" + p.stem[:40] + ".jpg"); im.save(out, "JPEG", quality=92); ok += 1
            r = {"file": str(out.relative_to(BASE / "dados")), "subject_id": f"{fonte}_{p.stem[:50]}", "source": fonte, "domain": dominio, "classe": cls, "enquadramento": c}
            for l in LABELS: r[l] = int(l in labs)
            rows.append(r)
        stats[cls] = f"{ok}/{len(lst)}"
    with (OUT / f"labels_{nome}.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "subject_id", "source", "domain", *LABELS, "classe", "enquadramento"]); w.writeheader(); w.writerows(rows)
    print(f"{nome}: {len(rows)} recortes | aceitos por classe {stats}", flush=True)
def lista(d): return sorted(p for p in Path(d).rglob("*") if p.suffix.lower() in EXTS)
def main():
    # 1) mendeley_conj_lesoes
    M = RAW / "mendeley_conj_lesoes"; it = []
    for cls, labs in (("pterygium", ["pterigio"]), ("nevus", ["lesao_pigmentada"]), ("melanosis", ["lesao_pigmentada"]), ("melanoma", ["lesao_pigmentada", "tumor_superficie_ocular"]), ("normal", [])):
        it += [(p, labs, cls) for p in lista(M / cls)]
    escreve("mendeley_conj", it, "mendeley_conj", "web")
    # 2) blefarite
    B = RAW / "mendeley_blefarite"; it = [(p, ["alteracao_palpebral"], "mgd") for p in lista(B / "mgd")] + [(p, [], "normal") for p in lista(B / "normal")]
    escreve("mendeley_blefarite", it, "mendeley_blefarite", "web")
    # 3) zenodo normais (amostra)
    Z = RAW / "zenodo_eyearea_tr" / "Photos"; it = [(p, [], "normal") for p in lista(Z)]
    escreve("zenodo_normais", it, "zenodo_eyearea", "phone_closeup", max_por_classe=500)
    # 4) pinkeye desduplicado contra eye_diseases
    ED = RAW / "eye_diseases"; md5s = set(); dh = []
    for p in lista(ED):
        try: md5s.add(hashlib.md5(p.read_bytes()).hexdigest()); dh.append(dhash(Image.open(p)))
        except Exception: pass
    print("eye_diseases: md5", len(md5s), "dhash", len(dh), flush=True)
    PK = RAW / "hf_pinkeye" / "Multi-dataset"; it = []; dup = 0; seen = set()
    for cls, labs in (("Viral-bacterial", ["conjuntivite", "hiperemia"]), ("Allergic", ["conjuntivite", "hiperemia"]), ("Irritant-chemical", ["conjuntivite", "hiperemia"]), ("Normal", [])):
        for p in lista(PK / cls):
            try: b = p.read_bytes(); m = hashlib.md5(b).hexdigest()
            except Exception: continue
            if m in md5s or m in seen: dup += 1; continue
            seen.add(m)
            try: h = dhash(Image.open(p))
            except Exception: continue
            if any(ham(h, x) <= 6 for x in dh): dup += 1; continue
            it.append((p, labs, cls))
    print("pinkeye: duplicatas removidas", dup, "| restantes", len(it), flush=True)
    escreve("pinkeye", it, "hf_pinkeye", "web", max_por_classe=500)
if __name__ == "__main__":
    main()
