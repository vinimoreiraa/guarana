"""Transforma as figuras mineradas do PubMed em recortes de olho para o treino/validacao:
1. separa figuras compostas (paineis A-F) pelas calhas brancas entre paineis;
2. em cada painel roda o detector de enquadramento (saida/enquadramento_v1.onnx): fica so o que e foto de olho
   (OK, TOO_CLOSE ou OFF_CENTER), o resto (grafico, texto, olho longe, sem olho) e descartado;
3. salva dados/crops/pubmed/<figura>_<painel>.jpg e dados/labels_pubmed.csv com os rotulos vindos dos termos da
   legenda e a propria legenda em `caption` (anotacao verbosa), dominio "clinical_photo", revisar=1 (o rotulo e da figura
   inteira: se um painel e "antes" e outro "depois da cirurgia", a legenda diz, mas o CSV nao sabe; revisar antes de treinar).
Uso: .venv/bin/python treino/preparar_pubmed.py
"""
import csv, json
from pathlib import Path
import numpy as np, onnxruntime as ort
from PIL import Image
BASE = Path(__file__).resolve().parents[1]; RAW = BASE / "dados/raw/pubmed"; CROPS = BASE / "dados/crops/pubmed"; CROPS.mkdir(parents=True, exist_ok=True)
LABELS = ["hiperemia", "ictericia", "pterigio", "pinguecula", "catarata_leucocoria", "hemorragia_subconjuntival", "lesao_pigmentada", "opacidade_corneana",
          "tumor_superficie_ocular", "ceratite", "cisto_conjuntival", "lente_intraocular", "conjuntivite", "uveite", "alteracao_palpebral",
          "palidez_conjuntival", "arco_corneano", "esclera_azul", "manchas_bitot", "ocronose", "telangiectasia", "proptose"]
enq = json.load(open(BASE / "saida/enquadramento_card.json")); sess = ort.InferenceSession(str(BASE / "saida/enquadramento_v1.onnx"), providers=["CPUExecutionProvider"])

def framing(im):
    g = im.convert("L"); ratio = max(g.size) / min(g.size)
    if ratio <= 1.4: s = min(g.size); g = g.crop(((g.width - s) // 2, (g.height - s) // 2, (g.width - s) // 2 + s, (g.height - s) // 2 + s))
    else: s = max(g.size); c = Image.new("L", (s, s), 128); c.paste(g, ((s - g.width) // 2, (s - g.height) // 2)); g = c
    x = ((np.asarray(g.resize((enq["input"]["size"],) * 2), np.float32) / 255 - enq["input"]["mean"]) / enq["input"]["std"])[None].repeat(3, 0)[None]
    lg = sess.run(None, {"image": x})[0][0]; p = np.exp(lg - lg.max()); p /= p.sum(); k = int(p.argmax())
    return enq["classes"][k], float(p[k])

def split_panels(im, min_side=120):
    """corta pelas linhas/colunas quase brancas (ou quase pretas) que atravessam a figura; recursivo ate 2 niveis"""
    a = np.asarray(im.convert("L"), np.float32)
    def cuts(arr, axis):
        prof = (arr > 235).mean(axis=axis) + (arr < 20).mean(axis=axis)   # fracao de pixels de fundo por linha/coluna
        gut = prof > 0.97; edges = []; inside = False
        for i, g in enumerate(gut):
            if g and not inside: inside = True; start = i
            if not g and inside: inside = False; edges.append((start, i))
        return [(s, e) for s, e in edges if e - s >= 3 and s > 5 and e < len(gut) - 5]
    out = []
    def rec(box, depth):
        x0, y0, x1, y1 = box; sub = a[y0:y1, x0:x1]
        if depth > 2 or min(x1 - x0, y1 - y0) < min_side: 
            if min(x1 - x0, y1 - y0) >= min_side: out.append(box)
            return
        rows = cuts(sub, 1); cols = cuts(sub, 0)
        if not rows and not cols: out.append(box); return
        segs = []
        if rows and (not cols or len(rows) >= len(cols)):
            last = 0
            for s, e in rows: segs.append((x0, y0 + last, x1, y0 + s)); last = e
            segs.append((x0, y0 + last, x1, y1))
        else:
            last = 0
            for s, e in cols: segs.append((x0 + last, y0, x0 + s, y1)); last = e
            segs.append((x0 + last, y0, x1, y1))
        for sb in segs:
            if sb[2] - sb[0] >= min_side and sb[3] - sb[1] >= min_side: rec(sb, depth + 1)
    rec((0, 0, im.width, im.height), 0)
    return out or [(0, 0, im.width, im.height)]

def main():
    legendas = [json.loads(l) for l in (RAW / "legendas.jsonl").open()] if (RAW / "legendas.jsonl").exists() else []
    rows = []; kept = 0; seen = 0
    for it in legendas:
        p = RAW / "images" / it["image"]
        if not p.exists(): continue
        try: im = Image.open(p).convert("RGB")
        except Exception: continue
        for k, (x0, y0, x1, y1) in enumerate(split_panels(im)):
            panel = im.crop((x0, y0, x1, y1)); seen += 1
            cls, conf = framing(panel)
            if cls not in ("OK", "TOO_CLOSE", "OFF_CENTER") or conf < 0.5: continue
            out = CROPS / f"{Path(it['image']).stem}_p{k}.jpg"; panel.save(out, "JPEG", quality=92); kept += 1
            r = {"file": str(out.relative_to(BASE / "dados")), "subject_id": f"pmc_{it['id']}", "source": "pubmed", "domain": "clinical_photo", "revisar": 1,
                 "caption": it["caption"].replace("\n", " ")[:500], "termos": "|".join(it["termos"]), "enquadramento": cls}
            for l in LABELS: r[l] = int(l in it["rotulos"])
            rows.append(r)
    with (BASE / "dados/labels_pubmed.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "subject_id", "source", "domain", *LABELS, "revisar", "caption", "termos", "enquadramento"]); w.writeheader(); w.writerows(rows)
    pos = {l: sum(r[l] for r in rows) for l in LABELS if sum(r[l] for r in rows)}
    print(f"paineis vistos {seen} | recortes de olho {kept} | positivos {pos}")

if __name__ == "__main__":
    main()
