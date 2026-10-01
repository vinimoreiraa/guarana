"""Verificacao de rotulos das fotos de busca com SigLIP 2 (zero-shot imagem x texto). Para cada foto, similaridade com uma
descricao clinica de cada classe; a foto e mantida se a classe da busca estiver entre as 2 mais provaveis e com prob >= piso.
Primeiro calibra: mede a concordancia do SigLIP com rotulos curados (pool_multiclasse, fontes nao-web) para saber quanto confiar.
Saida: dados/externos/labels_busca_web_verificado.csv (coluna verificado, siglip_top, siglip_p) e saida/verificacao_siglip.md
Uso: .venv/bin/python treino/verificar_rotulos.py [--modelo google/siglip2-so400m-patch16-384]
"""
import argparse
from pathlib import Path
import numpy as np, pandas as pd, torch
from PIL import Image, ImageOps
BASE = Path(__file__).resolve().parents[1]; D = BASE / "dados"; OUT = BASE / "saida"
DESC = {
 "normal": "a close-up photo of a healthy normal human eye with white sclera",
 "ictericia": "a close-up photo of an eye with jaundice, yellow sclera",
 "conjuntivite": "a close-up photo of an eye with conjunctivitis, pink red eye with discharge",
 "pterigio": "a close-up photo of an eye with pterygium, a fleshy triangular growth of conjunctiva onto the cornea",
 "catarata_leucocoria": "a close-up photo of an eye with a white or cloudy pupil, cataract or leukocoria",
 "ceratite": "a close-up photo of an eye with a corneal ulcer or keratitis, white spot on the cornea",
 "hemorragia_subconjuntival": "a close-up photo of an eye with subconjunctival hemorrhage, a bright red patch of blood on the white of the eye",
 "alteracao_palpebral": "a close-up photo of an eyelid problem such as a chalazion, stye, blepharitis or drooping eyelid",
 "uveite": "a close-up photo of an eye with uveitis, red ring around the cornea, hypopyon",
 "trauma_ocular": "a photo of an eye injury, foreign body, chemical burn or blood in the eye after trauma",
 "celulite_orbitaria": "a photo of a swollen red eyelid from periorbital or orbital cellulitis",
 "hanseniase_ocular": "a photo of an eye affected by leprosy, unable to close the eyelid or loss of eyebrows",
 "palidez_conjuntival": "a photo of a pulled down lower eyelid showing pale conjunctiva from anemia",
 "tracoma": "a photo of trachoma, everted eyelid with follicles or inturned eyelashes",
}
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--modelo", default="google/siglip2-so400m-patch16-384"); ap.add_argument("--piso", type=float, default=0.10); a = ap.parse_args()
    from transformers import AutoModel, AutoProcessor
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    m = AutoModel.from_pretrained(a.modelo, torch_dtype=torch.float16 if dev == "mps" else torch.float32).eval().to(dev); proc = AutoProcessor.from_pretrained(a.modelo)
    vec = lambda o: o if torch.is_tensor(o) else (o.pooler_output if getattr(o, 'pooler_output', None) is not None else o[0])
    cls = list(DESC); tin = proc(text=[DESC[c] for c in cls], padding="max_length", max_length=64, return_tensors="pt").to(dev)
    with torch.no_grad(): T = vec(m.get_text_features(**tin)); T = T / T.norm(dim=-1, keepdim=True)
    def probs(files):
        out = []
        for i in range(0, len(files), 16):
            ims = [ImageOps.exif_transpose(Image.open(D / f)).convert("RGB") for f in files[i:i + 16]]
            x = proc(images=ims, return_tensors="pt").to(dev)
            with torch.no_grad():
                I = vec(m.get_image_features(**{k: v.to(T.dtype) if v.dtype.is_floating_point else v for k, v in x.items()})); I = I / I.norm(dim=-1, keepdim=True)
                lg = (I @ T.T).float() * m.logit_scale.exp().float() + m.logit_bias.float()
            out.append(torch.softmax(lg, -1).cpu().numpy())
            if (i // 16) % 20 == 0: print(f"  {i}/{len(files)}", flush=True)
        return np.concatenate(out)
    # 1) calibracao em rotulos curados (fontes nao-web)
    p = pd.read_csv(D / "pool_multiclasse.csv"); p = p[(p.source != "busca_web") & p.classe.isin(cls)]
    cal = pd.concat([d.sample(min(60, len(d)), random_state=0) for _, d in p.groupby("classe")])
    P = probs(cal.file.tolist()); top2 = np.argsort(-P, 1)[:, :2]; y = cal.classe.map(cls.index).to_numpy()
    linhas = ["# Verificação de rótulos com SigLIP 2 (zero-shot)\n", "## Calibração em rótulos curados", "| classe | n | top-1 | top-2 |", "|---|---:|---:|---:|"]
    for c in cal.classe.unique():
        k = (cal.classe == c).to_numpy(); ci = cls.index(c)
        linhas.append(f"| {c} | {k.sum()} | {(P[k].argmax(1) == ci).mean():.0%} | {np.mean([ci in t for t in top2[k]]):.0%} |")
    # 2) fotos da busca
    w = pd.read_csv(D / "externos/labels_busca_web.csv").drop_duplicates("file"); w = w[w.file.map(lambda f: (D / f).exists())]
    conflito = w.groupby("file").classe.nunique(); w = w[w.file.map(lambda f: conflito.get(f, 1) == 1)]
    Pw = probs(w.file.tolist()); w["siglip_top"] = [cls[i] for i in Pw.argmax(1)]; w["siglip_p"] = [Pw[i, cls.index(c)] if c in cls else np.nan for i, c in enumerate(w.classe)]
    t2 = np.argsort(-Pw, 1)[:, :2]; w["verificado"] = [int(c in cls and cls.index(c) in t2[i] and w.siglip_p.iloc[i] >= a.piso) for i, c in enumerate(w.classe)]
    w.to_csv(D / "externos/labels_busca_web_verificado.csv", index=False)
    linhas += ["\n## Fotos da busca", "| classe | coletadas | verificadas | % |", "|---|---:|---:|---:|"]
    for c, d in w.groupby("classe"): linhas.append(f"| {c} | {len(d)} | {int(d.verificado.sum())} | {d.verificado.mean():.0%} |")
    md = "\n".join(linhas); (OUT / "verificacao_siglip.md").write_text(md); print(md)
if __name__ == "__main__":
    main()
