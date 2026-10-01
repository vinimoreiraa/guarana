"""Conjunto + TTA sobre os pesos salvos do banco (saida/bench_<modelo>.pt), mesma regua (saida/bench_split.csv).
Mede acuracia (geral e media das 4 classes) em teste e google para: cada modelo sozinho, cada um com 6 vistas, e combinacoes.
Uso: .venv/bin/python treino/bench_conjunto.py --modelos a b c [--dev cpu]
"""
import argparse, itertools, sys, importlib.util
from pathlib import Path
import numpy as np, pandas as pd, torch, torchvision.transforms as T
from PIL import Image, ImageOps
BASE = Path(__file__).resolve().parents[1]; sys.argv_b = sys.argv[1:]; sys.argv = ["x"]
spec = importlib.util.spec_from_file_location("b", BASE / "treino/bench_arquiteturas.py"); b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
def vistas(im, size):
    w, h = im.size; s = min(w, h); out = []
    boxes = [((w - s) // 2, (h - s) // 2)] + ([(0, (h - s) // 2), (w - s, (h - s) // 2)] if w > h else [((w - s) // 2, 0), ((w - s) // 2, h - s)] if h > w else [])
    for x0, y0 in boxes:
        c = im.crop((x0, y0, x0 + s, y0 + s)); out += [c, ImageOps.mirror(c)]
    return out
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--modelos", nargs="+"); ap.add_argument("--dev", default="cpu"); a = ap.parse_args(sys.argv_b)
    sp = pd.read_csv(BASE / "saida/bench_split.csv"); sp = sp[sp.split.isin(["teste", "google"])].reset_index(drop=True); Y = sp.classe.map(b.CL.index).to_numpy()
    probs1, probs6 = {}, {}
    for nome in a.modelos:
        m, size, mean, std = b.cria(nome); m.load_state_dict(torch.load(BASE / f"saida/bench_{nome}.pt", map_location="cpu")); m.eval().to(a.dev)
        tf = T.Compose([T.Resize(size), T.CenterCrop(size), T.ToTensor(), T.Normalize(mean, std)]); tf1 = T.Compose([T.Resize(int(size * 1.1)), T.CenterCrop(size), T.ToTensor(), T.Normalize(mean, std)])
        p1, p6 = [], []
        with torch.no_grad():
            for i, f in enumerate(sp.file):
                im = ImageOps.exif_transpose(Image.open(b.D / f)).convert("RGB")
                p1.append(torch.softmax(m(tf1(im)[None].to(a.dev)), 1)[0].cpu().numpy())
                xs = torch.stack([tf(v) for v in vistas(im, size)]).to(a.dev); p6.append(torch.softmax(m(xs), 1).mean(0).cpu().numpy())
        probs1[nome], probs6[nome] = np.array(p1), np.array(p6); print("pronto", nome, flush=True)
    def mede(P):
        pred = P.argmax(1); r = {}
        for s in ("teste", "google"):
            k = (sp.split == s).to_numpy(); acc = (pred[k] == Y[k]).mean(); bal = np.mean([(pred[k & (Y == c)] == c).mean() for c in range(4) if (k & (Y == c)).any()])
            r[s] = f"{acc:.1%} / média4 {bal:.1%}"
        return r
    linhas = []
    for nome in a.modelos: linhas += [(nome, "1 vista", mede(probs1[nome])), (nome, "6 vistas", mede(probs6[nome]))]
    for k in range(2, len(a.modelos) + 1):
        for comb in itertools.combinations(a.modelos, k):
            linhas += [(" + ".join(c.split(".")[0] for c in comb), "6 vistas", mede(np.mean([probs6[c] for c in comb], 0)))]
    for n, v, r in linhas: print(f"{n[:70]:70s} {v:9s} | teste {r['teste']} | google {r['google']}")
if __name__ == "__main__":
    main()
