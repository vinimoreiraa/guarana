"""Modelo de visao-linguagem aberto (Ollama: llava:7b, llama3.2-vision:11b...) como reconhecedor zero-shot dos 15 sinais.
Amostra das fontes externas (metade B), pergunta em ingles com lista fechada, resposta em JSON 0/1; mede sensibilidade e
especificidade por sinal e o caso do usuario. Uso: .venv/bin/python treino/avaliar_vlm.py --modelo llava:7b --n 120
"""
import argparse, base64, io, json, re, time, urllib.request
from pathlib import Path
import numpy as np, pandas as pd
from PIL import Image, ImageOps
BASE = Path(__file__).resolve().parents[1]; DATA = BASE / "dados"; OUT = BASE / "saida"
LABELS = ["hiperemia","ictericia","pterigio","pinguecula","catarata_leucocoria","hemorragia_subconjuntival","lesao_pigmentada","opacidade_corneana","tumor_superficie_ocular","ceratite","cisto_conjuntival","lente_intraocular","conjuntivite","uveite","alteracao_palpebral"]
EN = {"hiperemia": "conjunctival redness / red eye", "ictericia": "yellow sclera (jaundice)", "pterigio": "pterygium (fleshy wedge growing onto the cornea)", "pinguecula": "pinguecula (yellowish bump on the sclera)", "catarata_leucocoria": "white or cloudy pupil (cataract / leukocoria)", "hemorragia_subconjuntival": "subconjunctival hemorrhage (bright red blood patch)", "lesao_pigmentada": "pigmented (brown/black) lesion on the eye surface", "opacidade_corneana": "corneal opacity / scar (white haze on the cornea)", "tumor_superficie_ocular": "tumor or mass on the ocular surface", "ceratite": "keratitis / corneal ulcer (white infiltrate on the cornea)", "cisto_conjuntival": "conjunctival cyst", "lente_intraocular": "intraocular lens implant visible", "conjuntivite": "conjunctivitis (pink eye with discharge or diffuse redness)", "uveite": "anterior uveitis (red ring around the cornea, small irregular pupil, hypopyon)", "alteracao_palpebral": "eyelid abnormality (chalazion, stye, blepharitis, ptosis)"}
PROMPT = "You are an ophthalmologist. Look at this photo of one human eye. For each finding below answer 1 if clearly visible, else 0. Reply ONLY with a JSON object with these exact keys.\n" + "\n".join(f'- "{k}": {v}' for k, v in EN.items())
def pergunta(modelo, im):
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=90); b64 = base64.b64encode(buf.getvalue()).decode()
    req = urllib.request.Request("http://localhost:11434/api/generate", data=json.dumps({"model": modelo, "prompt": PROMPT, "images": [b64], "stream": False, "options": {"temperature": 0}}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r: txt = json.load(r)["response"]
    m = re.search(r"\{.*\}", txt, re.S)
    try: d = json.loads(m.group(0)) if m else {}
    except Exception: d = {}
    return {k: int(bool(int(d.get(k, 0)))) if str(d.get(k, 0)).strip() in ("0", "1", "true", "false", "True", "False") else 0 for k in LABELS}, txt
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--modelo", default="llava:7b"); ap.add_argument("--n", type=int, default=120); ap.add_argument("--extra", nargs="*", default=["/Users/Vinicius/Desktop/blog-donato-1.png"]); a = ap.parse_args()
    fontes = ["labels_pubmed_limpo", "labels_commons", "externos/labels_mendeley_conj", "externos/labels_pinkeye", "externos/labels_cekmate_leucocoria", "externos/labels_gh_eyedis5", "externos/labels_zenodo_normais"]
    df = pd.concat([pd.read_csv(DATA / f"{f}.csv") for f in fontes], ignore_index=True)
    for l in LABELS:
        if l not in df.columns: df[l] = 0
    df = df[df["metade"] == "B"]; pos = df[df[LABELS].sum(axis=1) > 0].sample(min(a.n, int((df[LABELS].sum(axis=1) > 0).sum())), random_state=0); neg = df[df[LABELS].sum(axis=1) == 0].sample(a.n // 3, random_state=0)
    rows = []; t0 = time.time()
    for _, r in pd.concat([pos, neg]).iterrows():
        try: im = ImageOps.exif_transpose(Image.open(DATA / r["file"])).convert("RGB")
        except Exception: continue
        if max(im.size) > 768: im.thumbnail((768, 768))
        try: pred, txt = pergunta(a.modelo, im)
        except Exception as e: print("erro", e); continue
        rows.append({"file": r["file"], **{"y_" + l: int(r[l]) for l in LABELS}, **{"p_" + l: pred[l] for l in LABELS}})
        if len(rows) % 20 == 0: print(f"  {len(rows)} ({(time.time()-t0)/len(rows):.1f} s/img)", flush=True)
    d = pd.DataFrame(rows); d.to_csv(OUT / f"vlm_{a.modelo.replace(':', '_')}.csv", index=False)
    lines = [f"# VLM zero-shot · {a.modelo} · {len(d)} imagens externas (metade B)\n", "| sinal | n pos | sens | esp |", "|---|---:|---:|---:|"]
    for l in LABELS:
        y = d["y_" + l].to_numpy(); p = d["p_" + l].to_numpy()
        if y.sum() >= 5: lines.append(f"| {l} | {int(y.sum())} | {(p[y == 1] == 1).mean():.2f} | {(p[y == 0] == 0).mean():.2f} |")
    anyp = d[[f"p_{l}" for l in LABELS]].to_numpy().any(axis=1); haspos = d[[f"y_{l}" for l in LABELS]].to_numpy().any(axis=1)
    lines.append(f"\npositivos sem nenhum sinal: {int((~anyp & haspos).sum())} de {int(haspos.sum())} | normais com algum sinal: {int((anyp & ~haspos).sum())} de {int((~haspos).sum())}")
    for f in a.extra:
        if Path(f).exists():
            pred, txt = pergunta(a.modelo, ImageOps.exif_transpose(Image.open(f)).convert("RGB")); lines.append(f"\ncaso {Path(f).name}: " + ", ".join(k for k, v in pred.items() if v) + f"\n  resposta bruta: {txt[:300]}")
    md = "\n".join(lines); print(md); (OUT / f"vlm_{a.modelo.replace(':', '_')}.md").write_text(md)
if __name__ == "__main__":
    main()
