"""Teste 'foto de tela': positivos externos (metade B) fotografados de uma tela simulada (grade, moire, brilho, tela azulada, borrao).
Mede, por sinal, deteccao (presente / candidato) e alarme de uveite, para as versoes dadas. Uso: .venv/bin/python treino/testar_tela.py ocular_v22 ocular_v21_e5_tela
"""
import sys, json, importlib.util, numpy as np, pandas as pd, onnxruntime as ort
from pathlib import Path
from PIL import Image, ImageOps, ImageFilter
BASE = Path(__file__).resolve().parents[1]; sys.argv_backup = sys.argv[1:]; sys.argv = ["x"]
spec = importlib.util.spec_from_file_location("te", BASE / "treino/testar_externo.py"); te = importlib.util.module_from_spec(spec); spec.loader.exec_module(te)
LABELS = ["hiperemia","ictericia","pterigio","pinguecula","catarata_leucocoria","hemorragia_subconjuntival","lesao_pigmentada","opacidade_corneana","tumor_superficie_ocular","ceratite","cisto_conjuntival","lente_intraocular","conjuntivite","uveite","alteracao_palpebral"]
def tela(im, rng):
    a = np.asarray(im.resize((640, max(64, int(640 * im.size[1] / im.size[0]))), Image.BILINEAR)).astype(np.float32); h, w = a.shape[:2]; yy, xx = np.mgrid[:h, :w]; per = rng.choice([2, 3, 4])
    grade = 1 - rng.uniform(0.08, 0.22) * (((xx % per) == 0) | ((yy % per) == 0)); moire = 1 + rng.uniform(0.02, 0.08) * np.sin(2 * np.pi * (xx * rng.uniform(0.03, 0.09) + yy * rng.uniform(0.03, 0.09)))
    brilho = 1 + rng.uniform(0.1, 0.45) * np.exp(-(((xx - rng.uniform(0.1, 0.9) * w) / (rng.uniform(0.2, 0.5) * w)) ** 2 + ((yy - rng.uniform(0.1, 0.9) * h) / (rng.uniform(0.2, 0.5) * h)) ** 2))
    a = a * (grade * moire * brilho)[..., None] * np.array([rng.uniform(0.95, 1.05), 1.0, rng.uniform(1.0, 1.3)]); a = np.clip(a * rng.uniform(0.75, 1.15) + rng.uniform(0, 25), 0, 255).astype(np.uint8)
    return Image.fromarray(a).filter(ImageFilter.GaussianBlur(rng.uniform(0.4, 1.6)))
def main():
    versoes = sys.argv_backup or ["ocular_v22"]; rng = np.random.RandomState(0)
    fontes = ["labels_pubmed_limpo", "labels_commons", "externos/labels_mendeley_conj", "externos/labels_pinkeye", "externos/labels_cekmate_leucocoria", "externos/labels_gh_eyedis5", "externos/labels_mendeley_blefarite", "externos/labels_zenodo_normais"]
    df = pd.concat([pd.read_csv(BASE / "dados" / f"{f}.csv") for f in fontes], ignore_index=True)
    for l in LABELS:
        if l not in df.columns: df[l] = 0
    df = df[df["metade"] == "B"]; pos = df[df[LABELS].sum(axis=1) > 0].sample(min(240, int((df[LABELS].sum(axis=1) > 0).sum())), random_state=0); neg = df[df[LABELS].sum(axis=1) == 0].sample(120, random_state=0)
    imgs = {}
    for _, r in pd.concat([pos, neg]).iterrows():
        try: im = ImageOps.exif_transpose(Image.open(BASE / "dados" / r["file"])).convert("RGB")
        except Exception: continue
        imgs[r["file"]] = (im, tela(im, rng))
    print(f"imagens: {len(imgs)} (positivas {len(pos)}, normais {len(neg)})")
    mean, std = np.array([0.485, 0.456, 0.406], np.float32), np.array([0.229, 0.224, 0.225], np.float32); res = {}
    for v in versoes:
        cardp = BASE / "saida" / ("model_card.json" if v == "ocular_v22" else f"{v}_card.json"); card = json.load(open(cardp)); thr = card["thresholds"]; cand = card.get("thresholds_candidato", {l: t / 2 for l, t in thr.items()}); labels = list(thr)
        sess = ort.InferenceSession(str(BASE / "saida" / f"{v}.onnx"), providers=["CPUExecutionProvider"]); name = sess.get_inputs()[0].name
        def run(img):
            xs = np.stack([((np.asarray(vw, np.float32) / 255 - mean) / std).transpose(2, 0, 1) for vw in te.views(img, card["input"].get("size", 320) if isinstance(card.get("input"), dict) else 320)]); lg = np.concatenate([sess.run(None, {name: x[None]})[0] for x in xs]); return (1 / (1 + np.exp(-lg))).max(axis=0)
        lines = [f"\n## {v}", "| sinal | n | orig presente / candidato | TELA presente / candidato |", "|---|---:|---|---|"]
        Po = {}; Pt = {}
        for f, (im, tl) in imgs.items(): Po[f] = run(im); Pt[f] = run(tl)
        for l in labels:
            fs = [f for f in imgs if f in set(pos["file"]) and pos.set_index("file").loc[f, l] == 1]
            if len(fs) < 5: continue
            i = labels.index(l); po = np.array([Po[f][i] for f in fs]); pt = np.array([Pt[f][i] for f in fs])
            lines.append(f"| {l} | {len(fs)} | {(po >= thr[l]).mean():.0%} / {(po >= cand[l]).mean():.0%} | {(pt >= thr[l]).mean():.0%} / {(pt >= cand[l]).mean():.0%} |")
        nf = [f for f in imgs if f in set(neg["file"])]; T = np.array([thr[l] for l in labels])
        alo = np.mean([(Po[f] >= T).any() for f in nf]); alt = np.mean([(Pt[f] >= T).any() for f in nf]); iu = labels.index("uveite")
        lines.append(f"\nnormais com algum alarme: orig {alo:.0%} | tela {alt:.0%}. Uveíte disparando em positivos de outros sinais na TELA: {np.mean([Pt[f][iu] >= thr['uveite'] for f in imgs if f in set(pos['file'])]):.0%}")
        res[v] = "\n".join(lines); print(res[v])
    (BASE / "saida" / "teste_tela.md").write_text("# Teste foto-de-tela (simulada) nas metades B\n" + "\n".join(res.values()))
if __name__ == "__main__":
    main()
