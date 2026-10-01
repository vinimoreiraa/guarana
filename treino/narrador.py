"""Protótipo do narrador: evidência estruturada do nosso modelo -> modelo de visão e linguagem escreve a explicação.
Nível 0 (decisão): P(doente) = 1 - P(normal) com corte conservador. Nível 1 (evidência): top-3 doenças, região do olho onde o
modelo olhou (gradiente x entrada, mapeado pela segmentação de fenda/íris), índice de cor da esclera vs olhos normais.
Nível 2 (narrador): VLM (Ollama) recebe a foto + evidência e escreve 2-3 frases em pt-BR, termo técnico + leigo, sem decidir.
Uso: .venv/bin/python treino/narrador.py --fotos a.jpg b.jpg [--vlm llama3.2-vision:11b]
"""
import argparse, base64, io, json, math, urllib.request
from pathlib import Path
import numpy as np, torch, timm, torchvision.transforms as T, onnxruntime as ort
from PIL import Image, ImageOps
BASE = Path(__file__).resolve().parents[1]; OUT = BASE / "saida"
NOME = {"normal": ("olho sem alterações", "sem achados"), "pterigio": ("pterígio", "carne crescendo sobre o olho"), "catarata_leucocoria": ("catarata / leucocoria", "pupila esbranquiçada"),
        "conjuntivite": ("conjuntivite", "olho vermelho por inflamação da membrana do olho"), "hiperemia": ("hiperemia conjuntival", "olho vermelho"), "uveite": ("uveíte anterior", "inflamação dentro do olho"),
        "ceratite": ("ceratite / úlcera de córnea", "ferida na parte transparente do olho"), "hemorragia_subconjuntival": ("hemorragia subconjuntival", "mancha de sangue no branco do olho"),
        "ictericia": ("icterícia", "branco do olho amarelado"), "alteracao_palpebral": ("alteração palpebral", "problema na pálpebra"), "lesao_pigmentada": ("lesão pigmentada conjuntival", "pinta escura no olho"),
        "trauma_ocular": ("trauma ocular", "lesão por pancada, corpo estranho ou queimadura")}
CORTE = 0.803   # limiar conservador de P(doente) escolhido no teste separado (97,8% de doentes detectados no Google)
def carrega():
    ck = torch.load(OUT / "doencas_vit_pe_core_small_patch16_384_todas.pt", map_location="cpu", weights_only=False)
    m = timm.create_model(ck["modelo"], pretrained=False, num_classes=len(ck["classes"])); m.load_state_dict(ck["estado"]); m.eval()
    tf = T.Compose([T.Resize(int(ck["size"] * 1.1)), T.CenterCrop(ck["size"]), T.ToTensor(), T.Normalize(ck["mean"], ck["std"])]); return m, tf, ck["classes"], ck["size"]
seg_card = json.load(open(OUT / "fenda_card.json")); seg = ort.InferenceSession(str(OUT / "fenda_v1.onnx"), providers=["CPUExecutionProvider"])
REF = json.load(open(OUT / "indices_referencia.json"))
def segmenta(im):
    S = seg_card["input"]["size"]; mean, std = np.array(seg_card["input"]["mean"], np.float32), np.array(seg_card["input"]["std"], np.float32)
    x = ((np.asarray(im.resize((S, S)), np.float32) / 255 - mean) / std).transpose(2, 0, 1)[None]; pr = 1 / (1 + np.exp(-seg.run(None, {"image": x})[0][0])); return pr[0] > 0.5, pr[1] > 0.5
def evidencia(m, tf, CL, size, path):
    im0 = ImageOps.exif_transpose(Image.open(path)).convert("RGB"); x = tf(im0)[None].requires_grad_(True)
    lg = m(x); p = torch.softmax(lg, 1)[0]; top = p.argsort(descending=True)[:3].tolist(); pdoente = float(1 - p[CL.index("normal")])
    alvo = top[0] if CL[top[0]] != "normal" else top[1]; lg[0, alvo].backward()
    sal = (x.grad[0] * x[0]).abs().sum(0).detach().numpy(); g = 24; h = sal.shape[0] // g; grid = sal[:g * h, :g * h].reshape(g, h, g, h).sum((1, 3))
    gy, gx = np.unravel_index(grid.argmax(), grid.shape); cy, cx = (gy + .5) / g, (gx + .5) / g
    # mesma geometria do recorte central do tf: imagem redimensionada e cortada no centro
    w, hh = im0.size; s = min(w, hh); crop = im0.crop(((w - s) // 2, (hh - s) // 2, (w - s) // 2 + s, (hh - s) // 2 + s)).resize((256, 256))
    fen, iri = segmenta(crop); py, px = int(cy * 255), int(cx * 255)
    if iri.any():
        ys, xs = np.nonzero(iri); icx, icy = xs.mean(), ys.mean(); r = max((xs.max() - xs.min()) / 2, 1); d = math.hypot(px - icx, py - icy) / r
        estrutura = "córnea/pupila" if d < 0.75 else ("limbo (transição córnea-esclera)" if d < 1.25 else ("esclera/conjuntiva bulbar" if fen[py, px] else "pálpebra ou pele ao redor"))
        lado = "lado esquerdo da foto" if px < icx - 0.3 * r else ("lado direito da foto" if px > icx + 0.3 * r else "centro")
    else: estrutura, lado = "região não identificada (íris não encontrada)", ""
    a = np.asarray(crop).astype(np.float32); esc = fen & ~iri & (a.max(axis=2) < 245)
    cor = None
    if esc.sum() > 100:
        e = a[esc].mean(0) + 1e-3; lnrb = math.log(e[0] / e[2]); pct = int(np.searchsorted(sorted([REF["ict_lnRB"][k] for k in ("p5", "p25", "p50", "p75", "p90", "p95", "p99")]), lnrb))
        cor = {"amarelado_ln_R_B": round(lnrb, 3), "comparado_a_olhos_normais": ["abaixo do p5", "p5-p25", "p25-p50", "p50-p75", "p75-p90", "p90-p95", "p95-p99", "acima do p99"][pct]}
    return {"decisao": "precisa de avaliação" if pdoente >= CORTE else "sem sinais", "p_doente": round(pdoente, 3),
            "provaveis": [{"condicao": NOME[CL[i]][0], "leigo": NOME[CL[i]][1], "prob": round(float(p[i]), 3)} for i in top],
            "onde_o_modelo_olhou": f"{estrutura}, {lado}".strip(", "), "cor_da_esclera": cor}
TIPICO = {"pterígio": "tecido fibrovascular em forma de asa, geralmente no lado nasal, avançando da conjuntiva bulbar sobre a córnea",
          "catarata / leucocoria": "opacidade branca ou acinzentada na pupila (reflexo pupilar esbranquiçado)",
          "icterícia": "coloração amarelada difusa da esclera",
          "uveíte anterior": "injeção ciliar (vermelhidão em anel ao redor da córnea), às vezes pupila pequena ou nível de pus (hipópio)",
          "ceratite / úlcera de córnea": "mancha esbranquiçada ou infiltrado na córnea, com olho vermelho",
          "conjuntivite": "vermelhidão difusa da conjuntiva, às vezes com secreção",
          "hiperemia conjuntival": "vasos da conjuntiva dilatados, sem lesão focal",
          "hemorragia subconjuntival": "mancha vermelho-viva e bem delimitada sob a conjuntiva",
          "alteração palpebral": "nódulo, inchaço, crosta ou queda da pálpebra",
          "lesão pigmentada conjuntival": "mancha marrom ou preta na conjuntiva",
          "trauma ocular": "corpo estranho, sangue na câmara anterior (hifema), queimadura ou laceração"}
def frase_fixa(ev):
    if ev["decisao"] == "sem sinais":
        return "Sem sinais que indiquem avaliação nesta foto (probabilidade de alteração " + f"{ev['p_doente']:.0%}" + ", abaixo do corte conservador)."
    t = next(x for x in ev["provaveis"] if x["condicao"] != "olho sem alterações")
    txt = f"Sinais compatíveis com {t['condicao']} ({t['leigo']}), {t['prob']:.0%} de probabilidade. A atenção do modelo se concentrou em: {ev['onde_o_modelo_olhou']}. O sinal típico é {TIPICO.get(t['condicao'], 'uma alteração visível nessa região')}."
    cor = ev.get("cor_da_esclera")
    if cor and t["condicao"] == "icterícia": txt += f" A cor da esclera medida está {cor['comparado_a_olhos_normais']} em relação a olhos normais."
    return txt
PROMPT = """Descreva em UMA frase, em português do Brasil, o que se vê na região "{regiao}" desta foto de olho, com termos anatômicos (conjuntiva bulbar, limbo, córnea, esclera, pupila, pálpebra).
Descreva só aparência (cor, forma, vasos, manchas). NÃO cite nome de doença, NÃO dê diagnóstico, NÃO dê recomendação."""
DOENCAS = ["pterígio", "catarata", "icterícia", "uveíte", "ceratite", "úlcera", "conjuntivite", "hiperemia", "hemorragia", "calázio", "terçol", "blefarite", "trauma", "glaucoma", "melanoma", "nevo", "pinguécula"]
def verifica(txt, ev):
    t = txt.lower(); motivos = []
    if any(d in t for d in DOENCAS): motivos.append("citou doença")
    cor = ev.get("cor_da_esclera") or {}
    if ("amarel" in t) and cor.get("comparado_a_olhos_normais") not in ("p95-p99", "acima do p99"): motivos.append("amarelado sem medição que sustente")
    if len(txt) > 400 or txt.count(".") > 3: motivos.append("longo demais")
    return motivos
def narra(vlm, path, ev):
    buf = io.BytesIO(); im = ImageOps.exif_transpose(Image.open(path)).convert("RGB"); im.thumbnail((768, 768)); im.save(buf, "JPEG", quality=90)
    body = {"model": vlm, "prompt": PROMPT.format(regiao=ev["onde_o_modelo_olhou"]), "images": [base64.b64encode(buf.getvalue()).decode()], "stream": False, "options": {"temperature": 0.1, "num_predict": 90, "repeat_penalty": 1.15}}
    req = urllib.request.Request("http://localhost:11434/api/generate", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r: desc = json.load(r)["response"].strip()
    base = frase_fixa(ev); mot = verifica(desc, ev) if ev["decisao"] != "sem sinais" else ["decisão sem sinais: só frase fixa"]
    return (base + (" Na foto: " + desc if not mot else "")), desc, mot
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--fotos", nargs="+"); ap.add_argument("--vlm", default="llama3.2-vision:11b"); a = ap.parse_args()
    m, tf, CL, size = carrega()
    for f in a.fotos:
        ev = evidencia(m, tf, CL, size, f); print(f"\n=== {Path(f).name}\nEVIDÊNCIA: {json.dumps(ev, ensure_ascii=False)}"); final, desc, mot = narra(a.vlm, f, ev); print("VLM BRUTO:", desc); print("VERIFICADOR:", mot or "aprovado"); print("TEXTO FINAL:", final, flush=True)
if __name__ == "__main__":
    main()
