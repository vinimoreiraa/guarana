"""Treino multiclasse das doencas prioritarias com a regua honesta.
Pool = fotos curadas (pool_multiclasse, fontes nao-web) + fotos da busca VERIFICADAS pelo SigLIP 2 (metade A).
Teste 1 = ate 200 por classe (min 30% do curado), separado por paciente, de fontes nao-web.
Teste 2 ("Google") = metade B das fotos da busca verificadas, nunca vistas.
Classes com menos de --min fotos ficam de fora (e sao listadas). Reporta acuracia geral, media por classe e por classe.
Uso: .venv/bin/python treino/treinar_doencas.py [--modelo vit_pe_core_small_patch16_384.fb] [--min 80] [--max-treino 1500] [--epocas 12]
"""
import argparse, hashlib, json, random, time, sys, importlib.util
from pathlib import Path
import numpy as np, pandas as pd, torch, torch.nn as nn, torchvision.transforms as T
from PIL import Image, ImageOps
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
BASE = Path(__file__).resolve().parents[1]; D = BASE / "dados"; OUT = BASE / "saida"; DEV = "mps" if torch.backends.mps.is_available() else "cpu"
spec = importlib.util.spec_from_file_location("b", BASE / "treino/bench_arquiteturas.py"); b = importlib.util.module_from_spec(spec); sys.argv_b = sys.argv; sys.argv = ["x"]; spec.loader.exec_module(b); sys.argv = sys.argv_b
FORA = {"palidez_conjuntival", "tracoma"}   # captura diferente (palpebra evertida): vao para o ramo de cor / modo proprio
def main():
    torch.multiprocessing.set_start_method("fork", force=True)
    ap = argparse.ArgumentParser(); ap.add_argument("--modelo", default="vit_pe_core_small_patch16_384.fb"); ap.add_argument("--min", type=int, default=80); ap.add_argument("--max-treino", type=int, default=1500); ap.add_argument("--epocas", type=int, default=12); ap.add_argument("--web", default="todas", choices=["todas", "verificadas"]); ap.add_argument("--so", default=""); ap.add_argument("--tag", default=""); a = ap.parse_args()
    SO = set(x for x in a.so.split(",") if x); TAG = a.tag or a.web
    random.seed(0); torch.manual_seed(0); np.random.seed(0)
    p = pd.read_csv(D / "pool_multiclasse.csv"); p = p[p.source != "busca_web"][["file", "subject_id", "source", "classe"]]
    # conj_seg: palpebra evertida (captura de palidez), nao e "olho normal" de foto comum
    p = p[p.source != "conj_seg"]
    # hf_pterygium: o "normal" dessa base tem catarata, palpebra inchada etc.; fica so no treino, nunca no teste
    p["so_treino"] = (p.source == "hf_pterygium") & (p.classe == "normal")
    w = pd.read_csv(D / "externos/labels_busca_web_verificado.csv")
    if a.web == "verificadas": w = w[w.verificado == 1]
    w = w[["file", "subject_id", "source", "classe", "metade"]]
    existe = lambda f: (D / f).exists()
    p = p[p.file.map(existe)]; w = w[w.file.map(existe)]
    wa, wb = w[w.metade == "A"], w[w.metade == "B"]
    tot = pd.concat([p, wa, wb]).groupby("classe").file.nunique(); CL = sorted([c for c, n in tot.items() if n >= a.min and c not in FORA and (not SO or c in SO)], key=lambda c: (c != "normal", c))
    print("classes:", {c: int(tot[c]) for c in CL}, "| fora (poucas fotos ou outra captura):", {c: int(n) for c, n in tot.items() if c not in CL})
    p = p[p.classe.isin(CL)]; wa = wa[wa.classe.isin(CL)]; wb = wb[wb.classe.isin(CL)]
    p["g"] = p.subject_id.astype(str).map(lambda s: int(hashlib.md5(s.encode()).hexdigest(), 16)); tr, te = [], []
    for c in CL:
        d = p[(p.classe == c) & ~p.so_treino]; d_extra = p[(p.classe == c) & p.so_treino]; gs = list(dict.fromkeys(d.g)); random.Random(1).shuffle(gs); alvo = min(200, max(int(0.3 * len(d)), 1)); tg, n = set(), 0
        for g in gs:
            if n >= alvo: break
            tg.add(g); n += int((d.g == g).sum())
        te.append(d[d.g.isin(tg)].head(200)); tr.append(pd.concat([wa[wa.classe == c], d[~d.g.isin(tg)], d_extra]).head(a.max_treino))
    tr, te = pd.concat(tr), pd.concat(te); print(pd.DataFrame({"treino": tr.classe.value_counts(), "teste": te.classe.value_counts(), "google": wb.classe.value_counts()}).fillna(0).astype(int).to_string())
    pd.concat([tr.assign(split="treino"), te.assign(split="teste"), wb.assign(split="google")]).to_csv(OUT / f"doencas_split_{TAG}.csv", index=False)
    b.CL = CL; m, size, mean, std = b.cria(a.modelo); m.reset_classifier(len(CL)); m = m.to(DEV)
    ttr = T.Compose([T.RandomResizedCrop(size, scale=(0.4, 1)), T.RandomHorizontalFlip(), T.RandomRotation(15), T.ColorJitter(0.3, 0.3, 0.15, 0.02), T.ToTensor(), T.Normalize(mean, std)])
    tte = T.Compose([T.Resize(int(size * 1.1)), T.CenterCrop(size), T.ToTensor(), T.Normalize(mean, std)])
    peso = tr.classe.map(1.0 / tr.classe.value_counts()).to_numpy()
    dl = DataLoader(b.DS(tr, ttr), batch_size=32, sampler=WeightedRandomSampler(torch.tensor(peso), num_samples=min(len(tr), 400 * len(CL)), replacement=True), num_workers=4, persistent_workers=True)
    lr = 5e-5; head = [q for n, q in m.named_parameters() if n.startswith(("head", "classifier", "fc."))]; hid = {id(q) for q in head}
    opt = torch.optim.AdamW([{"params": [q for q in m.parameters() if id(q) not in hid], "lr": lr}, {"params": head, "lr": lr * 10}], weight_decay=0.05)
    sch = torch.optim.lr_scheduler.OneCycleLR(opt, [lr, lr * 10], total_steps=a.epocas * len(dl), pct_start=0.15); t0 = time.time()
    for ep in range(a.epocas):
        m.train(); tl = 0
        for x, y in dl:
            x, y = x.to(DEV), y.to(DEV); loss = nn.functional.cross_entropy(m(x), y, label_smoothing=0.1); opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step(); sch.step(); tl += loss.item()
        print(f"ep {ep+1}/{a.epocas} loss {tl/len(dl):.3f} ({time.time()-t0:.0f}s)", flush=True)
    m.eval(); linhas = [f"# Doenças prioritárias · {a.modelo} · {len(CL)} classes\n"]
    for nome, d in (("teste separado", te), ("Google nunca visto", wb)):
        P, Y = [], []
        with torch.no_grad():
            for x, y in DataLoader(b.DS(d, tte), batch_size=32, num_workers=4): P.append(m(x.to(DEV)).argmax(1).cpu()); Y.append(y)
        P, Y = torch.cat(P).numpy(), torch.cat(Y).numpy(); por = {c: (P[Y == i] == i).mean() for i, c in enumerate(CL) if (Y == i).any()}
        linhas += [f"\n## {nome}: acurácia {(P == Y).mean():.1%} · média por classe {np.mean(list(por.values())):.1%} ({len(Y)} fotos)", "| classe | n | acerto | mais confundida com |", "|---|---:|---:|---|"]
        for i, c in enumerate(CL):
            k = Y == i
            if not k.any(): continue
            err = pd.Series([CL[j] for j in P[k] if j != i]).value_counts(); linhas.append(f"| {c} | {k.sum()} | {por[c]:.0%} | {', '.join(f'{x} {n}' for x, n in err.head(2).items())} |")
        # pergunta clinica do olho vermelho: urgente (uveite, ceratite, trauma) x nao urgente (conjuntivite, hiperemia, hemorragia)
        URG = {"uveite", "ceratite", "trauma_ocular"}; NURG = {"conjuntivite", "hiperemia", "hemorragia_subconjuntival"}
        k = np.array([CL[y] in URG | NURG for y in Y])
        if k.any():
            yv = np.array([CL[y] in URG for y in Y[k]]); pv = np.array([CL[q] in URG for q in P[k]])
            sens = (pv[yv]).mean() if yv.any() else float("nan"); esp = (~pv[~yv]).mean() if (~yv).any() else float("nan")
            linhas.append(f"\nOlho vermelho, urgente x não urgente ({k.sum()} fotos): urgentes reconhecidos {sens:.0%} · não urgentes corretamente não urgentes {esp:.0%}")
    md = "\n".join(linhas); print(md); (OUT / f"doencas_{a.modelo.split('.')[0]}_{TAG}.md").write_text(md)
    torch.save({"estado": m.state_dict(), "classes": CL, "modelo": a.modelo, "size": size, "mean": mean, "std": std}, OUT / f"doencas_{a.modelo.split('.')[0]}_{TAG}.pt")
if __name__ == "__main__":
    main()
