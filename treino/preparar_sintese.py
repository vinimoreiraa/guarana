"""Junta os lotes do Blender (sintese/render/<lote>/s*/labels.csv) num CSV de treino dados/labels_sintese.csv,
com caminhos relativos a dados/ e dominio 'synthetic'. So entra no treino com OCULAR_USE_SINTESE=1.
Uso: .venv/bin/python treino/preparar_sintese.py [lote1]
"""
import sys, pandas as pd
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]; lote = sys.argv[1] if len(sys.argv) > 1 else "lote1"
LABELS = ["hiperemia","ictericia","pterigio","pinguecula","catarata_leucocoria","hemorragia_subconjuntival","lesao_pigmentada","opacidade_corneana",
          "tumor_superficie_ocular","ceratite","cisto_conjuntival","lente_intraocular","conjuntivite","uveite","alteracao_palpebral"]
dfs = []
for csv in sorted((BASE / "sintese/render" / lote).glob("s*/labels.csv")):
    d = pd.read_csv(csv); d["file"] = d["file"].map(lambda f: str(Path("..") / "sintese/render" / lote / csv.parent.name / f))
    d = d[d["file"].map(lambda f: (BASE / "dados" / f).exists())]; dfs.append(d)
df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
if len(df):
    df["source"] = "sintese_blender"; df["domain"] = "synthetic"; df["subject_id"] = "sint_" + df["subject_id"]
    df[["file", "subject_id", "source", "domain", *LABELS, "sinal"]].to_csv(BASE / "dados/labels_sintese.csv", index=False)
    print(len(df), "imagens sinteticas |", df["sinal"].value_counts().to_dict()); print(df[LABELS].sum()[lambda s: s > 0].to_dict())
else: print("nada renderizado ainda")
