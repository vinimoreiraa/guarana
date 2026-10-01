"""Teste externo: roda o modelo publicado (saida/<versao>.onnx) com as mesmas vistas do app (centro + laterais + espelho,
max por rotulo) sobre um CSV de rotulos que NUNCA entrou no treino (por padrao dados/labels_pubmed.csv) e mede, por rotulo,
AUROC, sensibilidade no limiar do cartao e especificidade contra os recortes das outras figuras.
Ressalva: o rotulo vem da legenda da figura inteira; um painel "depois da cirurgia" herda o rotulo. E um teste externo sujo,
mas e a unica regua de campo que a internet da hoje. Uso: .venv/bin/python treino/testar_externo.py [--versao ocular_v21] [--csv dados/labels_pubmed.csv]
"""
import argparse, json, sys
from pathlib import Path
import numpy as np, onnxruntime as ort, pandas as pd
from PIL import Image
from sklearn.metrics import roc_auc_score
BASE = Path(__file__).resolve().parents[1]; OUT = BASE / "saida"

def views(im, size):
    w, h = im.size; side = int(round(min(w, h) / 1.1)); boxes = [((w - side) // 2, (h - side) // 2)]
    if w > h: boxes += [(0, (h - side) // 2), (w - side, (h - side) // 2)]
    elif h > w: boxes += [((w - side) // 2, 0), ((w - side) // 2, h - side)]
    for x0, y0 in boxes:
        v = im.crop((x0, y0, x0 + side, y0 + side)).resize((size, size), Image.BILINEAR)
        yield v; yield v.transpose(Image.FLIP_LEFT_RIGHT)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--versao", default="ocular_v21"); ap.add_argument("--csv", default="dados/labels_pubmed.csv"); a = ap.parse_args()
    card_p = OUT / "model_card.json" if json.load(open(OUT / "model_card.json"))["name"] == a.versao else OUT / f"{a.versao}_card.json"
    card = json.load(open(card_p)); inp = card["input"]; labels = list(card["thresholds"]); thr = card["thresholds"]
    size = inp.get("size", 320); mean = np.array(inp.get("mean", [0.485, 0.456, 0.406]), np.float32); std = np.array(inp.get("std", [0.229, 0.224, 0.225]), np.float32)
    sess = ort.InferenceSession(str(OUT / f"{a.versao}.onnx"), providers=["CPUExecutionProvider"]); name = sess.get_inputs()[0].name
    df = pd.read_csv(BASE / a.csv)
    if "metade" in df.columns and "--tudo" not in sys.argv: df = df[df["metade"] == "B"].reset_index(drop=True)   # so a metade de teste
    P = np.zeros((len(df), len(labels)), np.float32)
    for i, f in enumerate(df["file"]):
        im = Image.open(BASE / "dados" / f).convert("RGB")
        xs = np.stack([((np.asarray(v, np.float32) / 255 - mean) / std).transpose(2, 0, 1) for v in views(im, size)])
        lg = np.concatenate([sess.run(None, {name: x[None]})[0] for x in xs])   # lote fixo em 1 no ONNX exportado
        P[i] = (1 / (1 + np.exp(-lg))).max(axis=0)
        if i % 100 == 0: print(f"  {i}/{len(df)}", flush=True)
    pred = pd.DataFrame(P, columns=[f"p_{l}" for l in labels]).assign(file=df["file"]); pred.to_csv(OUT / f"pred_{a.versao}_externo_{Path(a.csv).stem}.csv", index=False)
    lines = [f"# Teste externo · {a.versao} · {Path(a.csv).name} · n={len(df)} recortes de {df['subject_id'].nunique()} figuras\n",
             "Positivo = legenda da figura cita o sinal; negativo = recortes das demais figuras (ruidoso). Limiar = o do cartão. Vistas como o app (max).\n",
             "| sinal | n pos | AUROC | sens | esp | média p nos pos |", "|---|---:|---:|---:|---:|---:|"]
    res = {}
    for j, l in enumerate(labels):
        if l not in df.columns: continue
        y = df[l].to_numpy().astype(int); n = int(y.sum())
        if n == 0: continue
        p = P[:, j]; t = thr[l]; auc = roc_auc_score(y, p) if 0 < n < len(y) else float("nan")
        sens = float((p[y == 1] >= t).mean()); esp = float((p[y == 0] < t).mean()) if (y == 0).any() else float("nan")
        res[l] = dict(n=n, auroc=round(float(auc), 3), sens=round(sens, 3), esp=round(esp, 3)); lines.append(f"| {l} | {n} | {auc:.3f} | {sens:.2f} | {esp:.2f} | {p[y==1].mean():.2f} |")
    # o que o app faria: quantos recortes positivos de qualquer sinal saem "sem sinais"
    anyp = (P >= np.array([thr[l] for l in labels])).any(axis=1); haspos = df[[l for l in labels if l in df.columns]].sum(axis=1) > 0
    lines.append(f"\nRecortes com algum sinal na legenda que o app daria como **sem sinais**: {int((~anyp & haspos).sum())} de {int(haspos.sum())} ({100*(~anyp & haspos).mean()/max(haspos.mean(),1e-9):.0f}%).")
    md = "\n".join(lines); (OUT / f"teste_externo_{a.versao}_{Path(a.csv).stem}.md").write_text(md); json.dump(res, open(OUT / f"teste_externo_{a.versao}_{Path(a.csv).stem}.json", "w"), indent=1)
    print(md)

if __name__ == "__main__":
    main()
