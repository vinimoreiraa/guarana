"""Calibra a regra de cor para palidez conjuntival (anemia) nos recortes do CP-AnemiC (710 criancas, Hb medida).
Entrada: recorte da conjuntiva palpebral em fundo branco (o app precisa produzir um recorte equivalente).
Saida: saida/regra_palidez.json com um modelo logistico sobre a cor media em Lab, e um limiar simples de a*.
"""
import json
from pathlib import Path
import numpy as np, pandas as pd, cv2
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

BASE = Path(__file__).resolve().parents[1]
DS = BASE / "dados/raw/cp_anemic/extract/CP-AnemiC dataset"
OUT = BASE / "saida"; OUT.mkdir(exist_ok=True)

def color_features(png):
    rgb = np.asarray(Image.open(png).convert("RGB"))
    mask = (rgb.min(axis=2) < 225) & (rgb.max(axis=2) > 25)     # tira fundo branco e bordas pretas
    if mask.sum() < 50:
        return None
    px = rgb[mask].astype(np.float32)
    lab = cv2.cvtColor(px.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    L, a, b = lab[:, 0] * 100 / 255, lab[:, 1] - 128, lab[:, 2] - 128
    r, g, bch = px[:, 0], px[:, 1], px[:, 2]
    return {"L": L.mean(), "a": a.mean(), "b": b.mean(), "R": r.mean(), "G": g.mean(), "B": bch.mean(),
            "r_frac": (r / (r + g + bch + 1e-6)).mean(), "n_px": int(mask.sum())}

sheet = pd.read_excel(DS / "Anemia_Data_Collection_Sheet.xlsx")
rows = []
for _, s in sheet.iterrows():
    p = next(iter(list((DS / "Anemic").glob(f"{s['IMAGE_ID']}.*")) + list((DS / "Non-anemic").glob(f"{s['IMAGE_ID']}.*"))), None)
    if p is None: continue
    f = color_features(p)
    if f is None: continue
    f.update(image=s["IMAGE_ID"], hb=float(s["HB_LEVEL"]), anemic=int(str(s["REMARK"]).strip().lower().startswith("anemic")), age_m=s["Age(Months)"])
    rows.append(f)
d = pd.DataFrame(rows)
print(f"{len(d)} imagens | anemicas {d.anemic.sum()} | Hb media {d.hb.mean():.1f}")
print("correlacao com Hb:", d[["L", "a", "b", "r_frac"]].corrwith(d["hb"]).round(3).to_dict())

FEATS = ["L", "a", "b"]
X, y = d[FEATS].to_numpy(), d["anemic"].to_numpy()
model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
cv = StratifiedKFold(5, shuffle=True, random_state=42)
p_cv = cross_val_predict(model, X, y, cv=cv, method="predict_proba")[:, 1]
auc = roc_auc_score(y, p_cv)
fpr, tpr, thr = roc_curve(y, p_cv)
i = int(np.argmax(tpr >= 0.90)); thr90 = float(thr[i])
print(f"logistico L,a,b: AUROC cv={auc:.3f} | limiar p>={thr90:.3f} -> sens {tpr[i]:.2f} espec {1-fpr[i]:.2f}")

# regra univariada interpretavel: a* (vermelho-verde) baixo = palido
auc_a = roc_auc_score(y, -d["a"]); fpr_a, tpr_a, thr_a = roc_curve(y, -d["a"])
j = int(np.argmax(tpr_a >= 0.90)); a_cut = float(-thr_a[j])
print(f"univariada a*: AUROC={auc_a:.3f} | anemico se a* <= {a_cut:.1f} -> sens {tpr_a[j]:.2f} espec {1-fpr_a[j]:.2f}")

if auc < 0.70:
    print(f"\nSEM SINAL: AUROC {auc:.2f} < 0.70. A cor media da conjuntiva neste dataset nao separa anemicos de nao anemicos "
          "(mesma cor em todas as faixas de Hb). Nenhuma regra foi gravada; palidez fica com a nuvem ate haver dados proprios.")
    d.to_csv(BASE / "dados" / "calibracao_palidez.csv", index=False)
    raise SystemExit(0)

model.fit(X, y)
sc, lr = model.named_steps["standardscaler"], model.named_steps["logisticregression"]
regra = {
    "name": "regra_palidez_v1", "task": "palidez conjuntival (anemia) a partir da cor media da conjuntiva palpebral recortada",
    "input": "recorte da conjuntiva palpebral inferior em fundo branco ou mascarado; cor media em CIELab (L 0-100, a/b centrados em 0, conversao OpenCV)",
    "features": FEATS, "scaler_mean": sc.mean_.tolist(), "scaler_scale": sc.scale_.tolist(),
    "coef": lr.coef_[0].tolist(), "intercept": float(lr.intercept_[0]),
    "threshold_prob": thr90, "target_sensitivity": 0.90, "auroc_cv5": round(auc, 3),
    "simple_rule": {"feature": "a", "anemic_if_leq": round(a_cut, 2), "auroc": round(auc_a, 3)},
    "calibrated_on": "CP-AnemiC (Gana, 710 criancas 6-59 meses, Hb laboratorial; CC BY 4.0)",
    "caveats": ["iluminacao e balanco de branco do tablet mudam a cor: use referencia branca no protocolo de captura",
                "populacao pediatrica de Gana; validar em adultos e em outra pele/iluminacao antes de confiar",
                "triagem, nao diagnostico"],
}
(OUT / "regra_palidez.json").write_text(json.dumps(regra, indent=2, ensure_ascii=False), encoding="utf-8")
d.to_csv(BASE / "dados" / "calibracao_palidez.csv", index=False)
print("salvo:", OUT / "regra_palidez.json")
