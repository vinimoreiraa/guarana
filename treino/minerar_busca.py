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
 "pterigio": ["pterygium", "pterygium eye", "pterygium red eye", "pterygium large", "pterygium eye photo", "pterygium vascular wing eye", "pterígio olho foto", "pterigión ojo foto", "carnosidad en el ojo", "surfer's eye pterygium", "pterygium nasal conjunctiva", "pterygium before surgery eye"],
 "pinguecula": ["pinguecula eye photo", "pinguécula olho", "pinguécula ojo"],
 "hemorragia_subconjuntival": ["subconjunctival hemorrhage eye", "hemorragia subconjuntival olho", "derrame ocular hemorragia subconjuntival", "hiposfagma"],
 "ictericia": ["jaundice eyes yellow sclera", "icterícia olhos amarelos", "ictericia ojos amarillos escleras", "scleral icterus photo"],
 "conjuntivite": ["conjunctivitis eye photo", "conjuntivite olho vermelho", "conjuntivitis ojo rojo", "pink eye adult photo"],
 "hiperemia": ["red eye bloodshot close up", "olho vermelho irritado foto", "ojo rojo irritado foto", "episcleritis eye photo", "escleritis ojo foto"],
 "catarata_leucocoria": ["mature cataract white pupil photo", "catarata madura pupila branca foto", "catarata madura pupila blanca foto", "leukocoria child eye photo", "leucocoria criança foto"],
 "ceratite": ["corneal ulcer eye photo", "úlcera de córnea foto", "úlcera corneal foto", "bacterial keratitis eye", "fungal keratitis eye photo", "ceratite olho foto"],
 "uveite": ["anterior uveitis eye photo ciliary flush", "uveíte anterior olho foto", "uveítis anterior ojo foto", "hypopyon eye photo", "iritis red eye photo"],
 "opacidade_corneana": ["corneal opacity eye photo", "corneal scar leukoma eye", "leucoma corneano foto", "leucoma corneal ojo"],
 "alteracao_palpebral": ["chalazion eyelid photo", "calázio pálpebra foto", "chalazión párpado foto", "hordeolum stye eyelid photo", "terçol foto", "orzuelo foto", "blepharitis eyelid photo", "blefarite foto", "ptosis eyelid photo adult"],
 "lesao_pigmentada": ["conjunctival nevus eye photo", "nevo conjuntival foto", "nevus conjuntival foto", "conjunctival melanoma photo"],
 "tumor_superficie_ocular": ["ocular surface squamous neoplasia photo", "conjunctival tumor eye photo", "conjunctival papilloma photo"],
 "normal": ["healthy eye close up photo", "olho saudável foto close", "ojo sano foto de cerca", "human eye macro photo brown", "eye close up dark skin", "olho de perto criança", "beautiful eye macro", "eye close up stock photo", "brown eye close up", "blue eye close up", "green eye macro photography", "elderly eye close up", "child eye close up", "asian eye close up", "african eye close up photo"],
}
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
    ap = argparse.ArgumentParser(); ap.add_argument("--por-termo", type=int, default=80); ap.add_argument("--sinais", default=""); a = ap.parse_args()
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
            try:
                with DDGS() as dd: res = list(dd.images(termo, max_results=a.por_termo))
            except Exception as e: print("  busca falhou", termo, e, flush=True); time.sleep(5); continue
            for r in res:
                url = r.get("image") or ""
                if not url.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png", ".webp")) and "image" not in url.lower(): pass
                try:
                    req = urllib.request.Request(url, headers=UA)
                    with urllib.request.urlopen(req, timeout=15) as resp: b = resp.read(12_000_000)
                    im = ImageOps.exif_transpose(Image.open(io.BytesIO(b))).convert("RGB")
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
            print(f"  {sinal:26s} {termo[:40]:40s} -> acumulado {n_ok}", flush=True); time.sleep(1.5)
        print(f"{sinal}: {n_ok} imagens", flush=True)
    saida_csv = BASE / "dados/externos/labels_busca_web.csv"
    if saida_csv.exists() and a.sinais: rows = pd.read_csv(saida_csv).to_dict("records") + rows
    with saida_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "subject_id", "source", "domain", *LABELS, "classe", "termo", "url", "enquadramento", "metade"]); w.writeheader(); w.writerows(rows)
    import collections; print("total", len(rows), dict(collections.Counter(r["classe"] for r in rows)))
if __name__ == "__main__":
    main()
