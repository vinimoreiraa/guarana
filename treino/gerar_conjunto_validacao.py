"""Monta validacao/conjunto/ (imagens + manifest.csv) para o harness do aparelho a partir do split de TESTE do modelo
(nunca visto no treino) mais faixas dos dois olhos do CFD (esperado: enquadramento TWO_EYES).
manifest.csv: file;labels;triage;framing  (labels separados por |; triage pela mesma regra do app; framing so quando conhecido)
Uso: .venv/bin/python treino/gerar_conjunto_validacao.py [--n 60] [--versao ocular_v2]
"""
import argparse, csv, json, shutil, random
from pathlib import Path
import pandas as pd
BASE = Path(__file__).resolve().parents[1]
URGENTE = {"ceratite", "uveite"}
ENCAMINHAR = {"lesao_pigmentada", "catarata_leucocoria", "ictericia", "opacidade_corneana", "pterigio", "tumor_superficie_ocular"}
OBSERVAR = {"hiperemia", "hemorragia_subconjuntival", "pinguecula", "conjuntivite", "cisto_conjuntival", "alteracao_palpebral"}
def triage(labels):
    if labels & URGENTE: return "encaminhar_urgente"
    if labels & ENCAMINHAR: return "encaminhar"
    if labels & OBSERVAR: return "observar"
    return "sem_sinais"
ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=60); ap.add_argument("--versao", default="ocular_v21"); a = ap.parse_args()
card = json.load(open(BASE / "saida/model_card.json")); labels = card["output"]["labels"]
test = pd.read_csv(BASE / f"saida/split_{a.versao}_test.csv")
out = BASE / "validacao/conjunto"; shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
rng = random.Random(3)
# estratifica: metade positivos variados, metade negativos, so dominios proximos de foto (web, phone_closeup, slit_lamp)
test = test[test["domain"].isin(["web", "phone_closeup", "slit_lamp", "external_camera"])]
pos = test[test[labels].sum(axis=1) > 0].sample(min(a.n // 2, int((test[labels].sum(axis=1) > 0).sum())), random_state=3)
neg = test[test[labels].sum(axis=1) == 0].sample(min(a.n - len(pos), int((test[labels].sum(axis=1) == 0).sum())), random_state=3)
rows = []
for _, r in pd.concat([pos, neg]).iterrows():
    src = BASE / "dados" / r["file"]; name = f"{r['source']}_{Path(r['file']).stem}.jpg"[:80]
    shutil.copy(src, out / name)
    labs = {l for l in labels if int(r[l]) == 1}
    rows.append({"file": name, "labels": "|".join(sorted(labs)), "triage": triage(labs), "framing": ""})
# faixas com os dois olhos (CFD): esperado TWO_EYES, sem rotulo de sinal
bands = sorted((BASE / "dados/raw/periorbital/extract/periorbital_dataset").rglob("*_crop.jpg"))
for p in rng.sample(bands, min(10, len(bands))):
    name = "cfd_band_" + p.name; shutil.copy(p, out / name)
    rows.append({"file": name, "labels": "", "triage": "sem_sinais", "framing": "TWO_EYES"})
with (out / "manifest.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["file", "labels", "triage", "framing"], delimiter=";"); w.writeheader(); w.writerows(rows)
print(f"{len(rows)} imagens em {out} (positivas {len(pos)}, negativas {len(neg)}, faixas 2 olhos {len(rows) - len(pos) - len(neg)})")
