"""Baixa os datasets abertos para dados/raw/<fonte>/ com retomada (curl -C -). Uso:
  python treino/baixar_datasets.py            # todos
  python treino/baixar_datasets.py slid hf_jaundice   # so alguns
"""
import json, subprocess, sys, urllib.request, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "dados" / "raw"
UA = "Mozilla/5.0 (ocular-ia downloader)"

def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def curl(url, dest):
    dest = Path(dest); dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.with_suffix(dest.suffix + ".ok").exists():
        return "skip"
    cmd = ["curl", "-L", "-sS", "--retry", "5", "--retry-delay", "3", "-C", "-", "-A", UA, "-o", str(dest), url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0:
        dest.with_suffix(dest.suffix + ".ok").touch(); return "ok"
    return f"erro {r.returncode}: {r.stderr.strip()[:120]}"

def mendeley_root_files(ds, version=1):
    return get_json(f"https://data.mendeley.com/public-api/datasets/{ds}/files?folder_id=root&version={version}")

def mendeley_folder_files(ds, folder_id, version=1):
    # a API devolve no maximo 1000 por chamada; pagina com $start
    start = 0
    while True:
        page = get_json(f"https://data.mendeley.com/public-api/datasets/{ds}/files?folder_id={folder_id}&version={version}&%24start={start}&%24limit=1000")
        yield from page
        if len(page) < 1000: break
        start += 1000

def mendeley_walk(ds, dest_root, version=1, keep_folder=lambda name: True, keep_file=lambda name: True):
    folders = get_json(f"https://data.mendeley.com/public-api/datasets/{ds}/folders/{version}")
    for fo in folders:
        if not keep_folder(fo["name"]): continue
        for f in mendeley_folder_files(ds, fo["id"], version):
            if keep_file(f["filename"]):
                yield f["content_details"]["download_url"], dest_root / fo["name"] / f["filename"]

SOURCES = {}

def src(name):
    def deco(fn): SOURCES[name] = fn; return fn
    return deco

@src("periorbital")
def _():
    yield "https://zenodo.org/api/records/13916845/files/periorbital_dataset.zip/content", ROOT/"periorbital"/"periorbital_dataset.zip"

@src("slid")
def _():
    yield "https://raw.githubusercontent.com/xumingyu-hub/SLID/main/Annotations.csv", ROOT/"slid"/"Annotations.csv"
    yield "https://media.githubusercontent.com/media/xumingyu-hub/SLID/main/Original_Slit-lamp_Images.zip", ROOT/"slid"/"Original_Slit-lamp_Images.zip"

@src("cp_anemic")
def _():
    for f in mendeley_root_files("m53vz6b7fx"):
        yield f["content_details"]["download_url"], ROOT/"cp_anemic"/f["filename"]

@src("faridpur")
def _():
    for f in mendeley_root_files("s9bfhswzjb"):
        if f["filename"].startswith("Original"):
            yield f["content_details"]["download_url"], ROOT/"faridpur"/f["filename"]

@src("hf_jaundice")
def _():
    repo = "Bleachcarte/Jaundice_Dataset"
    for s in get_json(f"https://huggingface.co/api/datasets/{repo}")["siblings"]:
        p = s["rfilename"]
        if p.startswith("."): continue
        yield f"https://huggingface.co/datasets/{repo}/resolve/main/{urllib.parse.quote(p)}", ROOT/"hf_jaundice"/p

import re
AUG = re.compile(r" \(\d+\)\.[A-Za-z]+$")   # "Anemic-001 (10).png" = copia aumentada

@src("conj_seg")
def _():
    yield from mendeley_walk("yxwjgcndg2", ROOT/"conj_seg", keep_folder=lambda n: n == "Images")

@src("conj_seg_masks")
def _():
    yield from mendeley_walk("yxwjgcndg2", ROOT/"conj_seg", keep_folder=lambda n: n == "Masks Annotator 1")

@src("eye_diseases")
def _():
    yield from mendeley_walk("n9zp473wfw", ROOT/"eye_diseases")

@src("ghana_ida")
def _():
    yield from mendeley_walk("nt7r8hv2pz", ROOT/"ghana_ida", keep_file=lambda n: not AUG.search(n))

from concurrent.futures import ThreadPoolExecutor

def main():
    names = sys.argv[1:] or list(SOURCES)
    for n in names:
        print(f"== {n}", flush=True)
        try:
            items = list(SOURCES[n]())
        except Exception as e:
            print(f"   listagem falhou: {e}", flush=True); continue
        counts = {}
        print(f"   {len(items)} arquivos", flush=True)
        def work(it):
            url, dest = it
            return dest, curl(url, dest)
        with ThreadPoolExecutor(max_workers=8 if len(items) > 5 else 1) as ex:
            for i, (dest, st) in enumerate(ex.map(work, items), 1):
                counts[st.split()[0]] = counts.get(st.split()[0], 0) + 1
                if st.startswith("erro") or len(items) <= 5:
                    print(f"   [{i}/{len(items)}] {Path(dest).name}: {st}", flush=True)
                elif i % 500 == 0:
                    print(f"   ... {i}/{len(items)}", flush=True)
        print(f"   {n}: {counts}", flush=True)
    print("FIM", flush=True)

if __name__ == "__main__":
    main()
