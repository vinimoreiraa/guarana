"""Minera fotos clinicas de olho externo nas figuras do PubMed Central (base PubMedVision no Hugging Face), por termo
da legenda, guardando so o que e 'Digital Photography' do 'Eye'. A legenda vira a anotacao verbosa da imagem.
Passo 1 (este script): busca + filtro -> dados/raw/pubmed/candidatos.jsonl (id, termos, legenda, caminhos das imagens).
Passo 2 (baixar_pubmed.py): baixa as imagens dos candidatos.
Uso: .venv/bin/python treino/minerar_pubmed.py [--max 400]
"""
import argparse, json, time, urllib.parse, urllib.request
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]; OUT = BASE / "dados/raw/pubmed"; OUT.mkdir(parents=True, exist_ok=True)
DS = "FreedomIntelligence/PubMedVision"; CFG = "_Original_Caption"
# termo de busca -> rotulo(s) do Guarana (ou marcador para revisao). Quem decide o rotulo final e a legenda, revisada.
TERMOS = {
    "pterygium": ["pterigio"], "pinguecula": ["pinguecula"], "subconjunctival hemorrhage": ["hemorragia_subconjuntival"],
    "subconjunctival haemorrhage": ["hemorragia_subconjuntival"], "conjunctival nevus": ["lesao_pigmentada"], "conjunctival melanoma": ["lesao_pigmentada", "tumor_superficie_ocular"],
    "conjunctival melanosis": ["lesao_pigmentada"], "ocular surface squamous neoplasia": ["tumor_superficie_ocular"], "conjunctival papilloma": ["tumor_superficie_ocular"],
    "conjunctival cyst": ["cisto_conjuntival"], "corneal opacity": ["opacidade_corneana"], "corneal scar": ["opacidade_corneana"], "leukoma": ["opacidade_corneana"],
    "keratitis": ["ceratite"], "corneal ulcer": ["ceratite"], "cataract": ["catarata_leucocoria"], "leukocoria": ["catarata_leucocoria"], "white pupil": ["catarata_leucocoria"],
    "scleral icterus": ["ictericia"], "jaundice sclera": ["ictericia"], "conjunctival pallor": ["palidez_conjuntival"], "pallor conjunctiva": ["palidez_conjuntival"],
    "conjunctival injection": ["hiperemia"], "conjunctival hyperemia": ["hiperemia"], "red eye": ["hiperemia"], "conjunctivitis": ["conjuntivite", "hiperemia"],
    "episcleritis": ["hiperemia"], "scleritis": ["hiperemia"], "anterior uveitis": ["uveite"], "ciliary flush": ["uveite"], "hypopyon": ["uveite"],
    "chalazion": ["alteracao_palpebral"], "hordeolum": ["alteracao_palpebral"], "stye": ["alteracao_palpebral"], "blepharitis": ["alteracao_palpebral"], "ptosis": ["alteracao_palpebral"],
    "xanthelasma": ["alteracao_palpebral"], "trichiasis": ["alteracao_palpebral"], "entropion": ["alteracao_palpebral"], "ectropion": ["alteracao_palpebral"],
    "intraocular lens": ["lente_intraocular"], "pseudophakia": ["lente_intraocular"], "arcus senilis": ["arco_corneano"], "corneal arcus": ["arco_corneano"],
    "blue sclera": ["esclera_azul"], "bitot": ["manchas_bitot"], "ochronosis": ["ocronose"], "telangiectasia conjunctiva": ["telangiectasia"], "proptosis": ["proptose"],
}
EXCLUIR = ("histolog", "microscop", "oct ", "optical coherence", "fundus", "retina", "angiograph", "ultrasound", "mri", "ct scan", "computed tomography", "gonioscop", "specular", "topograph", "schematic", "diagram", "flow chart", "immunohisto", "h&e", "hematoxylin", "biopsy specimen")

def buscar(termo, offset, length=100):
    url = f"https://datasets-server.huggingface.co/search?dataset={urllib.parse.quote(DS, safe='')}&config={CFG}&split=train&query={urllib.parse.quote(termo)}&offset={offset}&length={length}"
    for tent in range(6):
        try:
            with urllib.request.urlopen(url, timeout=60) as r: return json.load(r)
        except Exception as e:
            time.sleep(8 + 8 * tent)
    return {}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--max", type=int, default=400, help="maximo de linhas varridas por termo"); a = ap.parse_args()
    vistos = {}; resumo = {}
    for termo, rotulos in TERMOS.items():
        total = 0; aceitos = 0; offset = 0
        while offset < a.max:
            d = buscar(termo, offset)
            rows = d.get("rows", []); total = d.get("num_rows_total", 0)
            if not rows: break
            for r in rows:
                row = r["row"]; cap = (row.get("Original_Caption") or ""); capl = cap.lower()
                # etiquetas da base sao imperfeitas: fotos clinicas aparecem como "Digital Photography" e tambem como "Endoscopy";
                # a parte do corpo vem como Eye, Others, Face ou Head. Microscopia, OCT, fundo e tomografia ficam de fora.
                mod = row.get("modality") or ""; parte = row.get("body_part") or ""
                foto = mod in ("Digital Photography", "Endoscopy") or (parte == "Eye" and ("photograph" in capl or "clinical picture" in capl or "clinical photo" in capl))
                if not foto or parte not in ("Eye", "Others", "Face", "Head") or any(x in capl for x in EXCLUIR): continue
                if termo.lower() not in capl: continue   # a busca e por palavras soltas; exige a frase exata na legenda
                if "slit" in capl: continue               # lampada de fenda ja temos de sobra; queremos foto comum
                rid = row.get("id")
                item = vistos.setdefault(rid, {"id": rid, "termos": [], "rotulos": [], "caption": cap, "images": row.get("image") or []})
                if termo not in item["termos"]: item["termos"].append(termo)
                for l in rotulos:
                    if l not in item["rotulos"]: item["rotulos"].append(l)
                aceitos += 1
            offset += len(rows)
            if offset >= total: break
        resumo[termo] = {"encontrados": total, "fotos_de_olho": aceitos}
        print(f"{termo:34s} encontrados {total:6d} | fotos de olho aceitas {aceitos:5d}", flush=True)
    with (OUT / "candidatos.jsonl").open("w") as f:
        for it in vistos.values(): f.write(json.dumps(it, ensure_ascii=False) + "\n")
    (OUT / "resumo_busca.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False))
    print("candidatos unicos:", len(vistos), "| imagens:", sum(len(v["images"]) for v in vistos.values()))

if __name__ == "__main__":
    main()
