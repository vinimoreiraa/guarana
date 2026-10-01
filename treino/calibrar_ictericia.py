"""Ramo de cor, icterícia: mede se o indice de cor da pele prevê a bilirrubina serica no NeoJaundice
(fotos de recem-nascidos por smartphone com cartao de cor e bilirrubina de sangue), com e sem calibracao pelo
branco do cartao. E a validacao do principio ln(R/B) do PDF, no unico conjunto aberto com padrao-ouro.
Saida: saida/calibracao_ictericia.json/.md. Uso: .venv/bin/python treino/calibrar_ictericia.py
"""
import json, csv, datetime
from pathlib import Path
import numpy as np
from PIL import Image
BASE = Path(__file__).resolve().parents[1]; RAW = BASE / "dados/raw/neojaundice"; OUT = BASE / "saida"

def medir(path):
    im = np.asarray(Image.open(path).convert("RGB"), np.float32); h, w, _ = im.shape
    # pele: janela central (o recorte do cartao); branco: anel do cartao ao redor, so pixels neutros e claros
    cy, cx = h // 2, w // 2; s = int(min(h, w) * 0.16)
    skin = im[cy - s:cy + s, cx - s:cx + s].reshape(-1, 3)
    ring = np.concatenate([im[int(h*0.05):int(h*0.20)].reshape(-1, 3), im[int(h*0.80):int(h*0.95)].reshape(-1, 3),
                           im[:, int(w*0.05):int(w*0.20)].reshape(-1, 3), im[:, int(w*0.80):int(w*0.95)].reshape(-1, 3)])
    lum = ring.mean(1); sat = ring.max(1) - ring.min(1)
    white = ring[(lum > np.percentile(lum, 85)) & (sat < 25)]
    if len(white) < 50: white = ring[lum > np.percentile(lum, 95)]
    sm = skin.mean(0); wm = white.mean(0)
    return sm, wm

def indices(sm, wm=None):
    r, g, b = (sm / wm) if wm is not None else (sm / 255.0)
    eps = 1e-6
    return {"ln_rb": float(np.log((r + eps) / (b + eps))), "r_menos_b": float(r - b), "ln_rg": float(np.log((r + eps) / (g + eps))),
            "b_norm": float(b / (r + g + b + eps)), "amarelo": float((r + g) / 2 - b)}

def main():
    rows = list(csv.DictReader(open(RAW / "neojaundice.csv"))); by = {}
    for r in rows:
        p = RAW / "images" / r["image_idx"]
        if p.exists(): by.setdefault(r["patient_id"], []).append((p, float(r["blood(mg/dL)"])))
    X = {"sem_cal": {k: [] for k in ("ln_rb", "r_menos_b", "ln_rg", "b_norm", "amarelo")}, "com_cal": {k: [] for k in ("ln_rb", "r_menos_b", "ln_rg", "b_norm", "amarelo")}}
    Y = []; pid = []
    for p_id, items in by.items():   # media das fotos do mesmo paciente
        feats = {"sem_cal": [], "com_cal": []}; bili = items[0][1]
        for path, _ in items:
            try: sm, wm = medir(path)
            except Exception: continue
            feats["sem_cal"].append(indices(sm)); feats["com_cal"].append(indices(sm, wm))
        if not feats["sem_cal"]: continue
        for cal in X:
            for k in X[cal]: X[cal][k].append(float(np.mean([f[k] for f in feats[cal]])))
        Y.append(bili); pid.append(p_id)
    Y = np.array(Y); n = len(Y)
    from scipy.stats import spearmanr, pearsonr
    rep = {"data": datetime.datetime.now().isoformat(timespec="seconds"), "pacientes": n, "bilirrubina_media": float(Y.mean()), "bilirrubina_max": float(Y.max()), "indices": {}}
    for cal in X:
        for k, v in X[cal].items():
            v = np.array(v); rs = spearmanr(v, Y).correlation; rp = pearsonr(v, Y)[0]
            # regressao linear com validacao cruzada por paciente (5 dobras)
            idx = np.arange(n); rng = np.random.default_rng(0); rng.shuffle(idx); folds = np.array_split(idx, 5); pred = np.zeros(n)
            for f in folds:
                tr = np.setdiff1d(idx, f); a, b = np.polyfit(v[tr], Y[tr], 1); pred[f] = a * v[f] + b
            mae = float(np.abs(pred - Y).mean())
            # triagem: bilirrubina >= 12 mg/dL (zona de risco em RN de termo) — AUROC do indice
            from sklearn.metrics import roc_auc_score
            auc = float(roc_auc_score((Y >= 12).astype(int), v if rs > 0 else -v)) if 0 < (Y >= 12).sum() < n else float("nan")
            rep["indices"][f"{cal}:{k}"] = {"spearman": round(float(rs), 3), "pearson": round(float(rp), 3), "mae_cv_mg_dL": round(mae, 2), "auroc_bili_ge_12": round(auc, 3)}
    (OUT / "calibracao_ictericia.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    md = [f"# Calibração do índice de icterícia · NeoJaundice · {rep['data']}", "", f"Pacientes: {n} (fotos de pele com cartão de cor, bilirrubina sérica média {Y.mean():.1f}, máx {Y.max():.1f} mg/dL)", "",
          "| índice | calibração | Spearman | Pearson | MAE CV (mg/dL) | AUROC bili ≥ 12 |", "|---|---|---:|---:|---:|---:|"]
    for key, v in sorted(rep["indices"].items(), key=lambda kv: -abs(kv[1]["spearman"])):
        cal, k = key.split(":"); md.append(f"| {k} | {'branco do cartão' if cal == 'com_cal' else 'nenhuma'} | {v['spearman']} | {v['pearson']} | {v['mae_cv_mg_dL']} | {v['auroc_bili_ge_12']} |")
    (OUT / "calibracao_ictericia.md").write_text("\n".join(md)); print("\n".join(md))

if __name__ == "__main__":
    main()
