"""Embute dados_{UF}.json no painel: python montar_painel.py AM"""
import pathlib, sys
uf = sys.argv[1] if len(sys.argv) > 1 else "AM"
aqui = pathlib.Path(__file__).parent
html = (aqui / "painel_template.html").read_text().replace("/*DADOS*/null", (aqui / f"dados_{uf}.json").read_text())
(aqui / f"painel_{uf}.html").write_text(html)
print(aqui / f"painel_{uf}.html", len(html) // 1024, "KB")
