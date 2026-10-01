"""Promove a metade A de todas as fontes externas para o treino: dados/labels_promovidas_A.csv (o treino le dados/labels*.csv).
A metade B continua sendo teste. Uso: .venv/bin/python treino/promover_metade_A.py [--sem fonte1,fonte2]
"""
import sys, glob, pandas as pd
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]; D = BASE / "dados"
LABELS = ["hiperemia","ictericia","pterigio","pinguecula","catarata_leucocoria","hemorragia_subconjuntival","lesao_pigmentada","opacidade_corneana","tumor_superficie_ocular","ceratite","cisto_conjuntival","lente_intraocular","conjuntivite","uveite","alteracao_palpebral"]
sem = set(sys.argv[sys.argv.index("--sem") + 1].split(",")) if "--sem" in sys.argv else set()
dfs = []
for f in sorted(glob.glob(str(D / "labels_pubmed_limpo.csv")) + glob.glob(str(D / "labels_commons.csv")) + glob.glob(str(D / "externos/labels_*.csv"))):
    d = pd.read_csv(f)
    if "metade" not in d.columns or Path(f).stem.replace("labels_", "") in sem: continue
    d = d[d["metade"] == "A"].copy()
    for l in LABELS:
        if l not in d.columns: d[l] = 0
    if "domain" not in d.columns: d["domain"] = "web"
    d["source"] = "A_" + d["source"].astype(str); dfs.append(d[["file", "subject_id", "source", "domain", *LABELS]]); print(Path(f).stem, len(d))
out = pd.concat(dfs, ignore_index=True); out = out[out["file"].map(lambda f: (D / f).exists())]
out.to_csv(D / "labels_promovidas_A.csv", index=False); print("promovidas:", len(out), dict(out["source"].value_counts()))
