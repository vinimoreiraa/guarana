"""Wikimedia Commons -> recortes de olho com rotulo da categoria (dados/labels_commons.csv).
Reusa o separador de paineis e o gate de enquadramento de preparar_pubmed.py. Categoria 'normal' vira negativo.
Uso: .venv/bin/python treino/preparar_commons.py
"""
import csv, json, re, sys
from pathlib import Path
from PIL import Image
BASE = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(BASE / "treino"))
from preparar_pubmed import split_panels, framing, LABELS
RAW = BASE / "dados/raw/commons"; CROPS = BASE / "dados/crops/commons"; CROPS.mkdir(parents=True, exist_ok=True)
EXTRA = ["tracoma", "xantelasma", "arco_corneano", "proptose"]
SKIP = re.compile(r"(surg|histolog|microscop|fundus|oct\b|ultrasound|mri|ct scan|x-ray|drawing|diagram|illustration|painting|dog|cat\b|horse|rabbit|animal|veterinar)", re.I)
def main():
    metas = [json.loads(l) for l in (RAW / "meta.jsonl").open()]
    rows = []; seen = 0; kept = 0; skipped = 0
    for it in metas:
        p = BASE / it["file"]
        if not p.exists(): continue
        texto = (it.get("title", "") + " " + it.get("desc", "")).lower()
        if SKIP.search(texto): skipped += 1; continue
        try: im = Image.open(p).convert("RGB")
        except Exception: continue
        labels = it["labels"]
        for k, (x0, y0, x1, y1) in enumerate(split_panels(im)):
            panel = im.crop((x0, y0, x1, y1)); seen += 1
            cls, conf = framing(panel)
            if cls not in ("OK", "TOO_CLOSE", "OFF_CENTER") or conf < 0.5: continue
            out = CROPS / f"{p.stem[:80]}_p{k}.jpg"; panel.save(out, "JPEG", quality=92); kept += 1
            r = {"file": str(out.relative_to(BASE / "dados")), "subject_id": "commons_" + p.stem[:60], "source": "commons", "domain": "clinical_photo", "revisar": 1,
                 "caption": (it.get("desc", "") or it.get("title", "")).replace("\n", " ")[:500], "termos": it["category"], "enquadramento": cls, "license": it.get("license", ""), "normal": int(not labels)}
            for l in LABELS + EXTRA: r[l] = int(l in labels)
            rows.append(r)
    with (BASE / "dados/labels_commons.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "subject_id", "source", "domain", *LABELS, *EXTRA, "normal", "revisar", "caption", "termos", "enquadramento", "license"]); w.writeheader(); w.writerows(rows)
    import collections
    pos = collections.Counter(); 
    for r in rows:
        for l in LABELS + EXTRA + ["normal"]:
            if r[l]: pos[l] += 1
    print("arquivos", len(metas), "| pulados por texto", skipped, "| paineis", seen, "| recortes aceitos", kept); print(dict(pos.most_common()))
if __name__ == "__main__":
    main()
