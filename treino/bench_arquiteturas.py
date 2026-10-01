"""Banco de arquiteturas com a MESMA regua: split fixo (saida/bench_split.csv) de 4 classes (normal, conjuntivite, pterigio,
catarata), 300 por classe no treino (inclui metade A das fotos da busca de imagens), 200 por classe no teste separado por paciente,
e um segundo teste = metade B das fotos da busca ("Google", nunca vistas). Ajuste fino completo, mesmos aumentos, mesmas epocas.
Reporta ACURACIA nos dois testes, por classe, parametros, tempo de treino e latencia na CPU (1 imagem).
Uso: .venv/bin/python treino/bench_arquiteturas.py --modelos mobilenetv3_large_100 convnext_tiny.dinov3_lvd1689m ... [--split-novo]
Modelos especiais: eyeclip (CLIP ViT-B/32 oftalmico), visionfm_externo (ViT-B/16 VisionFM External Eye, so pesquisa).
Resultados acumulam em saida/bench_arquiteturas.csv e .md.
"""
import argparse, hashlib, json, os, random, time
from pathlib import Path
import numpy as np, pandas as pd, torch, torch.nn as nn, timm, torchvision.transforms as T
from PIL import Image, ImageOps
from torch.utils.data import Dataset, DataLoader
BASE = Path(__file__).resolve().parents[1]; D = BASE / "dados"; OUT = BASE / "saida"; DEV = "mps" if torch.backends.mps.is_available() else "cpu"
CL = ["normal", "conjuntivite", "pterigio", "catarata_leucocoria"]
CASOS = ["/Users/Vinicius/Desktop/blog-donato-1.png", str(BASE / "validacao/casos/pterigio_usuario_01.jpg")]

def faz_split():
    p = pd.read_csv(D / "pool_multiclasse.csv"); p = p[p.classe.isin(CL) & (p.source != "busca_web")]
    w = pd.read_csv(D / "externos/labels_busca_web.csv").drop_duplicates("file"); w = w[w.classe.isin(CL)]
    p = pd.concat([p, w[w.metade == "A"]], ignore_index=True); p["grupo"] = p["subject_id"].astype(str).map(lambda s: int(hashlib.md5(s.encode()).hexdigest(), 16))
    rows = []
    for c in CL:
        d = p[p.classe == c].sample(frac=1, random_state=0); nao_web = d[d.source != "busca_web"]; grupos = list(dict.fromkeys(nao_web.grupo)); random.Random(1).shuffle(grupos)
        tg, n = set(), 0
        for g in grupos:
            if n >= 200: break
            tg.add(g); n += int((nao_web.grupo == g).sum())
        te = nao_web[nao_web.grupo.isin(tg)].head(200); resto = d[~d.grupo.isin(tg)]
        tr = pd.concat([resto[resto.source == "busca_web"], resto[resto.source != "busca_web"]]).head(300)
        rows += [tr.assign(split="treino"), te.assign(split="teste")]
    wb = w[w.metade == "B"].assign(split="google")
    s = pd.concat(rows + [wb], ignore_index=True)[["file", "subject_id", "source", "classe", "split"]]; s.to_csv(OUT / "bench_split.csv", index=False)
    print(pd.crosstab(s.classe, s.split).to_string()); return s

def cria(nome):
    """devolve (modelo, tamanho de entrada, media, desvio)"""
    if nome == "eyeclip":
        from timm.models.vision_transformer import _convert_openai_clip
        m = timm.create_model("vit_base_patch32_clip_224.openai", pretrained=False, num_classes=0)
        sd = torch.load(D / "pesos/eyeclip_visual.pt", map_location="cpu", weights_only=False)["model_state_dict"]
        sd = _convert_openai_clip(sd, m); sd = {k: v for k, v in sd.items() if not k.startswith("head")}; r = m.load_state_dict(sd, strict=False); print("eyeclip faltando", r.missing_keys[:4])
        m.reset_classifier(len(CL)); return m, 224, (0.48145466, 0.4578275, 0.40821073), (0.26862954, 0.26130258, 0.27577711)
    if nome == "visionfm_externo":
        m = timm.create_model("vit_base_patch16_224", pretrained=False, num_classes=len(CL))
        v = torch.load(D / "pesos/VFM_External_weights.pth", map_location="cpu", weights_only=False)["teacher"]
        sd = {k.replace("backbone.", ""): x for k, x in v.items() if k.startswith("backbone.")}; r = m.load_state_dict(sd, strict=False); print("visionfm faltando", r.missing_keys[:4])
        return m, 224, (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
    kw = {}
    m = timm.create_model(nome, pretrained=True, num_classes=len(CL), **kw); cfg = timm.data.resolve_data_config({}, model=m)
    size = cfg["input_size"][-1]; size = min(size, 384)
    return m, size, cfg["mean"], cfg["std"]

class DS(Dataset):
    def __init__(s, d, tf): s.d, s.tf = d.reset_index(drop=True), tf
    def __len__(s): return len(s.d)
    def __getitem__(s, i):
        r = s.d.iloc[i]; return s.tf(ImageOps.exif_transpose(Image.open(D / r.file)).convert("RGB")), CL.index(r.classe)

def roda(nome, split, epocas):
    torch.manual_seed(0); random.seed(0); np.random.seed(0)
    m, size, mean, std = cria(nome); m = m.to(DEV); npar = sum(p.numel() for p in m.parameters()) / 1e6
    ttr = T.Compose([T.RandomResizedCrop(size, scale=(0.4, 1)), T.RandomHorizontalFlip(), T.RandomRotation(15), T.ColorJitter(0.3, 0.3, 0.2, 0.02), T.ToTensor(), T.Normalize(mean, std)])
    tte = T.Compose([T.Resize(int(size * 1.1)), T.CenterCrop(size), T.ToTensor(), T.Normalize(mean, std)])
    grande = npar > 60; bs = 16 if grande else 32
    dl = DataLoader(DS(split[split.split == "treino"], ttr), batch_size=bs, shuffle=True, num_workers=4, persistent_workers=True)
    transformer = any(k in nome for k in ("vit", "eva", "clip", "siglip", "pe_core", "tips", "eyeclip", "visionfm"))
    lr = 5e-5 if transformer else 3e-4
    head = [p for n, p in m.named_parameters() if n.startswith(("head", "classifier", "fc."))]; hid = {id(p) for p in head}
    opt = torch.optim.AdamW([{"params": [p for p in m.parameters() if id(p) not in hid], "lr": lr}, {"params": head, "lr": lr * 10}], weight_decay=0.05 if transformer else 1e-4)
    sch = torch.optim.lr_scheduler.OneCycleLR(opt, [lr, lr * 10], total_steps=epocas * len(dl), pct_start=0.15)
    t0 = time.time()
    for ep in range(epocas):
        m.train(); tl = 0
        for x, y in dl:
            x, y = x.to(DEV), y.to(DEV); loss = nn.functional.cross_entropy(m(x), y, label_smoothing=0.1); opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step(); sch.step(); tl += loss.item()
        print(f"  {nome} ep {ep+1}/{epocas} loss {tl/len(dl):.3f} ({time.time()-t0:.0f}s)", flush=True)
    ttreino = time.time() - t0; m.eval(); res = {"modelo": nome, "params_M": round(npar, 1), "entrada": size, "treino_min": round(ttreino / 60, 1)}
    for sp in ("teste", "google"):
        d = split[split.split == sp]; P, Y = [], []
        with torch.no_grad():
            for x, y in DataLoader(DS(d, tte), batch_size=32, num_workers=4): P.append(m(x.to(DEV)).argmax(1).cpu()); Y.append(y)
        P, Y = torch.cat(P).numpy(), torch.cat(Y).numpy(); res[f"acc_{sp}"] = round(float((P == Y).mean()) * 100, 1); res[f"n_{sp}"] = len(Y)
        for i, c in enumerate(CL):
            if (Y == i).sum(): res[f"{sp}_{c}"] = round(float((P[Y == i] == i).mean()) * 100, 1)
    with torch.no_grad():
        for k, f in enumerate(CASOS):
            pr = torch.softmax(m(tte(ImageOps.exif_transpose(Image.open(f)).convert("RGB"))[None].to(DEV)), 1)[0].cpu().numpy(); res[f"caso{k+1}"] = f"{CL[int(pr.argmax())]} {pr.max():.2f}"
    mc = m.to("cpu"); x = torch.randn(1, 3, size, size)
    with torch.no_grad():
        for _ in range(3): mc(x)
        t1 = time.time()
        for _ in range(10): mc(x)
    res["lat_cpu_ms"] = round((time.time() - t1) / 10 * 1000); print(json.dumps(res, ensure_ascii=False), flush=True)
    torch.save(m.state_dict(), OUT / f"bench_{nome.replace('/', '_')}.pt"); del m; torch.mps.empty_cache() if DEV == "mps" else None
    return res

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--modelos", nargs="+", required=True); ap.add_argument("--epocas", type=int, default=12); ap.add_argument("--split-novo", action="store_true"); a = ap.parse_args()
    split = faz_split() if (a.split_novo or not (OUT / "bench_split.csv").exists()) else pd.read_csv(OUT / "bench_split.csv")
    csv = OUT / "bench_arquiteturas.csv"
    for nome in a.modelos:
        try: r = roda(nome, split, a.epocas)
        except Exception as e: import traceback; traceback.print_exc(); r = {"modelo": nome, "erro": str(e)[:200]}
        df = pd.concat([pd.read_csv(csv), pd.DataFrame([r])]) if csv.exists() else pd.DataFrame([r]); df = df.drop_duplicates("modelo", keep="last"); df.to_csv(csv, index=False)
        cols = [c for c in ["modelo", "params_M", "entrada", "acc_teste", "acc_google", "google_pterigio", "google_conjuntivite", "google_catarata_leucocoria", "google_normal", "caso1", "caso2", "lat_cpu_ms", "treino_min", "erro"] if c in df.columns]
        (OUT / "bench_arquiteturas.md").write_text("# Banco de arquiteturas (mesma régua)\n\n" + df.sort_values("acc_google", ascending=False)[cols].to_markdown(index=False))
if __name__ == "__main__":
    main()
