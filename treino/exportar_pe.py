"""Exporta o modelo de doencas (Perception Encoder S, multiclasse) para o app: ONNX com duas saidas
- "probs": softmax por doenca [1, n]
- "atencao": onde o pool de atencao do modelo olhou [1, 24, 24] (media das cabecas, sem o token CLS)
e o cartao (saida/<versao>_card.json): classes, entrada, corte conservador de P(doente) = 1 - P(normal).
Uso: .venv/bin/python treino/exportar_pe.py --tag geral --versao ocular_v23 [--sens 0.99]
"""
import argparse, json, datetime
from pathlib import Path
import numpy as np, pandas as pd, torch, torch.nn as nn, timm, onnxruntime as ort, torchvision.transforms as T
from PIL import Image, ImageOps
BASE = Path(__file__).resolve().parents[1]; OUT = BASE / "saida"
class ComAtencao(nn.Module):
    def __init__(s, m): super().__init__(); s.m = m
    def forward(s, x):
        m = s.m; t = m.forward_features(x)                       # [1, 577, C]
        ap = m.attn_pool; B, N, C = t.shape; tt = t + ap.pos_embed.unsqueeze(0) if ap.pos_embed is not None else t
        q = ap.q(ap.latent.expand(B, -1, -1)).reshape(B, ap.latent_len, ap.num_heads, ap.head_dim).transpose(1, 2)
        k = ap.kv(tt).reshape(B, N, 2, ap.num_heads, ap.head_dim).permute(2, 0, 3, 1, 4)[0]
        q, k = ap.q_norm(q), ap.k_norm(k); a = ((q * ap.scale) @ k.transpose(-2, -1)).softmax(-1)   # [B, H, L, N]
        att = a.mean(1)[:, 0, 1:]; g = 24
        return torch.softmax(m.forward_head(t), 1), att.reshape(B, g, g)
def main():
    ap_ = argparse.ArgumentParser(); ap_.add_argument("--tag", default="geral"); ap_.add_argument("--versao", default="ocular_v23"); ap_.add_argument("--sens", type=float, default=0.99); a = ap_.parse_args()
    ck = torch.load(OUT / f"doencas_vit_pe_core_small_patch16_384_{a.tag}.pt", map_location="cpu", weights_only=False); CL = ck["classes"]; size = ck["size"]
    m = timm.create_model(ck["modelo"], pretrained=False, num_classes=len(CL)); m.load_state_dict(ck["estado"]); m.eval()
    w = ComAtencao(m).eval(); x = torch.randn(1, 3, size, size)
    with torch.no_grad(): p_t, a_t = w(x)
    onnx_p = OUT / f"{a.versao}.onnx"
    torch.onnx.export(w, x, onnx_p, input_names=["image"], output_names=["probs", "atencao"], opset_version=17, dynamo=False)
    s = ort.InferenceSession(str(onnx_p), providers=["CPUExecutionProvider"]); p_o, a_o = s.run(None, {"image": x.numpy()})
    print("paridade probs", float(np.abs(p_o - p_t.numpy()).max()), "| atencao", float(np.abs(a_o - a_t.numpy()).max()), "| forma atencao", a_o.shape)
    # corte conservador no TESTE SEPARADO (nunca no Google): sensibilidade alvo para doente
    sp = pd.read_csv(OUT / f"doencas_split_{a.tag}.csv"); te = sp[sp.split == "teste"]
    tf = T.Compose([T.Resize(int(size * 1.1)), T.CenterCrop(size), T.ToTensor(), T.Normalize(ck["mean"], ck["std"])])
    pd_ = []
    for f in te.file:
        pr = s.run(None, {"image": tf(ImageOps.exif_transpose(Image.open(BASE / "dados" / f)).convert("RGB"))[None].numpy()})[0][0]; pd_.append(1 - pr[CL.index("normal")])
    pd_ = np.array(pd_); doente = (te.classe != "normal").to_numpy(); corte = float(np.sort(pd_[doente])[int((1 - a.sens) * doente.sum())])
    print(f"corte P(doente) = {corte:.3f} | no teste: doentes detectados {(pd_[doente] >= corte).mean():.1%}, saudáveis liberados {(pd_[~doente] < corte).mean():.1%}")
    card = {"name": a.versao, "task": "multiclasse", "created": datetime.date.today().isoformat(), "backbone": ck["modelo"], "classes": CL,
            "input": {"size": size, "mean": list(ck["mean"]), "std": list(ck["std"]), "layout": "NCHW", "range": "0-1 normalizado"},
            "output": {"probs": "softmax por classe, na ordem de classes", "atencao": "mapa 24x24 do pool de atencao (onde o modelo olhou)"},
            "corte_doente": round(corte, 4), "regra": f"P(doente)=1-P(normal) >= corte_doente -> precisa de avaliacao (sensibilidade alvo {a.sens:.0%} no teste separado)",
            "files": {"fp32": onnx_p.name, "recommended": onnx_p.name}, "thresholds": {c: 0.5 for c in CL}, "unreliable_labels": [],
            "nota": "Decisao conservadora saudavel x precisa de avaliacao; doencas como explicacao. Teste separado e Google nunca visto em saida/doencas_vit_pe_core_small_patch16_384_" + a.tag + ".md"}
    json.dump(card, open(OUT / f"{a.versao}_card.json", "w"), indent=2, ensure_ascii=False); print("cartao", OUT / f"{a.versao}_card.json", "| onnx MB", round(onnx_p.stat().st_size / 1e6, 1))
if __name__ == "__main__":
    main()
