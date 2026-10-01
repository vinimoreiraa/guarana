"""Fontes do grupo B -> CSVs de teste externo em dados/externos/ (metade A/B por sujeito):
- cekmate_leucocoria (Leukocoria/Normal, fotos de crianca com flash) -> catarata_leucocoria
- hf_retinoblastoma (rr/healthy, 224 px) -> catarata_leucocoria
- gh_eyedis5 (Cataracts, Uveitis; Glaucoma/Bulging/Crossed ignorados) -> catarata_leucocoria, uveite+hiperemia
- commons_olho (commons_meta.csv, coluna sinais separada por ;) -> rotulos do app, desduplicado por titulo contra dados/raw/commons/meta.jsonl
Uso: .venv/bin/python treino/preparar_fontes_B.py
"""
import sys, json, hashlib, csv, re
from pathlib import Path
import pandas as pd
BASE = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(BASE / "treino"))
from preparar_novas_fontes import escreve, lista, LABELS, RAW, OUT
def metade(df):
    df["metade"] = df["subject_id"].astype(str).map(lambda s: "A" if int(hashlib.md5(s.encode()).hexdigest(), 16) % 2 == 0 else "B"); return df
def main():
    C = RAW / "cekmate_leucocoria"; it = []
    for split in ("Training", "Validation"):
        it += [(p, ["catarata_leucocoria"], "leucocoria") for p in lista(C / split / "Leukocoria")] + [(p, [], "normal") for p in lista(C / split / "Normal")]
    escreve("cekmate_leucocoria", it, "cekmate", "web")
    R = RAW / "hf_retinoblastoma"; it = [(p, ["catarata_leucocoria"], "leucocoria") for p in lista(R / "rr")] + [(p, [], "normal") for p in lista(R / "healthy")]
    escreve("hf_retinoblastoma", it, "hf_retinoblastoma", "web")
    E = RAW / "gh_eyedis5" / "Original_Dataset"; it = [(p, ["catarata_leucocoria"], "catarata") for p in lista(E / "Cataracts")] + [(p, ["uveite", "hiperemia"], "uveite") for p in lista(E / "Uveitis")]
    escreve("gh_eyedis5", it, "gh_eyedis5", "web")
    # commons_olho
    meta = pd.read_csv(RAW / "commons_olho" / "commons_meta.csv"); ja = set()
    mj = RAW / "commons" / "meta.jsonl"
    if mj.exists(): ja = {json.loads(l)["title"] for l in mj.open()}
    it = []; skip = re.compile(r"(surg|histolog|microscop|fundus|oct\b|ultrasound|mri|ct scan|x-ray|drawing|diagram|illustration|painting|dog|cat\b|horse|rabbit|animal|veterinar)", re.I)
    for _, r in meta.iterrows():
        if str(r.get("status", "")).lower().startswith(("fal", "err")) or r["titulo"] in ja: continue
        p = RAW / "commons_olho" / "img" / str(r["arquivo"])
        if not p.exists() or skip.search(str(r["titulo"]) + " " + str(r.get("descricao", ""))): continue
        labs = [l.strip() for l in str(r.get("sinais", "")).replace(",", ";").split(";") if l.strip() in LABELS]
        it.append((p, labs, labs[0] if labs else "outros"))
    escreve("commons_olho", it, "commons_olho", "clinical_photo")
    for nome in ("cekmate_leucocoria", "hf_retinoblastoma", "gh_eyedis5", "commons_olho"):
        f = OUT / f"labels_{nome}.csv"; d = metade(pd.read_csv(f)); d.to_csv(f, index=False); print(nome, dict(d["metade"].value_counts()))
if __name__ == "__main__":
    main()
