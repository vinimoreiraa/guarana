"""Rotula fotos de olho externo com o Claude (visao + saida estruturada) e gera um labels_claude.csv
no formato do notebook. Rotulos "incerto" viram 0 e entram na coluna `revisar` para conferencia humana.

Uso:
  export ANTHROPIC_API_KEY=...   (ou `ant auth login`)
  python rotular_com_claude.py --imagens ../dados/brutas --saida ../dados/labels_claude.csv --idade 40
"""
import argparse, base64, csv, json, sys
from pathlib import Path
import anthropic

MODEL = "claude-opus-5-5"
EXTS = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
SINAIS = ["hiperemia", "ictericia", "palidez_conjuntival", "arco_corneano", "opacidade_corneana", "esclera_azul",
          "hemorragia_subconjuntival", "pterigio_pinguecula", "manchas_bitot", "ocronose", "telangiectasia",
          "lesao_pigmentada", "catarata_leucocoria"]

DEFINICOES = """Voce e um assistente de triagem que descreve sinais VISIVEIS em uma foto comum do olho externo
(cornea, esclera, conjuntiva, cristalino). Nunca diagnostica; apenas marca cada sinal como presente, incerto ou ausente.
Se a foto nao mostrar um olho, ou estiver desfocada/escura demais, marque qualidade_ok = false e todos os sinais como incerto.

Definicoes:
- hiperemia: vermelhidao difusa da esclera/conjuntiva (vasos dilatados espalhados).
- ictericia: amarelo DIFUSO e liso em toda a esclera. Nao confundir com pinguecula (amarelo local, com relevo, ao lado da cornea).
- palidez_conjuntival: conjuntiva palpebral (palpebra inferior puxada) palida/rosada clara em vez de vermelha viva.
- arco_corneano: anel branco-acinzentado na periferia da cornea, separado da borda por faixa clara.
- opacidade_corneana: cornea perde transparencia, aspecto de vidro fosco difuso.
- esclera_azul: tom azulado difuso de toda a esclera.
- hemorragia_subconjuntival: mancha vermelho-viva, bem delimitada, sobre esclera branca.
- pterigio_pinguecula: elevacao amarelada na conjuntiva ao lado da cornea (pinguecula) ou tecido avancando sobre a cornea (pterigio).
- manchas_bitot: placas esbranquicadas, secas, espumosas na conjuntiva ao lado da cornea.
- ocronose: pigmentacao acinzentada a acastanhada da esclera, em placas perto do limbo/insercao dos musculos.
- telangiectasia: vasos da conjuntiva dilatados e tortuosos, bem visiveis sobre a esclera.
- lesao_pigmentada: mancha pigmentada acastanhada na conjuntiva (nevo, melanose ou melanoma; nao separar).
- catarata_leucocoria: pupila esbranquicada/acinzentada, cristalino opaco atras da pupila.

Regra: na duvida entre presente e ausente, responda incerto. Seja conservador com "presente".
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "qualidade_ok": {"type": "boolean"},
        "sinais": {
            "type": "object",
            "properties": {s: {"type": "string", "enum": ["presente", "incerto", "ausente"]} for s in SINAIS},
            "required": SINAIS,
            "additionalProperties": False,
        },
        "observacao": {"type": "string"},
    },
    "required": ["qualidade_ok", "sinais", "observacao"],
    "additionalProperties": False,
}


def rotular(client, path, idade):
    b64 = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=1024,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=[{"type": "text", "text": DEFINICOES, "cache_control": {"type": "ephemeral"}}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}, "effort": "low"},
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": EXTS[path.suffix.lower()], "data": b64}},
            {"type": "text", "text": f"Idade aproximada da pessoa: {idade if idade else 'desconhecida'}. Classifique a foto."},
        ]}],
    )
    if resp.stop_reason == "refusal":
        return None
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--imagens", required=True, help="pasta com as fotos (pode ter subpastas)")
    ap.add_argument("--saida", required=True, help="labels_claude.csv a gerar")
    ap.add_argument("--raiz", default=None, help="DATA_DIR do notebook, para gravar caminhos relativos (padrao: pasta pai de --imagens)")
    ap.add_argument("--idade", type=int, default=None)
    ap.add_argument("--fonte", default="claude")
    args = ap.parse_args()

    root = Path(args.raiz) if args.raiz else Path(args.imagens).resolve().parent
    files = sorted(p for p in Path(args.imagens).rglob("*") if p.suffix.lower() in EXTS)
    if not files:
        sys.exit("nenhuma imagem encontrada")
    client = anthropic.Anthropic()
    out = Path(args.saida)
    done = set()
    if out.exists():
        with out.open(encoding="utf-8") as f:
            done = {r["file"] for r in csv.DictReader(f)}
    cols = ["file", "subject_id", "source", *SINAIS, "revisar", "qualidade_ok", "observacao"]
    write_header = not out.exists()
    with out.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if write_header:
            w.writeheader()
        for i, p in enumerate(files, 1):
            rel = str(p.resolve().relative_to(root.resolve()))
            if rel in done:
                continue
            try:
                r = rotular(client, p, args.idade)
            except anthropic.RateLimitError:
                print("rate limit; rode de novo depois, o CSV e retomavel"); break
            except anthropic.APIStatusError as e:
                print(f"{rel}: erro {e.status_code}, pulando"); continue
            if r is None:
                print(f"{rel}: recusado, pulando"); continue
            row = {"file": rel, "subject_id": f"{args.fonte}_{p.stem}", "source": args.fonte,
                   "qualidade_ok": int(r["qualidade_ok"]), "observacao": r["observacao"].replace("\n", " ")}
            incertos = []
            for s in SINAIS:
                v = r["sinais"][s]
                row[s] = int(v == "presente")
                if v == "incerto":
                    incertos.append(s)
            row["revisar"] = ";".join(incertos)
            w.writerow(row); f.flush()
            print(f"[{i}/{len(files)}] {rel}: " + ", ".join(s for s in SINAIS if row[s]) + (f" | revisar: {row['revisar']}" if incertos else ""))
    print("pronto:", out)


if __name__ == "__main__":
    main()
