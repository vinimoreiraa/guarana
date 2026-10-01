"""Embrulha uma FOTO REAL de olho na geometria (globo r=12 mm + cornea + pele com a fenda recortada pela mascara da propria foto)
e refotografa em varios angulos, lentes, luzes e flashes. O sinal e o da foto (rotulo herdado); a geometria da paralaxe,
brilho de cornea e sombra novos. Uso:
  Blender -b -P sintese/embrulhar.py -- --foto x.jpg --mascara x_mask.png --iris cx,cy,r --n 8 --out dir [--rotulos "pterigio|hiperemia"] [--size 512]
Entrada: iris (px) e mascara binaria da fenda (branco = esclera+iris). Escala: 2r px = 12 mm (diametro da cornea).
Saida: dir/<stem>_vNN.jpg + labels.csv (mesmas colunas do treino, source=embrulho, domain=wrapped).
"""
import bpy, bmesh, sys, os, math, random, csv, json
from mathutils import Vector, Matrix
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import olho as O
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d): return type(d)(argv[argv.index(k) + 1]) if k in argv else d
FOTO = arg("--foto", ""); MASC = arg("--mascara", ""); IRIS = [float(v) for v in arg("--iris", "0,0,0").split(",")]; N = arg("--n", 6); OUT = arg("--out", "sintese/render/embrulho")
ROT = [r for r in arg("--rotulos", "").split("|") if r]; TOPO = "--topo" in argv; SIZE = arg("--size", 512); SEED = arg("--seed", 0); SAMPLES = arg("--samples", 24)
MM = 0.001; os.makedirs(OUT, exist_ok=True)

def pele_z(x, y):
    r = math.hypot(x, y); Rs = O.R_GLOBO + 1.2 * MM; r0 = 9.0 * MM
    if r <= r0: return math.sqrt(Rs * Rs - r * r) - 0.5 * MM
    z0 = math.sqrt(Rs * Rs - r0 * r0) - 0.5 * MM; dr = (r - r0) / MM
    return max(z0 - (0.30 * dr - 0.002 * dr * dr) * MM, -4 * MM) if dr < 60 else -4 * MM

def contorno_fenda(mask, cx, cy, s_px_mm):
    """contorno da mascara (branco) como poligono em mm centrado na iris; usa varredura radial (72 raios) a partir do centro da iris"""
    h, w = mask.shape; pts = []
    for k in range(180):
        ang = 2 * math.pi * k / 180; dx, dy = math.cos(ang), math.sin(ang); rr = 0; last = 0
        for t in range(0, int(max(w, h))):
            x, y = int(round(cx + dx * t)), int(round(cy + dy * t))
            if x < 0 or y < 0 or x >= w or y >= h: break
            if mask[y, x]: last = t
            elif t - last > 6: break
        pts.append(((cx + dx * last - cx) * s_px_mm, -(cy + dy * last - cy) * s_px_mm))   # y da imagem para cima = -y
    return pts

def dentro_poligono(x, y, poly):
    n = len(poly); inside = False; j = n - 1
    for i in range(n):
        xi, yi = poly[i]; xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi): inside = not inside
        j = i
    return inside

def mat_foto(nome, img, s_px_mm, cx, cy, W, H, gloss=0.0, sss=0.0):
    """cor = foto projetada ao longo de Z: uv = ((x_mm/s + cx)/W, 1 - (-y_mm/s + cy)/H)"""
    m, nt = O.new_mat(nome); out = O.node(nt, "ShaderNodeOutputMaterial"); b = O.node(nt, "ShaderNodeBsdfPrincipled")
    tc = O.node(nt, "ShaderNodeTexCoord"); sep = O.node(nt, "ShaderNodeSeparateXYZ"); O.link(nt, tc, "Object", sep, "Vector")
    u = O.math_(nt, "DIVIDE", O.math_(nt, "ADD", O.math_(nt, "DIVIDE", O.math_(nt, "MULTIPLY", sep.outputs[0], vb=1000.0), vb=s_px_mm), vb=cx), vb=W)
    v = O.math_(nt, "SUBTRACT", None, O.math_(nt, "DIVIDE", O.math_(nt, "ADD", O.math_(nt, "DIVIDE", O.math_(nt, "MULTIPLY", sep.outputs[1], vb=-1000.0), vb=s_px_mm), vb=cy), vb=H), va=1.0)
    comb = O.node(nt, "ShaderNodeCombineXYZ"); nt.links.new(u, comb.inputs[0]); nt.links.new(v, comb.inputs[1])
    tex = O.node(nt, "ShaderNodeTexImage"); tex.image = img; tex.extension = "EXTEND"; O.link(nt, comb, 0, tex, "Vector")
    # dentro da foto (u,v em [0.03,0.97] com borda suave) usa a foto; fora, a cor media da borda da foto
    def dentro(t):
        return O.math_(nt, "MULTIPLY", O.clamp01(nt, O.math_(nt, "DIVIDE", O.math_(nt, "SUBTRACT", t, vb=0.02), vb=0.18)), O.clamp01(nt, O.math_(nt, "DIVIDE", O.math_(nt, "SUBTRACT", None, t, va=0.98), vb=0.18)))
    fac = O.math_(nt, "MULTIPLY", dentro(u), dentro(v))
    px = np.array(img.pixels[:], np.float32).reshape(img.size[1], img.size[0], 4); borda = np.concatenate([px[:8].reshape(-1, 4), px[-8:].reshape(-1, 4), px[:, :8].reshape(-1, 4), px[:, -8:].reshape(-1, 4)])[:, :3].mean(0)
    mixc = O.node(nt, "ShaderNodeMix", data_type="RGBA"); mixc.inputs[6].default_value = (*borda, 1); O.link(nt, tex, "Color", mixc, 7); nt.links.new(fac, mixc.inputs["Factor"]); O.link(nt, mixc, 2, b, "Base Color")
    O.setin(b, "Roughness", 0.7 if gloss == 0 else 0.25); O.setin(b, "Specular IOR Level", 0.12)
    if gloss: O.setin(b, "Coat Weight", gloss); O.setin(b, "Coat Roughness", 0.05)
    if sss: O.setin(b, "Subsurface Weight", sss); O.setin(b, "Subsurface Radius", (1 * MM, 0.5 * MM, 0.3 * MM))
    O.link(nt, b, "BSDF", out, "Surface"); return m

def build(rng, img, mask, cx, cy, r_px):
    s = 6.0 / r_px   # mm por px (raio da cornea = 6 mm)
    P = O.sample(rng); P["exposicao"] = rng.uniform(-0.9, -0.2); sc = O.reset(P); H, W = mask.shape
    poly = contorno_fenda(mask, cx, cy, s)
    if max(abs(q[0]) for q in poly) < 2.0 or max(abs(q[1]) for q in poly) < 1.0: raise SystemExit("fenda degenerada: centro da iris fora da mascara")
    # pele: grade com o buraco da fenda pela mascara real (em mm), altura pelo perfil de O.skin_z com uma fenda "falsa" larga (so para o perfil)
    Pf = dict(P); Pf["fenda_w"] = 26 * MM; Pf["fenda_h_sup"] = 5 * MM; Pf["fenda_h_inf"] = 4.5 * MM; Pf["fenda_cx"] = 0; Pf["fenda_cy"] = 0; Pf["prega_mm"] = 1.5
    bm = bmesh.new(); n = 240; L = max(60 * MM, min(W, H) * s * MM / 2 * 1.2); grid = {}   # s e mm/px: largura da foto em metros = W*s*MM
    for i in range(n + 1):
        for j in range(n + 1):
            x = -L + 2 * L * i / n; y = -L + 2 * L * j / n
            if dentro_poligono(x / MM, y / MM, poly): continue
            grid[(i, j)] = bm.verts.new((x, y, pele_z(x, y)))
    for (i, j) in list(grid):
        if (i + 1, j) in grid and (i + 1, j + 1) in grid and (i, j + 1) in grid:
            try: bm.faces.new((grid[(i, j)], grid[(i + 1, j)], grid[(i + 1, j + 1)], grid[(i, j + 1)]))
            except ValueError: pass
    xs_ = [q[0] for q in poly]; ys_ = [q[1] for q in poly]; print(f"DEBUG poligono mm: x {min(xs_):.1f}..{max(xs_):.1f} y {min(ys_):.1f}..{max(ys_):.1f} | vertices pele {len(bm.verts)} faces {len(bm.faces)} | s={s:.4f} mm/px W={W} H={H} L={L*1000:.1f}mm", flush=True)
    # vertices de borda do buraco: projeta no ponto mais proximo do poligono (elimina a escada da grade)
    P_ = [(q[0] * MM, q[1] * MM) for q in poly]
    for (i, j), v in list(grid.items()):
        if all(((i + di, j + dj) in grid) for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1))): continue
        x, y = v.co.x, v.co.y
        if math.hypot(x, y) > 14 * MM: continue
        best = None
        for a_, b_ in zip(P_, P_[1:] + P_[:1]):
            ax, ay = a_; bx, by = b_; vx, vy = bx - ax, by - ay; L2 = vx * vx + vy * vy
            t = 0 if L2 == 0 else max(0.0, min(1.0, ((x - ax) * vx + (y - ay) * vy) / L2)); px_, py_ = ax + t * vx, ay + t * vy; d2 = (x - px_) ** 2 + (y - py_) ** 2
            if best is None or d2 < best[0]: best = (d2, px_, py_)
        if best and best[0] < (1.2 * MM) ** 2: v.co = (best[1], best[2], pele_z(best[1], best[2]))
    pele = O.mesh_obj("pele", bm); m = pele.modifiers.new("sol", "SOLIDIFY"); m.thickness = -0.6 * MM; m.offset = 1; sb = pele.modifiers.new("sub", "SUBSURF"); sb.levels = 1; sb.render_levels = 1
    pele.data.materials.append(mat_foto("pele_foto", img, s, cx, cy, W, H, sss=0.15))
    # globo (esclera + iris projetados) + cornea transparente/brilhante por cima
    globo = O.esfera("globo", O.R_GLOBO, (0, 0, 0)); globo.data.materials.append(mat_foto("globo_foto", img, s, cx, cy, W, H, gloss=0.8, sss=0.2))
    cor = O.esfera("cornea", O.R_COR, O.C_COR, corte_z=(-1, O.C_COR.z + math.sqrt(O.R_COR ** 2 - O.R_ABERTURA ** 2) - 1.4 * MM)); P2 = dict(P); P2["opacidade_corneana"] = 0; mc = O.mat_cornea(P2)
    for n in mc.node_tree.nodes:
        if n.type == "BSDF_GLOSSY": n.inputs["Roughness"].default_value = 0.12
        if n.type == "FRESNEL": n.inputs["IOR"].default_value = 1.15
    cor.data.materials.append(mc)
    # fornice atras
    forn = O.esfera("fornice", 13.2 * MM, Vector((0, 0, -1.0 * MM)), seg=64, ring=40, corte_z=(1, 4.0 * MM)); forn.data.materials.append(O.mat_plain("fornice_m", (0.78, 0.45, 0.42), 0.4, 0.3))
    # luz: sobretudo uniforme (a foto ja tem sombra), com um pouco de HDRI e flash opcional
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True; wnt = w.node_tree; bg = wnt.nodes["Background"]; bg.inputs[1].default_value = rng.uniform(0.6, 1.1)
    cor = (1, 1, 1, 1)
    if O.HDRIS and rng.random() < 0.7:
        env = wnt.nodes.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(rng.choice(O.HDRIS)); mp = wnt.nodes.new("ShaderNodeMapping"); tc = wnt.nodes.new("ShaderNodeTexCoord")
        mp.inputs["Rotation"].default_value = (0, 0, rng.uniform(0, 6.28)); wnt.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); wnt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
        mix = wnt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.inputs[0].default_value = 0.6; mix.inputs[6].default_value = cor; wnt.links.new(env.outputs["Color"], mix.inputs[7]); src_col = mix.outputs[2]
    else:
        rgb = wnt.nodes.new("ShaderNodeRGB"); rgb.outputs[0].default_value = cor; src_col = rgb.outputs[0]
    # raios de brilho (reflexo na cornea) veem preto: o unico reflexo e o do flash/luz pontual, como na foto original
    lp = wnt.nodes.new("ShaderNodeLightPath"); mixg = wnt.nodes.new("ShaderNodeMix"); mixg.data_type = "RGBA"; mixg.inputs[7].default_value = (0, 0, 0, 1)
    wnt.links.new(src_col, mixg.inputs[6]); wnt.links.new(lp.outputs["Is Glossy Ray"], mixg.inputs[0]); wnt.links.new(mixg.outputs[2], bg.inputs["Color"])
    # camera: angulo ate 28 graus, lente/distancia de celular (equivalente full-frame), foco profundo
    ang_x, ang_y = rng.uniform(-22, 22), rng.uniform(-28, 28); dist = rng.uniform(0.045, 0.09); fw = (max(q[0] for q in poly) - min(q[0] for q in poly)) * MM; quadro = min(W * s * MM * 0.98, fw / rng.uniform(0.45, 0.8)); lente = max(25.0, min(140.0, 36 * dist / quadro))
    loc = Vector((dist * math.sin(math.radians(ang_y)), dist * math.sin(math.radians(ang_x)), dist * math.cos(math.radians(max(abs(ang_x), abs(ang_y))))))
    bpy.ops.object.camera_add(location=loc); cam = bpy.context.active_object; sc.camera = cam; cam.data.lens = lente; cam.data.sensor_width = 36; cam.data.clip_start = 0.003; cam.data.dof.use_dof = False
    if TOPO: cam.data.type = "ORTHO"; cam.data.ortho_scale = 0.04; loc = Vector((0, 0, 0.15)); cam.location = loc; ang_x = ang_y = 0
    tgt = Vector((rng.uniform(-3, 3) * MM, rng.uniform(-2, 2) * MM, 10 * MM)) if not TOPO else Vector((0, 0, 0)); fwd = (tgt - loc).normalized(); right = fwd.cross(Vector((0, 1, 0))).normalized(); upv = right.cross(fwd).normalized()
    cam.matrix_world = Matrix.Translation(loc) @ Matrix((right, upv, -fwd)).transposed().to_4x4() @ Matrix.Rotation(math.radians(rng.uniform(-15, 15)), 4, "Z")
    if rng.random() < 0.6:
        bpy.ops.object.light_add(type="POINT", location=loc + right * 0.008 + upv * rng.uniform(-0.01, 0.02)); fl = bpy.context.active_object; fl.data.energy = rng.uniform(0.8, 3.0); fl.data.shadow_soft_size = 0.004
    return dict(ang_x=round(ang_x, 1), ang_y=round(ang_y, 1), dist_mm=round(dist * 1000), lente=round(lente))

def main():
    assert FOTO and MASC and IRIS[2] > 0, "faltou --foto/--mascara/--iris"
    rng = random.Random(SEED)
    mi = bpy.data.images.load(MASC); W0, H0 = mi.size; px = np.array(mi.pixels[:], np.float32).reshape(H0, W0, 4)[::-1]   # Blender guarda de baixo para cima
    m0 = px[:, :, 0]
    # suaviza a mascara (media movel 9x9, 2 passagens) antes do limiar: tira o serrilhado do segmentador
    for _ in range(2):
        k = 4; acc = np.zeros_like(m0); cnt = np.zeros_like(m0)
        for dy in range(-k, k + 1):
            for dx in range(-k, k + 1):
                acc[max(0, dy):H0 + min(0, dy), max(0, dx):W0 + min(0, dx)] += m0[max(0, -dy):H0 - max(0, dy), max(0, -dx):W0 - max(0, dx)]; cnt[max(0, dy):H0 + min(0, dy), max(0, dx):W0 + min(0, dx)] += 1
        m0 = acc / np.maximum(cnt, 1)
    mask = m0 > 0.5
    stem = os.path.splitext(os.path.basename(FOTO))[0]; rows = []
    for k in range(N):
        rng_k = random.Random(SEED * 1000 + k)
        info = build(rng_k, LazyImg(FOTO), mask, IRIS[0], IRIS[1], IRIS[2])   # a foto e carregada depois do reset da cena
        path = os.path.abspath(os.path.join(OUT, f"{stem}_v{k:02d}.jpg")); bpy.context.scene.render.filepath = path; bpy.ops.render.render(write_still=True)
        rows.append({"file": os.path.basename(path), "subject_id": "emb_" + stem, "source": "embrulho", "domain": "wrapped", **{l: int(l in ROT) for l in O.LABELS}, "sinal": "|".join(ROT) or "normal", "params": json.dumps(info)})
        print("render", path, info, flush=True)
    csvp = os.path.join(OUT, "labels.csv"); new = not os.path.exists(csvp)
    with open(csvp, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "subject_id", "source", "domain", *O.LABELS, "sinal", "params"])
        if new: w.writeheader()
        w.writerows(rows)

class LazyImg:
    """bpy.data.images e limpo no reset; carrega a imagem na hora de criar o material"""
    def __init__(self, path): self.path = path
    def __getattr__(self, k): raise AttributeError(k)
def _load(img):
    return bpy.data.images.load(img.path) if isinstance(img, LazyImg) else img
_orig = mat_foto
def mat_foto(nome, img, *a, **kw): return _orig(nome, _load(img), *a, **kw)
main()
