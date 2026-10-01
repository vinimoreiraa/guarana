"""Recalibra os limiares de uma versao pelo criterio de ESPECIFICIDADE no teste interno (split_<v>_test + pred_<v>_test):
por rotulo, menor limiar com especificidade >= --espec (padrao 0,92), entre piso 0,08 e teto 0,95. Guarda os limiares antigos
em `thresholds_sens90` no cartao e reescreve `thresholds`. Depois roda o teste externo em todas as fontes com os novos limiares.
Uso: .venv/bin/python treino/recalibrar_limiares.py --versao ocular_v21_e4a_realA [--espec 0.92]
"""
import argparse, json, subprocess, sys
from pathlib import Path
import numpy as np, pandas as pd
BASE = Path(__file__).resolve().parents[1]; OUT = BASE / "saida"
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--versao", required=True); ap.add_argument("--espec", type=float, default=0.92); ap.add_argument("--piso", type=float, default=0.08); ap.add_argument("--teto", type=float, default=0.95); ap.add_argument("--candidato-espec", type=float, default=0.0, help="se > 0, grava tambem thresholds_candidato com esta especificidade"); a = ap.parse_args()
    cardp = OUT / (f"{a.versao}_card.json" if (OUT / f"{a.versao}_card.json").exists() else "model_card.json"); card = json.load(open(cardp)); labels = list(card["thresholds"])
    test = pd.read_csv(OUT / f"split_{a.versao}_test.csv"); pred = pd.read_csv(OUT / f"pred_{a.versao}_test.csv").set_index("file").loc[test["file"]]
    # negativos REAIS de celular para a especificidade: metade B1 (hash) dos normais do Zenodo e do Commons; B2 fica para medir
    import hashlib
    negs = []
    for f, fonte in (("externos/labels_zenodo_normais", "zenodo"), ("labels_commons", "commons")):
        d = pd.read_csv(BASE / "dados" / f"{f}.csv"); d = d[(d["metade"] == "B") & (d[labels].sum(axis=1) == 0)]
        pr = pd.read_csv(OUT / f"pred_{a.versao}_externo_{Path(f).stem}.csv"); m = d.merge(pr, on="file")
        m["b1"] = m["subject_id"].astype(str).map(lambda s_: int(hashlib.md5(("cal" + s_).encode()).hexdigest(), 16) % 2 == 0); negs.append(m)
    negs = pd.concat(negs); cal = negs[negs["b1"]]; print(f"negativos reais para calibrar (B1): {len(cal)} | para medir (B2): {int((~negs['b1']).sum())}")
    novos = {}; linhas = []; cand = {}
    for l in labels:
        y = test[l].to_numpy(); p = pred[f"p_{l}"].to_numpy(); pos = p[y == 1]; neg = cal[f"p_{l}"].to_numpy()
        t = float(np.quantile(neg, a.espec)) if len(neg) else 0.5; t = float(min(max(t, a.piso), a.teto))
        if a.candidato_espec > 0: tc = float(np.quantile(neg, a.candidato_espec)) if len(neg) else t / 2; cand[l] = round(float(min(max(min(tc, t), a.piso), a.teto)), 4)
        sens = float((pos >= t).mean()) if len(pos) else float("nan"); esp = float((negs[~negs["b1"]][f"p_{l}"].to_numpy() < t).mean())
        novos[l] = round(t, 4); linhas.append(f"  {l:26s} {card['thresholds'][l]:.2f} -> {t:.2f} | sens teste interno {sens:.2f} | esp em normais reais B2 {esp:.2f}")
    print("\n".join(linhas))
    card["thresholds_sens90"] = card.get("thresholds_sens90", card["thresholds"]); card["thresholds"] = novos
    if cand: card["thresholds_candidato"] = cand; card["threshold_rule_candidato"] = f"especificidade >= {a.candidato_espec} nos mesmos normais reais"
    card["thresholds"] = novos; card["threshold_rule"] = f"especificidade >= {a.espec} em normais reais de celular (Zenodo+Commons, metade B1) (recalibrar_limiares.py)"
    json.dump(card, open(cardp, "w"), indent=2, ensure_ascii=False); print("cartao atualizado:", cardp.name)
    for f in ["labels_pubmed_limpo", "labels_commons", "externos/labels_mendeley_conj", "externos/labels_pinkeye", "externos/labels_mendeley_blefarite", "externos/labels_zenodo_normais", "externos/labels_cekmate_leucocoria", "externos/labels_gh_eyedis5", "externos/labels_commons_olho"]:
        subprocess.run([sys.executable, str(BASE / "treino/testar_externo.py"), "--versao", a.versao, "--csv", f"dados/{f}.csv"], capture_output=True, text=True)
    print("testes externos refeitos com os novos limiares")
if __name__ == "__main__":
    main()
