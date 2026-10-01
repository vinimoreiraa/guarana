"""Monta os dados do painel de planejamento a partir de fontes públicas.

IBGE Censo 2022 (tabela 9514: população total e de 60+ por município),
IBGE malha municipal, CNES Profissionais (PF{UF}{AAMM}.dbc, CBO 225265).
Saída: planejamento/dados_{UF}.json
"""
import gzip, json, sys, urllib.request, collections, pathlib
from dbfread import DBF

UF, COD_UF, COMP = sys.argv[1:4] if len(sys.argv) > 3 else ("AM", "13", "2608")
PF_DBF = sys.argv[4] if len(sys.argv) > 4 else f"PF{UF}{COMP}.dbf"
SAIDA = pathlib.Path(__file__).parent / f"dados_{UF}.json"
IDADES_20 = "93087,93088,93089,93090,93091,93092,93093,93094"
IDADES_60 = "93095,93096,93097,93098,49108,49109,60040,60041,6653"


def get(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        b = r.read()
    return json.loads(gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b)


def sidra(cats):
    url = (f"https://servicodados.ibge.gov.br/api/v3/agregados/9514/periodos/2022/variaveis/93"
           f"?localidades=N6[N3[{COD_UF}]]&classificacao=2[6794]|287[{cats}]|286[113635]")
    soma = collections.Counter()
    nomes = {}
    for cat in get(url)[0]["resultados"]:
        for s in cat["series"]:
            cod = s["localidade"]["id"]
            nomes[cod] = s["localidade"]["nome"].rsplit(" - ", 1)[0]
            v = s["serie"]["2022"]
            soma[cod] += int(v) if v not in ("-", "...", "X") else 0
    return soma, nomes


pop, nomes = sidra("100362")
pop60, _ = sidra(IDADES_60)
pop20, _ = sidra(IDADES_20 + "," + IDADES_60)

# região geográfica imediata (IBGE): agrupamento oficial próximo das regiões de saúde
imediata = {str(m["id"]): m["regiao-imediata"]["nome"]
            for m in get(f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{COD_UF}/municipios")}

malha = get(f"https://servicodados.ibge.gov.br/api/v3/malhas/estados/{COD_UF}"
            "?formato=application/vnd.geo+json&intrarregiao=municipio&qualidade=minima")

# CNES PF: oftalmologistas distintos (CPF_PROF/CNS_PROF) e carga horária por município
oft = collections.defaultdict(lambda: {"prof": set(), "sus": set(), "horas": 0.0, "regsaude": None})
for r in DBF(PF_DBF, encoding="latin-1"):
    mun = r["CODUFMUN"]
    if r["CBO"] != "225265":
        continue
    o = oft[mun]
    pid = r.get("CNS_PROF") or r.get("CPF_PROF")
    o["prof"].add(pid)
    if str(r.get("PROF_SUS")) == "1":
        o["sus"].add(pid)
    o["horas"] += sum(float(r.get(k) or 0) for k in ("HORAOUTR", "HORAHOSP", "HORA_AMB"))

municipios = []
for cod7, nome in nomes.items():
    c6 = cod7[:6]
    o = oft.get(c6)
    municipios.append({
        "cod": cod7, "nome": nome, "pop": pop[cod7], "pop20": pop20[cod7], "pop60": pop60[cod7],
        "regiao": imediata.get(cod7),
        "oftalmo": len(o["prof"]) if o else 0,
        "oftalmo_sus": len(o["sus"]) if o else 0,
        "fte": round(o["horas"] / 40, 1) if o else 0.0,
    })

# centroide simples (média dos vértices do maior anel) para desenhar e medir distância
for f in malha["features"]:
    cod = f["properties"]["codarea"]
    geom = f["geometry"]
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    # centroide de área do maior polígono (fórmula do shoelace)
    def area_centro(a):
        A = cx = cy = 0.0
        for (x0, y0), (x1, y1) in zip(a, a[1:] + a[:1]):
            c = x0 * y1 - x1 * y0
            A += c; cx += (x0 + x1) * c; cy += (y0 + y1) * c
        return A / 2, cx / (3 * A), cy / (3 * A)
    _, cx, cy = max((area_centro(p[0]) for p in polys), key=lambda t: abs(t[0]))
    for m in municipios:
        if m["cod"] == cod:
            m["lon"], m["lat"] = round(cx, 4), round(cy, 4)

profs_total = set().union(*(o["prof"] for o in oft.values())) if oft else set()
json.dump({
    "uf": UF, "competencia_cnes": COMP, "censo": 2022,
    "oftalmologistas_distintos_uf": len(profs_total),
    "municipios": sorted(municipios, key=lambda m: -m["pop"]),
    "malha": malha,
}, open(SAIDA, "w"), ensure_ascii=False, separators=(",", ":"))
print(SAIDA, len(municipios), "municípios,", len(profs_total), "oftalmologistas distintos")
