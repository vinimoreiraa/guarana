"""Wikimedia Commons como fonte de foto clinica (licencas livres, camera variada). Lista os arquivos de categorias por sinal
(1 nivel de subcategorias, pulando cirurgia/histologia/animais/exames), baixa a versao de 1280 px e guarda licenca e autor.
Saida: dados/raw/commons/<sinal>/<arquivo>.jpg + dados/raw/commons/meta.jsonl. Uso: .venv/bin/python treino/minerar_commons.py
"""
import json, re, time, urllib.parse, urllib.request
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]; OUT = BASE / "dados/raw/commons"; OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "guarana-research/0.1 (projeto academico; contato via GitHub)"}
CATS = {  # categoria: rotulos (lista vazia = normal / negativo)
    "Pterygium (conjunctiva)": ["pterigio"], "Pinguecula": ["pinguecula"], "Conjunctivitis": ["conjuntivite", "hiperemia"], "Bacterial conjunctivitis": ["conjuntivite", "hiperemia"],
    "Allergic conjunctivitis": ["conjuntivite", "hiperemia"], "Subconjunctival hemorrhage": ["hemorragia_subconjuntival"], "Chalazion": ["alteracao_palpebral"], "Stye": ["alteracao_palpebral"],
    "Blepharitis": ["alteracao_palpebral"], "Ptosis (eyelid)": ["alteracao_palpebral"], "Jaundice": ["ictericia"], "Cataracts": ["catarata_leucocoria"], "Leukocoria": ["catarata_leucocoria"],
    "Corneal ulcer": ["ceratite", "opacidade_corneana"], "Keratitis": ["ceratite"], "Acanthamoeba keratitis": ["ceratite"], "Herpetic simplex keratitis": ["ceratite"], "Hypopyon": ["uveite"],
    "Uveitis": ["uveite"], "Anterior uveitis": ["uveite"], "Trachoma": ["tracoma"], "Trichiasis": ["alteracao_palpebral", "tracoma"], "Entropion": ["alteracao_palpebral"], "Xanthelasma": ["xantelasma"],
    "Arcus senilis": ["arco_corneano"], "Exophthalmos": ["proptose"], "Conjunctival nevus": ["lesao_pigmentada"], "Red eye (medicine)": ["hiperemia"],
    "Close-up photographs of 1 human eye": [],
}
SKIP_SUB = re.compile(r"surger|histolog|histopath|microscop|dogs|cats|animal|veterinar|mri|ct |x-ray|radiograph|ultras|oct|fundus|diagram|drawing|illustration|painting|art|video|logo|icon", re.I)
SKIP_FILE = re.compile(r"\.(svg|gif|webm|ogv|pdf|tif|tiff|djvu)$", re.I)
def api(**q):
    q.update(format="json"); u = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(q)
    for t in range(5):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))
        except Exception: time.sleep(3 + 3 * t)
    return {}
def members(cat, depth=0):
    files, subs = [], []; cont = {}
    while True:
        r = api(action="query", list="categorymembers", cmtitle="Category:" + cat, cmtype="file|subcat", cmlimit=500, **cont)
        for m in r.get("query", {}).get("categorymembers", []):
            (subs if m["ns"] == 14 else files).append(m["title"])
        if "continue" in r: cont = r["continue"]
        else: break
    if depth < 1:
        for s in subs:
            name = s.replace("Category:", "")
            if SKIP_SUB.search(name): continue
            files += members(name, depth + 1)
    return files
def info(titles):
    out = {}
    for i in range(0, len(titles), 50):
        r = api(action="query", titles="|".join(titles[i:i + 50]), prop="imageinfo", iiprop="url|extmetadata|mime|size", iiurlwidth=1280)
        for p in r.get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [None])[0]
            if ii: out[p["title"]] = ii
    return out
def main():
    meta = (OUT / "meta.jsonl").open("a"); seen = set(); n = 0
    for cat, labels in CATS.items():
        titles = [t for t in dict.fromkeys(members(cat)) if not SKIP_FILE.search(t)]
        infos = info(titles); got = 0
        d = OUT / (labels[0] if labels else "normal"); d.mkdir(exist_ok=True)
        for t in titles:
            ii = infos.get(t)
            if not ii or t in seen or not ii.get("mime", "").startswith("image/"): continue
            if ii.get("width", 0) < 300: continue
            seen.add(t); em = ii.get("extmetadata", {})
            lic = em.get("LicenseShortName", {}).get("value", ""); desc = re.sub(r"<[^>]+>", " ", em.get("ImageDescription", {}).get("value", ""))[:400]
            if re.search(r"\b(dog|cat|canine|feline|horse|cow|rabbit|bird|veterinar)\b", (desc + " " + t).lower()): continue
            fname = re.sub(r"[^A-Za-z0-9._-]+", "_", t.replace("File:", ""))[:120]; fname = re.sub(r"\.(jpe?g|png|webp)$", "", fname, flags=re.I) + ".jpg"
            dst = d / fname
            if not dst.exists():
                try:
                    req = urllib.request.Request(ii.get("thumburl") or ii["url"], headers=UA)
                    with urllib.request.urlopen(req, timeout=120) as r: dst.write_bytes(r.read())
                except Exception as e: print("  falhou", t, e); continue
            meta.write(json.dumps({"file": str(dst.relative_to(BASE)), "title": t, "category": cat, "labels": labels, "license": lic, "artist": re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", ""))[:100], "desc": desc, "url": ii["url"]}, ensure_ascii=False) + "\n")
            got += 1; n += 1; time.sleep(0.2)
        print(f"{cat:40s} listados {len(titles):4d} | baixados {got:4d}", flush=True)
    print("total", n)
if __name__ == "__main__":
    main()
