"""Fonte nova por busca de imagens (DuckDuckGo, sem chave): termos por sinal em pt/es/en, download, desduplicacao contra tudo
que ja temos (md5 + dHash<=6) e entre si, gate de enquadramento + segmentador (iris e fenda plausiveis). Rotulo = sinal do termo
(ruidoso, como eye_diseases/pinkeye). Saida: dados/raw/busca_web/<sinal>/ e dados/externos/labels_busca_web.csv (metade A/B).
Uso: .venv/bin/python treino/minerar_busca.py [--por-termo 80]
"""
import argparse, hashlib, json, sys, time, io, csv, math
from pathlib import Path
import numpy as np, pandas as pd, urllib.request, onnxruntime as ort
from PIL import Image, ImageOps
BASE = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(BASE / "treino"))
from preparar_novas_fontes import dhash, ham, lista, LABELS, RAW
from preparar_pubmed import framing
OUT = RAW / "busca_web"; OUT.mkdir(parents=True, exist_ok=True)
TERMOS = {
 "ictericia": ["jaundice eyes", "yellow eyes jaundice", "scleral icterus", "icterus eye close up", "yellow sclera liver", "jaundice newborn eyes", "hepatitis yellow eyes", "icterícia olhos", "olhos amarelos icterícia", "esclera amarelada", "ictericia ojos", "ojos amarillos hepatitis", "ictère yeux jaunes", "jaundice eyes adult photo", "yellowing of the whites of the eyes"],
 "conjuntivite": ["conjunctivitis eye", "pink eye", "viral conjunctivitis", "bacterial conjunctivitis discharge", "allergic conjunctivitis eye", "adenovirus conjunctivitis", "conjuntivite", "conjuntivite viral olho", "conjuntivite bacteriana secreção", "conjuntivitis", "ojo rojo conjuntivitis", "conjonctivite oeil"],
 "pterigio": ["pterygium", "pterygium eye", "pterygium red eye", "pterygium large", "pterygium cornea", "nasal pterygium", "pterygium surfer's eye", "pterígio", "pterígio olho", "carne no olho pterígio", "pterigión", "carnosidad ojo", "ptérygion oeil"],
 "catarata_leucocoria": ["mature cataract eye", "white cataract pupil", "hypermature cataract", "cataract eye close up", "catarata olho", "catarata madura", "catarata ojo blanco", "cataracte oeil", "leukocoria", "white pupil child photo", "retinoblastoma white reflex", "congenital cataract baby eye", "leucocoria", "reflexo branco olho criança"],
 "ceratite": ["corneal ulcer", "corneal ulcer eye photo", "bacterial keratitis", "fungal keratitis", "keratitis eye", "corneal infiltrate", "herpes keratitis", "úlcera de córnea", "ceratite", "úlcera corneal", "queratitis", "ulcère cornéen"],
 "hemorragia_subconjuntival": ["subconjunctival hemorrhage", "subconjunctival haemorrhage", "broken blood vessel eye", "burst blood vessel in eye", "blood in white of eye", "hemorragia subconjuntival", "derrame no olho", "vaso estourado no olho", "hiposfagma", "derrame ocular", "hémorragie sous-conjonctivale"],
 "alteracao_palpebral": ["chalazion", "chalazion eyelid", "stye eyelid", "hordeolum", "blepharitis eyelid", "eyelid swelling stye", "ptosis eyelid", "entropion", "ectropion", "trichiasis", "calázio", "terçol", "blefarite", "chalazión párpado", "orzuelo"],
 "uveite": ["uveitis eye", "anterior uveitis", "iritis red eye", "hypopyon", "ciliary flush", "uveitis red eye photo", "uveíte", "hipópio", "uveítis anterior", "iritis ojo"],
 "trauma_ocular": ["eye injury", "corneal foreign body", "foreign body eye", "chemical eye burn", "eye trauma bruise", "hyphema", "corneal abrasion eye", "black eye injury", "corpo estranho no olho", "queimadura química olho", "trauma ocular", "hifema", "cuerpo extraño ojo", "quemadura ocular química"],
 "celulite_orbitaria": ["periorbital cellulitis", "orbital cellulitis", "preseptal cellulitis child", "swollen eyelid infection", "dacryocystitis", "celulite periorbitária", "celulite orbitária", "celulitis periorbitaria", "dacriocistite"],
 "hanseniase_ocular": ["leprosy eye", "lagophthalmos", "lagophthalmos leprosy", "madarosis", "madarosis leprosy eyebrow", "facial palsy eye cannot close", "hanseníase olho", "lagoftalmo", "madarose", "lepra ojo"],
 "palidez_conjuntival": ["conjunctival pallor", "pale conjunctiva anemia", "anemia eyelid pale", "lower eyelid pallor anemia", "palidez conjuntival", "anemia pálpebra pálida", "palidez conjuntival anemia"],
 "tracoma": ["trachoma", "trachomatous trichiasis", "trachoma eyelid", "trachoma follicles", "tracoma", "triquíase tracomatosa"],
 "normal": ["healthy eye close up photo", "eye close up stock photo", "brown eye close up", "blue eye close up", "green eye macro photography", "elderly eye close up", "child eye close up", "asian eye close up", "african eye close up photo", "olho humano de perto", "ojo humano de cerca", "beautiful eye macro", "eye makeup close up", "man eye close up", "teenager eye close up"],
}
TERMOS_EXTRA = {
 "hemorragia_subconjuntival": ["subconjunctival hemorrhage close up", "red spot on white of eye", "eye blood spot after coughing", "subconjunctival bleeding elderly", "eye hemorrhage photo", "sangue no branco do olho", "mancha vermelha no olho", "hemorragia subconjuntival foto", "mancha de sangre en el ojo", "subconjunctival hemorrhage newborn"],
 "trauma_ocular": ["corneal foreign body metal", "rust ring cornea", "eye injury emergency photo", "traumatic hyphema photo", "chemical burn eye limbal ischemia", "alkali burn eye", "eyelid laceration", "penetrating eye injury", "ferimento no olho", "lesão ocular trauma foto", "trauma ocular cuerpo extraño", "orbital fracture black eye"],
 "ceratite": ["corneal ulcer close up", "infected cornea white spot", "contact lens corneal ulcer", "acanthamoeba keratitis", "fungal corneal ulcer farmer", "dendritic ulcer", "corneal abscess", "úlcera de córnea fungo", "ceratite bacteriana foto", "úlcera corneal bacteriana"],
 "uveite": ["acute anterior uveitis eye", "hypopyon uveitis photo", "iritis eye photo", "ciliary injection eye", "posterior synechiae pupil", "uveíte olho vermelho foto", "irite olho", "uveítis ojo rojo", "toxoplasmosis uveitis eye", "HLA-B27 uveitis eye"],
 "ictericia": ["yellow eyes hepatitis patient", "jaundiced sclera close up", "liver failure yellow eyes", "neonatal jaundice yellow sclera", "icterícia neonatal olhos", "olho amarelo hepatite", "ojos amarillos ictericia neonatal", "sclera yellow discoloration"],
 "celulite_orbitaria": ["orbital cellulitis child eye", "periorbital cellulitis swollen eye", "preseptal cellulitis", "eyelid abscess", "swollen eye infection child", "celulite periorbital criança", "olho inchado infecção", "celulitis orbitaria niño", "dacryocystitis swelling", "orbital abscess proptosis"],
 "hanseniase_ocular": ["leprosy lagophthalmos", "leprosy eye complications", "madarosis eyebrows leprosy", "lepromatous leprosy face eyes", "facial nerve palsy lagophthalmos", "exposure keratopathy lagophthalmos", "hanseníase olho lagoftalmo", "hanseníase madarose", "lepra lagoftalmos", "Bell's palsy eye cannot close"],
 "hiperemia": ["bloodshot eyes close up", "red eyes irritation", "dry eye redness", "episcleritis", "scleritis red eye", "olho vermelho irritado", "olhos vermelhos cansaço", "ojos rojos irritados"],
}
TERMOS.update({k: v for k, v in TERMOS_EXTRA.items() if k not in TERMOS})

SEG = json.load(open(BASE / "saida/fenda_card.json")); SS = SEG["input"]["size"]; SM, SD = np.array(SEG["input"]["mean"], np.float32), np.array(SEG["input"]["std"], np.float32)
seg = ort.InferenceSession(str(BASE / "saida/fenda_v1.onnx"), providers=["CPUExecutionProvider"])
def plausivel(im):
    c, conf = framing(im)
    if c not in ("OK", "TOO_CLOSE", "OFF_CENTER") or conf < 0.5: return None
    w, h = im.size; x = ((np.asarray(im.resize((SS, SS), Image.BILINEAR), np.float32) / 255 - SM) / SD).transpose(2, 0, 1)[None]; pr = 1 / (1 + np.exp(-seg.run(None, {"image": x})[0][0]))
    fen = pr[0] > 0.5; iri = pr[1] > 0.5
    if iri.sum() < 60 or fen.sum() < 1.15 * iri.sum(): return None
    return c
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--por-termo", type=int, default=80); ap.add_argument("--sinais", default=""); ap.add_argument("--extra", action="store_true"); a = ap.parse_args()
    if a.extra:
        for k, v in TERMOS_EXTRA.items(): TERMOS[k] = v
    from ddgs import DDGS
    # indice de hashes do que ja temos
    md5s = set(); dh = []
    for d in ("eye_diseases", "hf_pterygium", "hf_jaundice", "hf_pinkeye", "mendeley_conj_lesoes", "mendeley_blefarite", "commons", "commons_olho", "cekmate_leucocoria", "gh_eyedis5", "zenodo_eyearea_tr", "busca_web"):
        for p in lista(RAW / d)[:6000]:
            try: b = p.read_bytes(); md5s.add(hashlib.md5(b).hexdigest()); dh.append(dhash(Image.open(io.BytesIO(b))))
            except Exception: pass
    print("hashes existentes:", len(md5s), flush=True)
    rows = []; vistos_md5 = set(); vistos_dh = []; UA = {"User-Agent": "Mozilla/5.0 (Macintosh) guarana-research/0.1"}
    for sinal, termos in TERMOS.items():
        if a.sinais and sinal not in a.sinais.split(","): continue
        d = OUT / sinal; d.mkdir(exist_ok=True); n_ok = 0
        for termo in termos:
            res = []
            for be in ("bing", "duckduckgo"):
                try: res += DDGS().images(termo, max_results=a.por_termo, backend=be)
                except Exception as e: print(f"  {be} falhou {termo}: {str(e)[:60]}", flush=True)
            urls = list(dict.fromkeys(r.get("image") or "" for r in res if r.get("image")))
            from concurrent.futures import ThreadPoolExecutor
            def baixa(url):
                try:
                    req = urllib.request.Request(url, headers=UA)
                    with urllib.request.urlopen(req, timeout=10) as resp: return url, resp.read(12_000_000)
                except Exception: return url, None
            with ThreadPoolExecutor(16) as ex: baixados = list(ex.map(baixa, urls))
            for url, b in baixados:
                if not b: continue
                try: im = ImageOps.exif_transpose(Image.open(io.BytesIO(b))).convert("RGB")
                except Exception: continue
                if min(im.size) < 200: continue
                m = hashlib.md5(b).hexdigest()
                if m in md5s or m in vistos_md5: continue
                h = dhash(im)
                if any(ham(h, x) <= 6 for x in dh) or any(ham(h, x) <= 6 for x in vistos_dh): continue
                if max(im.size) > 1400: im.thumbnail((1400, 1400))
                c = plausivel(im)
                if c is None: continue
                vistos_md5.add(m); vistos_dh.append(h); fn = d / f"{m[:12]}.jpg"; im.save(fn, "JPEG", quality=92); n_ok += 1
                rows.append({"file": str(fn.relative_to(BASE / "dados")), "subject_id": f"web_{m[:12]}", "source": "busca_web", "domain": "web", **{l: int(l == sinal) for l in LABELS}, "classe": sinal, "termo": termo, "url": url, "enquadramento": c, "metade": "A" if int(m, 16) % 2 == 0 else "B"})
            print(f"  {sinal:26s} {termo[:40]:40s} -> acumulado {n_ok}", flush=True); time.sleep(2)
        print(f"{sinal}: {n_ok} imagens", flush=True)
        _csv = BASE / "dados/externos/labels_busca_web.csv"; _old = pd.read_csv(_csv) if _csv.exists() else pd.DataFrame()
        pd.concat([_old, pd.DataFrame(rows)]).drop_duplicates("file").to_csv(_csv, index=False); rows = []
    saida_csv = BASE / "dados/externos/labels_busca_web.csv"
    if saida_csv.exists(): rows = pd.read_csv(saida_csv).to_dict("records") + rows
    with saida_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "subject_id", "source", "domain", *LABELS, "classe", "termo", "url", "enquadramento", "metade"]); w.writeheader(); w.writerows(rows)
    import collections; print("total", len(rows), dict(collections.Counter(r["classe"] for r in rows)))
if __name__ == "__main__":
    main()
