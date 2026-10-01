"""Avalia o caminho em dois niveis: modelo geral (todas as doencas) e, quando ele diz 'olho vermelho', o especialista
decide o subtipo. Mesmos testes do modelo geral (saida/doencas_split_<tag_geral>.csv).
Uso: .venv/bin/python treino/avaliar_dois_niveis.py --geral todas --especialista vermelho
"""
import argparse
from pathlib import Path
import numpy as np, pandas as pd, torch, timm, torchvision.transforms as T
from PIL import Image, ImageOps
BASE = Path(__file__).resolve().parents[1]; D = BASE / "dados"; OUT = BASE / "saida"; DEV = "mps" if torch.backends.mps.is_available() else "cpu"
VERM = {"conjuntivite", "hiperemia", "hemorragia_subconjuntival", "uveite", "ceratite", "trauma_ocular"}; URG = {"uveite", "ceratite", "trauma_ocular"}
def carrega(tag):
    ck = torch.load(OUT / f"doencas_vit_pe_core_small_patch16_384_{tag}.pt", map_location="cpu", weights_only=False)
    m = timm.create_model(ck["modelo"], pretrained=False, num_classes=len(ck["classes"])); m.load_state_dict(ck["estado"]); m.eval().to(DEV)
    tf = T.Compose([T.Resize(int(ck["size"] * 1.1)), T.CenterCrop(ck["size"]), T.ToTensor(), T.Normalize(ck["mean"], ck["std"])]); return m, tf, ck["classes"]
def prever(m, tf, CL, files):
    out = []
    with torch.no_grad():
        for i in range(0, len(files), 32):
            x = torch.stack([tf(ImageOps.exif_transpose(Image.open(D / f)).convert("RGB")) for f in files[i:i + 32]]).to(DEV); out += [CL[j] for j in m(x).argmax(1).cpu().numpy()]
    return np.array(out)
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--geral", default="todas"); ap.add_argument("--especialista", default="vermelho"); a = ap.parse_args()
    sp = pd.read_csv(OUT / f"doencas_split_{a.geral}.csv"); sp = sp[sp.split.isin(["teste", "google"])].reset_index(drop=True)
    mg, tg, CLg = carrega(a.geral); me, te_, CLe = carrega(a.especialista)
    pg = prever(mg, tg, CLg, sp.file.tolist()); pe = prever(me, te_, CLe, sp.file.tolist())
    p2 = np.where(np.isin(pg, list(VERM)), pe, pg); y = sp.classe.to_numpy(); linhas = [f"# Dois níveis: geral `{a.geral}` + especialista `{a.especialista}` ({', '.join(CLe)})\n"]
    for s in ("teste", "google"):
        k = (sp.split == s).to_numpy()
        for nome, p in (("só o geral", pg), ("dois níveis", p2)):
            cls = sorted(set(y[k])); por = {c: (p[k][y[k] == c] == c).mean() for c in cls}
            kv = k & np.isin(y, list(VERM)); yu = np.isin(y[kv], list(URG)); pu = np.isin(p[kv], list(URG))
            linhas.append(f"- **{s} · {nome}**: acurácia {(p[k] == y[k]).mean():.1%} · média por classe {np.mean(list(por.values())):.1%} · olho vermelho: urgentes reconhecidos {pu[yu].mean():.0%}, não urgentes sem alarme {(~pu[~yu]).mean():.0%}")
            if nome == "dois níveis": linhas.append("  - por classe: " + ", ".join(f"{c} {v:.0%}" for c, v in por.items()))
    md = "\n".join(linhas); print(md); (OUT / f"dois_niveis_{a.geral}_{a.especialista}.md").write_text(md)
if __name__ == "__main__":
    main()
