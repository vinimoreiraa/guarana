#!/bin/bash
# Roda o Blender para cada trabalho de sintese/embrulho_jobs/jobs.json: N vistas por foto. Uso: bash sintese/embrulhar_lote.sh [N_VISTAS] [OUT]
cd "$(dirname "$0")/.."; N=${1:-6}; OUT=${2:-sintese/render/embrulho1}; mkdir -p "$OUT"
.venv/bin/python - "$N" "$OUT" <<'PY'
import json, subprocess, sys, os
n, out = sys.argv[1], sys.argv[2]; jobs = json.load(open("sintese/embrulho_jobs/jobs.json"))
for k, j in enumerate(jobs):
    if os.path.exists(os.path.join(out, f"{j['id']}_v00.jpg")): continue
    cmd = ["/Applications/Blender.app/Contents/MacOS/Blender", "-b", "-P", "sintese/embrulhar.py", "--", "--foto", j["foto"], "--mascara", j["mascara"], "--iris", ",".join(map(str, j["iris"])), "--n", n, "--out", out, "--rotulos", "|".join(j["rotulos"]), "--size", "512", "--samples", "20", "--seed", str(k)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = sum(1 for l in r.stdout.splitlines() if l.startswith("render")); print(f"{k+1}/{len(jobs)} {j['id']} {j['rotulos']} -> {ok} vistas", flush=True)
    if ok == 0: print(r.stdout[-800:], r.stderr[-400:])
PY
