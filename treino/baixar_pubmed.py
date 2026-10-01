"""Baixa so as imagens candidatas do PubMedVision sem baixar os 57 GB de zips: le o diretorio central de cada
images_N.zip por HTTP Range (alguns MB por zip), monta o indice nome -> zip, e depois puxa cada entrada pelo
intervalo de bytes dela. Saida: dados/raw/pubmed/images/<nome>.jpg e dados/raw/pubmed/legendas.jsonl.
Uso: .venv/bin/python treino/baixar_pubmed.py [--indice-so] [--max N]
"""
import argparse, io, json, time, urllib.request, zipfile
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]; OUT = BASE / "dados/raw/pubmed"; IMG = OUT / "images"; IMG.mkdir(parents=True, exist_ok=True)
REPO = "https://huggingface.co/datasets/FreedomIntelligence/PubMedVision/resolve/main"
PARTS = [f"images_{i}.zip" for i in range(20)]

class HttpFile(io.RawIOBase):
    """arquivo remoto com seek/read por Range; o zipfile so pede o que precisa"""
    def __init__(self, url):
        self.url = url; self.pos = 0; self.size = self._size(); self.cache = {}
    def _size(self):
        for t in range(5):
            try:
                req = urllib.request.Request(self.url, method="HEAD")
                with urllib.request.urlopen(req, timeout=60) as r: return int(r.headers["Content-Length"])
            except Exception: time.sleep(3 + 3 * t)
        raise RuntimeError("HEAD falhou " + self.url)
    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]; return self.pos
    def tell(self): return self.pos
    def readable(self): return True
    def seekable(self): return True
    def read(self, n=-1):
        if n is None or n < 0: n = self.size - self.pos
        if n == 0: return b""
        end = min(self.size, self.pos + n) - 1
        for t in range(6):
            try:
                req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
                with urllib.request.urlopen(req, timeout=120) as r: data = r.read()
                self.pos += len(data); return data
            except Exception as e:
                time.sleep(4 + 4 * t)
        raise RuntimeError("Range falhou")

def indice():
    f = OUT / "indice_zip.json"
    if f.exists(): return json.load(open(f))
    idx = {}
    for p in PARTS:
        t0 = time.time(); hf = HttpFile(f"{REPO}/{p}")
        with zipfile.ZipFile(hf) as zf:
            for zi in zf.infolist():
                if not zi.is_dir(): idx[Path(zi.filename).name] = [p, zi.header_offset, zi.compress_size, zi.file_size, zi.compress_type]
        print(f"  {p}: {len(idx)} nomes acumulados ({time.time()-t0:.0f}s, {hf.size/1e9:.2f} GB)", flush=True)
        json.dump(idx, open(f, "w"))
    return idx

def baixar(idx, nome):
    part, off, csize, fsize, method = idx[nome]
    hf = HttpFile(f"{REPO}/{part}")
    hf.seek(off); head = hf.read(30)                      # cabecalho local: nome e extra tem tamanho variavel
    n, e = int.from_bytes(head[26:28], "little"), int.from_bytes(head[28:30], "little")
    hf.seek(off + 30 + n + e); data = hf.read(csize)
    if method == zipfile.ZIP_DEFLATED:
        import zlib; data = zlib.decompress(data, -15)
    return data

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--indice-so", action="store_true"); ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8); a = ap.parse_args()
    idx = indice(); print("indice:", len(idx), "imagens")
    if a.indice_so: return
    cands = [json.loads(l) for l in (OUT / "candidatos.jsonl").open()]
    fila = [(c, Path(rel).name) for c in cands for rel in c["images"] if Path(rel).name in idx]
    if a.max: fila = fila[:a.max]
    pend = [(c, n) for c, n in fila if not (IMG / n).exists()]
    print("candidatas:", len(fila), "| a baixar:", len(pend), flush=True)
    # um HttpFile por zip (HEAD uma vez so) e varios trabalhadores: cada imagem sao 2 pedidos Range pequenos
    from concurrent.futures import ThreadPoolExecutor
    import threading
    lock = threading.Lock(); hfs = {}
    def hf_de(part):
        with lock:
            if part not in hfs: hfs[part] = HttpFile(f"{REPO}/{part}")
            return hfs[part]
    def baixar1(nome):
        part, off, csize, fsize, method = idx[nome]
        hf = hf_de(part)
        for t in range(4):
            try:
                head = _range(hf.url, off, off + 29)
                n, e = int.from_bytes(head[26:28], "little"), int.from_bytes(head[28:30], "little")
                data = _range(hf.url, off + 30 + n + e, off + 30 + n + e + csize - 1)
                if method == zipfile.ZIP_DEFLATED:
                    import zlib; data = zlib.decompress(data, -15)
                (IMG / nome).write_bytes(data); return True
            except Exception as ex:
                time.sleep(3 + 3 * t); err = ex
        print("  falhou", nome, err, flush=True); return False
    feitas = 0; t0 = time.time()
    with ThreadPoolExecutor(a.workers) as ex:
        for ok in ex.map(lambda cn: baixar1(cn[1]), pend):
            feitas += 1
            if feitas % 50 == 0: print(f"  {feitas}/{len(pend)} ({time.time()-t0:.0f}s)", flush=True)
    # legendas: reescreve do zero so com o que existe em disco (sem duplicar em reexecucao)
    with (OUT / "legendas.jsonl").open("w") as legendas:
        n = 0
        for c, nome in fila:
            if (IMG / nome).exists():
                legendas.write(json.dumps({"image": nome, "id": c["id"], "rotulos": c["rotulos"], "termos": c["termos"], "caption": c["caption"]}, ensure_ascii=False) + "\n"); n += 1
    print("baixadas (em disco):", n)

def _range(url, a, b):
    """um pedido Range sem estado (seguro entre threads)"""
    req = urllib.request.Request(url, headers={"Range": f"bytes={a}-{b}"})
    with urllib.request.urlopen(req, timeout=120) as r: return r.read()

if __name__ == "__main__":
    main()
