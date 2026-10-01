"""Marca no model card quais rotulos tem validacao em foto comum (web/celular) e quais so viram lampada de fenda.
Regra: rotulo confiavel em foto comum precisa de >= MIN_WEB positivos de treino nos dominios web/phone_closeup/
external_camera/face_crop E AUROC de teste nesses dominios quando mensuravel. Os demais entram em
`unreliable_labels` (o app mostra "pouca validacao em foto comum") e `domain_positives` documenta a base de cada um.
Uso: .venv/bin/python treino/marcar_confiabilidade.py [--versao ocular_v21] [--min 40]
"""
import argparse, json
from pathlib import Path
import pandas as pd
BASE = Path(__file__).resolve().parents[1]; OUT = BASE / "saida"
FOTO = {"web", "phone_closeup", "external_camera", "face_crop"}
ap = argparse.ArgumentParser(); ap.add_argument("--versao", default="ocular_v21"); ap.add_argument("--min", type=int, default=40); a = ap.parse_args()
card = json.load(open(OUT / "model_card.json")); labels = card["output"]["labels"]
train = pd.read_csv(OUT / f"split_{a.versao}_train.csv"); test = pd.read_csv(OUT / f"split_{a.versao}_test.csv")
dom = {}
for l in labels:
    web = int(train[train["domain"].isin(FOTO)][l].sum()); slit = int(train[train["domain"] == "slit_lamp"][l].sum())
    tweb = int(test[test["domain"].isin(FOTO)][l].sum())
    dom[l] = {"treino_foto_comum": web, "treino_lampada_fenda": slit, "teste_foto_comum": tweb}
unrel = sorted(set(card.get("unreliable_labels", [])) | {l for l, v in dom.items() if v["treino_foto_comum"] < a.min})
card["domain_positives"] = dom; card["unreliable_labels"] = unrel
card["unreliable_note"] = f"rotulos com menos de {a.min} positivos de treino em foto comum (web/celular): o desempenho medido vale para lampada de fenda, nao para a camera do tablet"
json.dump(card, open(OUT / "model_card.json", "w"), indent=2, ensure_ascii=False)
print(f"{'rotulo':26s} {'foto comum':>10s} {'fenda':>6s} {'teste foto':>10s}  confiavel em foto comum?")
for l, v in dom.items(): print(f"{l:26s} {v['treino_foto_comum']:10d} {v['treino_lampada_fenda']:6d} {v['teste_foto_comum']:10d}  {'sim' if l not in unrel else 'NAO'}")
print("unreliable_labels:", unrel)
