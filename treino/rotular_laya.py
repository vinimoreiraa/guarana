"""Re-rotulagem por TEXTO com LAYA (decisoes tipadas, ModernBERT, Apache 2.0): le a legenda/descricao de cada imagem das fontes
rotuladas por texto (PubMed, Commons, Commons-olho) e decide: achado principal (15 sinais + normal + outro), tipo de imagem,
pos-operatorio e se algum painel e olho normal. Compara com o rotulo por palavra-chave e grava colunas laya_* no CSV.
Uso: .venv/bin/python treino/rotular_laya.py
Saida: dados/<fonte>_laya.csv e saida/rotulagem_laya.md
"""
import json, time
from pathlib import Path
import numpy as np, pandas as pd
from laya import Router
BASE = Path(__file__).resolve().parents[1]; D = BASE / "dados"; OUT = BASE / "saida"
LABELS = ["hiperemia","ictericia","pterigio","pinguecula","catarata_leucocoria","hemorragia_subconjuntival","lesao_pigmentada","opacidade_corneana","tumor_superficie_ocular","ceratite","cisto_conjuntival","lente_intraocular","conjuntivite","uveite","alteracao_palpebral"]
ACHADO = {"hiperemia": "red eye, conjunctival injection or hyperemia without a more specific diagnosis", "ictericia": "jaundice, yellow sclera, scleral icterus", "pterigio": "pterygium, fleshy wedge growing onto the cornea",
          "pinguecula": "pinguecula, yellowish bump on the conjunctiva", "catarata_leucocoria": "cataract, white pupil, leukocoria, retinoblastoma reflex", "hemorragia_subconjuntival": "subconjunctival hemorrhage, blood under the conjunctiva",
          "lesao_pigmentada": "pigmented conjunctival lesion, nevus, melanosis", "opacidade_corneana": "corneal opacity, corneal scar, leukoma", "tumor_superficie_ocular": "ocular surface tumor, squamous neoplasia, melanoma, papilloma",
          "ceratite": "keratitis, corneal ulcer, corneal infiltrate", "cisto_conjuntival": "conjunctival cyst", "lente_intraocular": "intraocular lens implant, pseudophakia", "conjuntivite": "conjunctivitis",
          "uveite": "uveitis, iritis, hypopyon, ciliary flush", "alteracao_palpebral": "eyelid disease: chalazion, stye, blepharitis, ptosis, entropion, ectropion, trichiasis, eyelid tumor",
          "normal": "a normal healthy eye", "outro": "other eye disease or not about the external eye"}
TIPO = {"external_photo": "clinical photograph of the external eye or face taken with a camera", "slit_lamp": "slit-lamp biomicroscopy photograph", "fundus_or_retina": "fundus, retina, OCT or angiography",
        "microscopy": "histology, pathology, microscopy", "imaging": "CT, MRI, ultrasound, X-ray", "surgery": "intraoperative surgical photograph", "diagram": "drawing, diagram, chart", "animal": "animal eye (dog, cat, horse, mouse...)"}
Q = {"achado": {"type": "choice", "instructions": "Which eye condition is the main finding described?", "criteria": ACHADO},
     "tipo": {"type": "choice", "instructions": "What kind of image does this text describe?", "criteria": TIPO},
     "pos_op": {"type": "noul", "instructions": "Does the text describe an eye after surgery or after treatment?"},
     "painel_normal": {"type": "noul", "instructions": "Does the text say that one of the images shows a normal, healthy or fellow eye?"}}
def main():
    r = Router(); fontes = [("labels_pubmed", "caption"), ("labels_commons", "caption"), ("externos/labels_commons_olho", None)]
    linhas = ["# Re-rotulagem das fontes rotuladas por texto com LAYA\n"]; t0 = time.time()
    for nome, col in fontes:
        df = pd.read_csv(D / f"{nome}.csv")
        if col is None:   # commons_olho: descricao vem do meta
            meta = pd.read_csv(D / "raw/commons_olho/commons_meta.csv"); meta["k"] = meta["arquivo"].astype(str).str[:40]
            df["k"] = df["subject_id"].str.replace("commons_olho_", "", regex=False).str[:40]; df = df.merge(meta[["k", "titulo", "descricao"]], on="k", how="left")
            df["texto"] = (df["titulo"].fillna("") + ". " + df["descricao"].fillna("")).str.replace("File:", "", regex=False)
        else: df["texto"] = df[col].fillna("").astype(str) + " " + df.get("termos", pd.Series([""] * len(df))).fillna("").astype(str)
        textos = df["texto"].str[:1500].tolist(); cache = {}
        res = []
        for i, t in enumerate(textos):
            if t not in cache:
                try: a = r.predict(t if t.strip() else "no description", Q)["answers"]
                except Exception as e: a = None
                cache[t] = a
            res.append(cache[t])
            if i % 100 == 0: print(f"  {nome}: {i}/{len(textos)} ({time.time()-t0:.0f}s)", flush=True)
        df["laya_achado"] = [a["achado"]["choice"] if a else None for a in res]; df["laya_achado_p"] = [a["achado"]["answer_confidence"] if a else None for a in res]
        df["laya_tipo"] = [a["tipo"]["choice"] if a else None for a in res]; df["laya_pos_op"] = [a["pos_op"]["noul"] if a else None for a in res]; df["laya_painel_normal"] = [a["painel_normal"]["noul"] if a else None for a in res]
        for l in LABELS:
            if l not in df.columns: df[l] = 0
        df["kw_principal"] = df[LABELS].apply(lambda row: next((l for l in LABELS if row[l] == 1), "normal"), axis=1)
        df.drop(columns=[c for c in ("texto", "k", "titulo", "descricao") if c in df.columns]).to_csv(D / f"{nome}_laya.csv", index=False)
        kw = df[LABELS].to_numpy(); concorda = np.array([ (a in LABELS and kw[i, LABELS.index(a)] == 1) or (a == "normal" and kw[i].sum() == 0) for i, a in enumerate(df["laya_achado"]) ])
        linhas += [f"\n## {nome} ({len(df)} imagens, {df['texto'].nunique() if 'texto' in df else len(cache)} textos distintos)",
                   f"- achado LAYA concorda com o rótulo por palavra-chave: **{concorda.mean():.0%}**",
                   f"- tipo de imagem (LAYA): " + ", ".join(f"{k} {v}" for k, v in df["laya_tipo"].value_counts().items()),
                   f"- pós-operatório (p>0,5): {(df['laya_pos_op'] > 0.5).mean():.0%} | algum painel normal (p>0,5): {(df['laya_painel_normal'] > 0.5).mean():.0%}",
                   "- maiores desacordos (palavra-chave → LAYA): " + ", ".join(f"{a}→{b} {n}" for (a, b), n in pd.Series(list(zip(df["kw_principal"], df["laya_achado"])))[~concorda].value_counts().head(8).items())]
    md = "\n".join(linhas); (OUT / "rotulagem_laya.md").write_text(md); print(md)
if __name__ == "__main__":
    main()
