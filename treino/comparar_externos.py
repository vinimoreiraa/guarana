"""Compara versoes do modelo em TODAS as fontes externas (so metade B): AUROC e sensibilidade por sinal e fonte,
mais o resumo (AUROC medio, positivos perdidos, negativos com alarme). Roda treino/testar_externo.py para cada par.
Uso: .venv/bin/python treino/comparar_externos.py ocular_v21 ocular_v21_e2_augbal ocular_v21_e1_gerado
Saida: saida/comparacao_externos.md
"""
import sys, json, subprocess, numpy as np, pandas as pd
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]; OUT = BASE / "saida"
FONTES = ["labels_pubmed_limpo", "labels_commons", "externos/labels_mendeley_conj", "externos/labels_pinkeye", "externos/labels_mendeley_blefarite", "externos/labels_zenodo_normais", "externos/labels_cekmate_leucocoria", "externos/labels_gh_eyedis5", "externos/labels_commons_olho"]
def main():
    versoes = sys.argv[1:] or ["ocular_v21"]; res = {}
    for v in versoes:
        for f in FONTES:
            r = subprocess.run([str(BASE / ".venv/bin/python"), str(BASE / "treino/testar_externo.py"), "--versao", v, "--csv", f"dados/{f}.csv"], capture_output=True, text=True)
            jf = OUT / f"teste_externo_{v}_{Path(f).stem}.json"
            if jf.exists(): res[(v, Path(f).stem)] = json.load(open(jf))
            md = OUT / f"teste_externo_{v}_{Path(f).stem}.md"
            perd = [l for l in md.read_text().splitlines() if "sem sinais" in l] if md.exists() else []
            res[(v, Path(f).stem)]["_perdidos"] = perd[0].split("**:")[-1].strip() if perd else "–"
            print(v, Path(f).stem, "ok" if jf.exists() else "FALHOU " + r.stderr[-200:], flush=True)
    linhas = ["# Comparação em fontes externas (metade B)\n", "Versões: " + ", ".join(versoes) + "\n"]
    for f in FONTES:
        fs = Path(f).stem; sinais = sorted({l for v in versoes for l in res.get((v, fs), {}) if not l.startswith("_")})
        linhas.append(f"\n## {fs}\n\n| sinal | " + " | ".join(f"{v} AUROC / sens (n)" for v in versoes) + " |\n|---|" + "---|" * len(versoes))
        for l in sinais:
            cells = []
            for v in versoes:
                x = res.get((v, fs), {}).get(l); cells.append(f"{x['auroc']:.2f} / {x['sens']:.2f} ({x['n']})" if x else "–")
            linhas.append(f"| {l} | " + " | ".join(cells) + " |")
        med = []
        for v in versoes:
            aucs = [x["auroc"] for k, x in res.get((v, fs), {}).items() if not k.startswith("_") and x["n"] >= 5]
            med.append(f"{np.mean(aucs):.3f} ({len(aucs)} sinais, n≥5)" if aucs else "–")
        linhas.append("| **AUROC médio** | " + " | ".join(med) + " |")
        linhas.append("| positivos que sairiam sem sinais | " + " | ".join(res.get((v, fs), {}).get("_perdidos", "–") for v in versoes) + " |")
    (OUT / "comparacao_externos.md").write_text("\n".join(linhas)); print("\n".join(linhas))
if __name__ == "__main__":
    main()
