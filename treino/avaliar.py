"""Avaliacao offline e reprodutivel do que vai para o aparelho, sem tirar foto nenhuma:
1. roda o ONNX exportado (nao o modelo torch) sobre o conjunto de teste, com o MESMO pre-processamento do app
   (lado menor -> 352, recorte central 320, /255, normalizacao ImageNet);
2. compara com as predicoes do torch (paridade da exportacao);
3. metricas por sinal com os limiares do cartao (sensibilidade, especificidade, AUROC) e por dominio;
4. triagem: aplica a regra do app (Triage.decide) e mede a concordancia com a triagem "esperada" pelos rotulos;
5. gate de enquadramento (se saida/enquadramento_v1.onnx existir): distribuicao das decisoes no mesmo conjunto.
Escreve saida/avaliacao_<versao>.json e .md. Uso: .venv/bin/python treino/avaliar.py [--versao ocular_v2] [--n 400]
"""
import argparse, json, datetime
from pathlib import Path
import numpy as np, pandas as pd, onnxruntime as ort
from PIL import Image
from sklearn.metrics import roc_auc_score

BASE = Path(__file__).resolve().parents[1]; OUT = BASE / "saida"; DADOS = BASE / "dados"
URGENTE = {"ceratite", "uveite"}
ENCAMINHAR = {"lesao_pigmentada", "catarata_leucocoria", "ictericia", "opacidade_corneana", "pterigio_pinguecula", "pterigio", "tumor_superficie_ocular",
              "esclera_azul", "manchas_bitot", "ocronose", "telangiectasia", "palidez_conjuntival", "arco_corneano"}
OBSERVAR = {"hiperemia", "hemorragia_subconjuntival", "pinguecula", "conjuntivite", "cisto_conjuntival", "alteracao_palpebral"}

def triage(present, candidate=()):
    if present & URGENTE: return "encaminhar_urgente"
    if present & ENCAMINHAR: return "encaminhar"
    if present & OBSERVAR: return "observar"
    if candidate: return "observar"
    return "sem_sinais"

def preprocess(path, size, mean, std, tta=False):
    """tta=False: recorte central (app ate v2). tta=True: as vistas do app v2.1 (centro, laterais, espelho), batch [V,3,S,S]."""
    im = Image.open(path).convert("RGB")
    if not tta:
        target = int(size * 1.1); s = target / min(im.size)
        im = im.resize((max(size, round(im.width * s)), max(size, round(im.height * s))), Image.BILINEAR)
        x0 = (im.width - size) // 2; y0 = (im.height - size) // 2
        a = np.asarray(im.crop((x0, y0, x0 + size, y0 + size)), dtype=np.float32) / 255.0
        return ((a - mean) / std).transpose(2, 0, 1)[None].astype(np.float32)
    w, h = im.size; side = int(round(min(w, h) * size / (size * 1.1)))
    boxes = [((w - side) // 2, (h - side) // 2)]
    if w > h: boxes += [(0, (h - side) // 2), (w - side, (h - side) // 2)]
    elif h > w: boxes += [((w - side) // 2, 0), ((w - side) // 2, h - side)]
    out = []
    for x0, y0 in boxes:
        c = im.crop((x0, y0, x0 + side, y0 + side)).resize((size, size), Image.BILINEAR)
        for v in (c, c.transpose(Image.FLIP_LEFT_RIGHT)):
            a = np.asarray(v, dtype=np.float32) / 255.0; out.append(((a - mean) / std).transpose(2, 0, 1))
    return np.stack(out).astype(np.float32)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--versao", default="ocular_v21"); ap.add_argument("--n", type=int, default=0)
    ap.add_argument("--tta", action="store_true", help="vistas multiplas como o app v2.1 (max entre vistas)")
    ap.add_argument("--casos", default="validacao/casos", help="pasta com casos dificeis reais + manifest.csv (regressao por imagem)"); a = ap.parse_args()
    card = json.load(open(OUT / "model_card.json")); labels = card["output"]["labels"]; thr = card["thresholds"]
    size = card["input"]["shape"][-1]; mean = np.array(card["input"]["mean"], np.float32); std = np.array(card["input"]["std"], np.float32)
    test = pd.read_csv(OUT / f"split_{a.versao}_test.csv"); pred_torch = pd.read_csv(OUT / f"pred_{a.versao}_test.csv").set_index("file")
    if a.n: test = test.sample(min(a.n, len(test)), random_state=0)
    sess = ort.InferenceSession(str(OUT / card["files"]["fp32"]), providers=["CPUExecutionProvider"])
    enq = OUT / "enquadramento_v1.onnx"; enq_sess = ort.InferenceSession(str(enq), providers=["CPUExecutionProvider"]) if enq.exists() else None
    enq_card = json.load(open(OUT / "enquadramento_card.json")) if enq_sess else None
    P, Y, parity, enq_dec, cam_ok = [], [], [], [], 0
    for _, r in test.iterrows():
        f = DADOS / r["file"] if not str(r["file"]).startswith("/") else Path(r["file"])
        x = preprocess(f, size, mean, std, tta=a.tta)
        if a.tta:
            ps = np.stack([1 / (1 + np.exp(-sess.run(None, {"image": x[k:k + 1]})[0][0])) for k in range(len(x))]); p = ps.max(0); outs = [ps]
        else:
            outs = sess.run(None, {"image": x}); logits = outs[0][0]; p = 1 / (1 + np.exp(-logits))
        P.append(p); Y.append([int(r[l]) for l in labels])
        if len(outs) > 1 and getattr(outs[1], "shape", (0, 0))[1:2] == (len(labels),): cam_ok += 1
        if r["file"] in pred_torch.index: parity.append(np.abs(p - pred_torch.loc[r["file"], [f"p_{l}" for l in labels]].to_numpy(dtype=np.float32)).max())
        if enq_sess:
            im = Image.open(f).convert("L"); s = min(im.size); im = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width - s) // 2 + s, (im.height - s) // 2 + s)).resize((enq_card["input"]["size"],) * 2, Image.BILINEAR)
            g = ((np.asarray(im, np.float32) / 255 - enq_card["input"]["mean"]) / enq_card["input"]["std"])[None].repeat(3, 0)[None]
            enq_dec.append(enq_card["classes"][int(np.argmax(enq_sess.run(None, {"image": g})[0]))])
    P, Y = np.array(P), np.array(Y)
    rows = []
    for j, l in enumerate(labels):
        y, p = Y[:, j], P[:, j]; pred = p >= thr[l]
        tp = int(((y == 1) & pred).sum()); fn = int(((y == 1) & ~pred).sum()); tn = int(((y == 0) & ~pred).sum()); fp = int(((y == 0) & pred).sum())
        auc = float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else float("nan")
        rows.append({"sinal": l, "n_pos": int(y.sum()), "auroc": round(auc, 3), "limiar": round(thr[l], 3),
                     "sensibilidade": round(tp / max(tp + fn, 1), 3), "especificidade": round(tn / max(tn + fp, 1), 3), "fp": fp, "fn": fn})
    # triagem esperada (rotulos) x triagem obtida (predicoes com limiar; candidato = p >= limiar/2)
    conf = {}; agree = 0
    for i in range(len(P)):
        exp_t = triage({l for j, l in enumerate(labels) if Y[i, j] == 1})
        present = {l for j, l in enumerate(labels) if P[i, j] >= thr[l]}; cand = {l for j, l in enumerate(labels) if thr[l] / 2 <= P[i, j] < thr[l] and P[i, j] >= 0.05}
        got = triage(present, cand); conf[(exp_t, got)] = conf.get((exp_t, got), 0) + 1; agree += exp_t == got
    # por dominio
    dom = {}
    for d, idx in test.reset_index(drop=True).groupby("domain").indices.items():
        aucs = {l: round(float(roc_auc_score(Y[idx, j], P[idx, j])), 2) for j, l in enumerate(labels) if 0 < Y[idx, j].sum() < len(idx)}
        dom[d] = {"n": int(len(idx)), "auroc": aucs}
    rep = {"versao": a.versao, "tta": a.tta, "data": datetime.datetime.now().isoformat(timespec="seconds"), "n_teste": int(len(P)), "onnx": card["files"]["fp32"],
           "paridade_max_diff_torch_onnx": round(float(max(parity)) if parity else -1, 5), "cam_presente_em": cam_ok,
           "por_sinal": rows, "triagem_concordancia": round(agree / len(P), 3), "triagem_confusao": {f"{k[0]}->{k[1]}": v for k, v in sorted(conf.items())},
           "por_dominio": dom, "enquadramento": ({k: enq_dec.count(k) for k in sorted(set(enq_dec))} if enq_dec else "modelo ausente")}
    suf = a.versao + ("_tta" if a.tta else "")
    (OUT / f"avaliacao_{suf}.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    md = [f"# Avaliação offline · {a.versao} · {rep['data']}", "", f"Teste: {rep['n_teste']} imagens · ONNX `{rep['onnx']}` · paridade torch/onnx max {rep['paridade_max_diff_torch_onnx']} · mapa de ativação em {cam_ok} imagens", "",
          "| sinal | n pos | AUROC | limiar | sens | esp | FP | FN |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    md += [f"| {r['sinal']} | {r['n_pos']} | {r['auroc']} | {r['limiar']} | {r['sensibilidade']} | {r['especificidade']} | {r['fp']} | {r['fn']} |" for r in rows]
    md += ["", f"Triagem (regra do app) concorda com a esperada pelos rótulos em **{rep['triagem_concordancia']:.0%}** das imagens.", "",
           "| esperada → obtida | n |", "|---|---:|"] + [f"| {k} | {v} |" for k, v in rep["triagem_confusao"].items()]
    md += ["", "## Por domínio", ""] + [f"- **{d}** (n={v['n']}): " + ", ".join(f"{k} {x}" for k, x in v["auroc"].items()) for d, v in dom.items()]
    md += ["", f"## Enquadramento no conjunto de teste", "", str(rep["enquadramento"])]
    # casos dificeis reais (ex.: a foto de pterigio que a v2 errou): um por linha, com a probabilidade do rotulo esperado
    casos = BASE / a.casos
    if (casos / "manifest.csv").exists():
        md += ["", "## Casos reais (regressão)", "", "| imagem | esperado | p(esperado) | limiar | passou | outros ≥ limiar |", "|---|---|---:|---:|---|---|"]
        for line in (casos / "manifest.csv").read_text().splitlines()[1:]:
            if not line.strip(): continue
            fn, labs, trg, frm = (line.split(";") + ["", "", ""])[:4]
            x = preprocess(casos / fn, size, mean, std, tta=a.tta)
            if a.tta: p = np.stack([1 / (1 + np.exp(-sess.run(None, {"image": x[k:k + 1]})[0][0])) for k in range(len(x))]).max(0)
            else: p = 1 / (1 + np.exp(-sess.run(None, {"image": x})[0][0]))
            exp_l = [l for l in labs.split("|") if l]
            others = [f"{l} {p[j]:.2f}" for j, l in enumerate(labels) if p[j] >= thr[l] and l not in exp_l]
            for l in exp_l or ["(nenhum)"]:
                j = labels.index(l) if l in labels else -1
                pj = p[j] if j >= 0 else float("nan"); ok = j >= 0 and pj >= thr[l]
                md.append(f"| {fn} | {l} | {pj:.2f} | {thr.get(l, float('nan')):.2f} | {'sim' if ok else 'NÃO'} | {', '.join(others) or '–'} |")
    (OUT / f"avaliacao_{suf}.md").write_text("\n".join(md)); print("\n".join(md))

if __name__ == "__main__":
    main()
