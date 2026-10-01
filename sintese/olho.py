"""Olho externo sintetico e parametrico no Blender (headless). v2.
Uso: /Applications/Blender.app/Contents/MacOS/Blender -b -P sintese/olho.py -- --n 8 --out sintese/render --seed 0 [--size 512] [--samples 24] [--engine eevee|cycles] [--mostruario] [--topo] [--wide]
Gera <out>/<id>.jpg e acrescenta linhas em <out>/labels.csv (colunas do treino + parametros em JSON).
Escala: 1 unidade = 1 m. Globo r=12 mm com abertura de 6 mm para a cornea (calota r=7,8 mm), iris a 3,6 mm do apice, fenda ~26 x 9 mm.
"""
import bpy, bmesh, math, random, json, sys, csv, os, glob
from mathutils import Vector, Matrix
import numpy as np

LABELS = ["hiperemia","ictericia","pterigio","pinguecula","catarata_leucocoria","hemorragia_subconjuntival","lesao_pigmentada","opacidade_corneana",
          "tumor_superficie_ocular","ceratite","cisto_conjuntival","lente_intraocular","conjuntivite","uveite","alteracao_palpebral"]
MM = 0.001; R_GLOBO = 12 * MM; R_COR = 7.8 * MM; C_COR = Vector((0, 0, (12 - 7.8 + 1.1) * MM)); R_ABERTURA = 6.0 * MM
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d): return type(d)(argv[argv.index(k) + 1]) if k in argv else d
N = arg("--n", 4); OUT = arg("--out", "sintese/render"); SEED = arg("--seed", 0); SIZE = arg("--size", 512); SAMPLES = arg("--samples", 24)
ENGINE = arg("--engine", "eevee"); FORCAR = arg("--forcar", ""); MOSTRUARIO = "--mostruario" in argv; TOPO = "--topo" in argv; WIDE = "--wide" in argv; NOSKIN = "--noskin" in argv
HERE = os.path.dirname(os.path.abspath(__file__)); os.makedirs(OUT, exist_ok=True)
def _skin_sets():
    out = []
    d = os.path.join(HERE, "assets", "pele")
    for c in sorted(glob.glob(os.path.join(d, "texturecan_*", "1k", "*_color_*.jpg"))):
        n = glob.glob(os.path.join(os.path.dirname(c), "*_normal_opengl_*.png")); out.append((c, n[0] if n else None))
    for c in sorted(glob.glob(os.path.join(d, "cc0textures_sharetextures", "*", "*diffuse*.*")) + glob.glob(os.path.join(d, "cc0textures_sharetextures", "*", "*Diffuse*.*"))):
        n = glob.glob(os.path.join(os.path.dirname(c), "*ormal*.*")); out.append((c, n[0] if n else None))
    return out
SKIN_TEX = _skin_sets()
HDRIS = [h for h in sorted(glob.glob(os.path.join(HERE, "assets", "hdri", "*.*"))) if h.lower().endswith((".hdr", ".exr"))]
IRIS_TEX = [f for f in sorted(glob.glob(os.path.join(HERE, "assets", "iris_texturas", "blender_institute_eyes", "eye_iris_*-color.*"))) if not any(k in f.lower() for k in ("insect", "dragon", "chicken", "hyena"))]

# ---------- nos ----------
def new_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    return m, nt
def node(nt, kind, **kw):
    n = nt.nodes.new(kind)
    for k, v in kw.items(): setattr(n, k, v)
    return n
def link(nt, a, ao, b, bi): nt.links.new(a.outputs[ao], b.inputs[bi])
def setin(n, name, v): n.inputs[name].default_value = v
def math_(nt, op, a=None, b=None, va=None, vb=None):
    m = nt.nodes.new("ShaderNodeMath"); m.operation = op
    if a is not None: nt.links.new(a, m.inputs[0])
    if va is not None: m.inputs[0].default_value = va
    if b is not None: nt.links.new(b, m.inputs[1])
    if vb is not None: m.inputs[1].default_value = vb
    return m.outputs[0]
def clamp01(nt, x): return math_(nt, "MAXIMUM", math_(nt, "MINIMUM", x, vb=1.0), vb=0.0)
def obj_mm(nt):
    """coordenadas de objeto em mm (x,y,z separados)"""
    tc = node(nt, "ShaderNodeTexCoord"); sc = node(nt, "ShaderNodeVectorMath", operation="SCALE"); link(nt, tc, "Object", sc, 0); setin(sc, "Scale", 1000.0)
    sep = node(nt, "ShaderNodeSeparateXYZ"); link(nt, sc, 0, sep, "Vector"); return sc, sep
def calota_mask(nt, sep, centro_mm, raio_mm, suave_mm):
    """1 dentro de uma esfera (em mm) centrada em centro_mm, borda suave"""
    dx = math_(nt, "SUBTRACT", sep.outputs[0], vb=centro_mm[0]); dy = math_(nt, "SUBTRACT", sep.outputs[1], vb=centro_mm[1]); dz = math_(nt, "SUBTRACT", sep.outputs[2], vb=centro_mm[2])
    d = math_(nt, "SQRT", math_(nt, "ADD", math_(nt, "ADD", math_(nt, "MULTIPLY", dx, dx), math_(nt, "MULTIPLY", dy, dy)), math_(nt, "MULTIPLY", dz, dz)))
    return math_(nt, "SUBTRACT", None, clamp01(nt, math_(nt, "DIVIDE", math_(nt, "SUBTRACT", d, vb=raio_mm), vb=suave_mm)), va=1.0)
def mix_rgb(nt, prev, cor, fac_socket):
    mx = node(nt, "ShaderNodeMix", data_type="RGBA")
    if isinstance(prev, tuple): mx.inputs[6].default_value = (*prev, 1)
    else: nt.links.new(prev, mx.inputs[6])
    mx.inputs[7].default_value = (*cor, 1); nt.links.new(fac_socket, mx.inputs["Factor"]); return mx.outputs[2]

# ---------- cena ----------
def reset(P):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    if ENGINE == "eevee":
        sc.render.engine = "BLENDER_EEVEE"; sc.eevee.taa_render_samples = SAMPLES
        for attr, val in (("use_raytracing", True), ("use_shadows", True)):
            if hasattr(sc.eevee, attr): setattr(sc.eevee, attr, val)
    else:
        sc.render.engine = "CYCLES"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
        prefs = bpy.context.preferences.addons.get("cycles")
        if prefs:
            try:
                prefs.preferences.compute_device_type = "METAL"; prefs.preferences.get_devices()
                for d in prefs.preferences.devices: d.use = True
                sc.cycles.device = "GPU"
            except Exception: pass
    sc.render.resolution_x = SIZE; sc.render.resolution_y = SIZE; sc.render.image_settings.file_format = "JPEG"; sc.render.image_settings.quality = 90
    sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Base Contrast"; sc.view_settings.exposure = P["exposicao"]
    return sc

def mesh_obj(name, bm, smooth=True):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(o)
    if smooth:
        for p in me.polygons: p.use_smooth = True
    return o

def esfera(name, r, loc, seg=128, ring=80, corte_z=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=ring, radius=r, location=loc); o = bpy.context.active_object; o.name = name; bpy.ops.object.shade_smooth()
    if corte_z is not None:
        bm = bmesh.new(); bm.from_mesh(o.data); sinal, z0 = corte_z
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if sinal * (v.co.z - z0) > 0], context="VERTS"); bm.to_mesh(o.data); bm.free()
    return o

def raio_superficie(d):
    """raio (do centro do globo) da superficie externa na direcao unitaria d: globo, ou cornea onde ela bojuda"""
    r = R_GLOBO; dc = d.dot(C_COR); disc = dc * dc - C_COR.length_squared + R_COR * R_COR
    if disc > 0:
        t = dc + math.sqrt(disc)
        if d.z > 0 and d.x * d.x + d.y * d.y < (R_ABERTURA / R_GLOBO) ** 2 * 1.02: r = max(r, t)
    return r

def asa_pterigio(P):
    """asa carnosa: em coordenadas esfericas (theta do eixo optico, phi em volta), base larga no lado nasal, apice invadindo a cornea."""
    lado = P["pterigio_lado"]; phi0 = 0.0 if lado > 0 else math.pi
    th_limbo = math.asin(R_ABERTURA / R_GLOBO)                     # ~30 graus
    th_apice = th_limbo - P["pterigio_mm"] * MM / R_GLOBO * 1.0     # quanto entra na cornea (arco ~ mm)
    th_base = th_limbo + math.radians(28)
    n_t, n_p = 60, 40; bm = bmesh.new(); grid = {}
    for i in range(n_t + 1):
        th = th_base + (th_apice - th_base) * i / n_t; t = i / n_t   # 0 base .. 1 apice
        half = math.radians(36) * (1 - t) ** 1.1 + math.radians(2.5)
        for j in range(n_p + 1):
            ph = phi0 + (-half + 2 * half * j / n_p)
            d = Vector((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)))
            lift = (0.7 * MM) * (1 - (abs(j / n_p - 0.5) * 2) ** 2) * (0.5 + 0.5 * (1 - t)) + 0.08 * MM
            grid[(i, j)] = bm.verts.new(d * (raio_superficie(d) + lift))
    for i in range(n_t):
        for j in range(n_p):
            bm.faces.new((grid[(i, j)], grid[(i + 1, j)], grid[(i + 1, j + 1)], grid[(i, j + 1)]))
    o = mesh_obj("pterigio", bm)
    m, nt = new_mat("pterigio_m"); out = node(nt, "ShaderNodeOutputMaterial"); b = node(nt, "ShaderNodeBsdfPrincipled"); setin(b, "Roughness", 0.3); setin(b, "Coat Weight", 0.6)
    setin(b, "Subsurface Weight", 0.4); setin(b, "Subsurface Radius", (1 * MM, 0.4 * MM, 0.3 * MM))
    sc, sep = obj_mm(nt); vor = node(nt, "ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE"); setin(vor, "Scale", 1.8); link(nt, sc, 0, vor, "Vector")
    v = math_(nt, "LESS_THAN", vor.outputs["Distance"], vb=0.04)
    base = (0.74, 0.40, 0.36) if P["pterigio_mm"] < 2.5 else (0.70, 0.32, 0.30)
    col = mix_rgb(nt, base, (0.55, 0.08, 0.06), v)
    nt.links.new(col, b.inputs["Base Color"]); link(nt, b, "BSDF", out, "Surface"); o.data.materials.append(m); return o

def skin_z(x, y, P):
    """altura da pele em (x,y): envolve o globo perto da fenda, achata longe; crista da palpebra superior e bolsa inferior."""
    a = P["fenda_w"] / 2; b_up = P["fenda_h_sup"]; b_dn = P["fenda_h_inf"]; cx, cy = P["fenda_cx"], P["fenda_cy"]
    r = math.hypot(x, y); Rs = R_GLOBO + 1.2 * MM; r0 = 10.5 * MM
    if r <= r0: z = math.sqrt(Rs * Rs - r * r)
    else:
        z0 = math.sqrt(Rs * Rs - r0 * r0); dr = (r - r0) / MM   # em mm
        z = z0 - (0.55 * dr - 0.006 * dr * dr) * MM if dr < 45 else z0 - (0.55 * 45 - 0.006 * 45 * 45) * MM
        z = max(z, -6 * MM)
    dy = y - cy; dyy = dy - (b_up if dy > 0 else -b_dn); lat = max(0.0, 1 - (abs(x - cx) / (a + 7 * MM)) ** 2)
    if dy > 0: z += (P["prega_mm"] * MM) * math.exp(-((dyy - 3.5 * MM) / (3.2 * MM)) ** 2) * lat - 0.6 * MM * math.exp(-((dyy - 8.5 * MM) / (1.3 * MM)) ** 2) * lat
    else: z += 1.0 * MM * math.exp(-((dyy + 2.5 * MM) / (2.5 * MM)) ** 2) * lat
    return z - 0.5 * MM

def skin_lids(P):
    a = P["fenda_w"] / 2; b_up = P["fenda_h_sup"]; b_dn = P["fenda_h_inf"]; cx, cy = P["fenda_cx"], P["fenda_cy"]
    bm = bmesh.new(); n = 200; L = 70 * MM; grid = {}
    for i in range(n + 1):
        for j in range(n + 1):
            x = -L + 2 * L * i / n; y = -L + 2 * L * j / n; dy = y - cy; bb = b_up if dy > 0 else b_dn
            if ((x - cx) / a) ** 2 + (dy / bb) ** 2 < 1.0: continue
            grid[(i, j)] = bm.verts.new((x, y, skin_z(x, y, P)))
    for (i, j) in list(grid):
        if (i + 1, j) in grid and (i + 1, j + 1) in grid and (i, j + 1) in grid:
            try: bm.faces.new((grid[(i, j)], grid[(i + 1, j)], grid[(i + 1, j + 1)], grid[(i, j + 1)]))
            except ValueError: pass
    # vertices da borda do buraco: projeta na elipse exata (tira o serrilhado da grade)
    for (i, j), v in grid.items():
        if all(((i + di, j + dj) in grid) for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1))): continue
        x, y = v.co.x, v.co.y
        if math.hypot((x - cx) / a, (y - cy) / (b_up if y - cy > 0 else b_dn)) < 1.35:
            th = math.atan2((y - cy) / (b_up if y - cy > 0 else b_dn), (x - cx) / a); bb = b_up if math.sin(th) > 0 else b_dn
            nx, ny = cx + a * math.cos(th), cy + bb * math.sin(th); v.co = (nx, ny, skin_z(nx, ny, P))
    o = mesh_obj("pele", bm)
    m = o.modifiers.new("sol", "SOLIDIFY"); m.thickness = -0.6 * MM; m.offset = 1; m.material_offset_rim = 0; m.use_rim = True
    s = o.modifiers.new("sub", "SUBSURF"); s.levels = 1; s.render_levels = 2
    return o

def cilios(P):
    a = P["fenda_w"] / 2; cx, cy = P["fenda_cx"], P["fenda_cy"]; rng = random.Random(int(P["cam_mm"] * 1000))
    cu = bpy.data.curves.new("cilios", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.035 * MM; cu.bevel_resolution = 1; cu.fill_mode = "FULL"
    for sgn, bb, L, n in ((1, P["fenda_h_sup"], (5.5, 8.0), 26), (-1, P["fenda_h_inf"], (3.0, 4.5), 14)):
        for i in range(n):
            t = -0.9 + 1.8 * (i + rng.random() * 0.6) / n; x = cx + a * t; y = cy + sgn * bb * math.sqrt(max(1 - t * t, 0))
            p0 = Vector((x, y, skin_z(x, y, P) + 0.3 * MM)); ln = rng.uniform(*L) * MM
            d = Vector((rng.uniform(-0.25, 0.25) + 0.5 * t, sgn * rng.uniform(0.45, 0.8), 0.9)).normalized(); curl = Vector((0, sgn * 0.5, -0.6)) * ln * 0.3
            sp = cu.splines.new("BEZIER"); sp.bezier_points.add(2); pts = [p0, p0 + d * ln * 0.55, p0 + d * ln + curl]
            for k, bp in enumerate(sp.bezier_points): bp.co = pts[k]; bp.handle_left_type = bp.handle_right_type = "AUTO"
    o = bpy.data.objects.new("cilios", cu); bpy.context.collection.objects.link(o); o.data.materials.append(mat_plain("cilio", (0.03, 0.02, 0.015), 0.5)); return o

# ---------- materiais ----------
def mat_plain(name, rgb, rough=0.5, sss=0.0):
    m, nt = new_mat(name); out = node(nt, "ShaderNodeOutputMaterial"); b = node(nt, "ShaderNodeBsdfPrincipled"); setin(b, "Base Color", (*rgb, 1)); setin(b, "Roughness", rough)
    if sss: setin(b, "Subsurface Weight", sss); setin(b, "Subsurface Radius", (1 * MM, 0.5 * MM, 0.3 * MM))
    link(nt, b, "BSDF", out, "Surface"); return m

def mat_skin(P, tinta=None):
    m, nt = new_mat("pele"); out = node(nt, "ShaderNodeOutputMaterial"); b = node(nt, "ShaderNodeBsdfPrincipled")
    base = tinta or P["pele_cor"]; setin(b, "Roughness", 0.7); setin(b, "Specular IOR Level", 0.15)
    setin(b, "Subsurface Weight", 0.15); setin(b, "Subsurface Radius", (3 * MM, 1.5 * MM, 0.8 * MM)); setin(b, "Subsurface Scale", 1.0)
    sc, sep = obj_mm(nt)
    nz = node(nt, "ShaderNodeTexNoise"); setin(nz, "Scale", 2.5); setin(nz, "Detail", 4); link(nt, sc, 0, nz, "Vector"); bump = node(nt, "ShaderNodeBump"); setin(bump, "Strength", 0.08); setin(bump, "Distance", 0.0003)
    link(nt, nz, "Fac", bump, "Height"); link(nt, bump, "Normal", b, "Normal")
    nz2 = node(nt, "ShaderNodeTexNoise"); setin(nz2, "Scale", 1.2); setin(nz2, "Detail", 3); link(nt, sc, 0, nz2, "Vector")
    fac = math_(nt, "MULTIPLY", nz2.outputs["Fac"], vb=0.35)
    col = mix_rgb(nt, base, (base[0] * 0.75, base[1] * 0.62, base[2] * 0.6), fac)
    if SKIN_TEX:
        cor_p, nrm_p = SKIN_TEX[P["pele_tex_i"] % len(SKIN_TEX)]
        mp = node(nt, "ShaderNodeMapping"); mp.inputs["Location"].default_value = (P["pele_tex_u"], P["pele_tex_v"], 0); mp.inputs["Rotation"].default_value = (0, 0, P["pele_tex_rot"]); mp.inputs["Scale"].default_value = (1 / 55.0, 1 / 55.0, 1)
        link(nt, sc, 0, mp, "Vector")
        img = node(nt, "ShaderNodeTexImage"); img.image = bpy.data.images.load(cor_p); img.extension = "REPEAT"; link(nt, mp, 0, img, "Vector")
        bw = node(nt, "ShaderNodeRGBToBW"); link(nt, img, "Color", bw, "Color")
        gain = math_(nt, "MULTIPLY", math_(nt, "ADD", math_(nt, "MULTIPLY", bw.outputs[0], vb=0.6), vb=0.55), vb=1.0)   # ~0.55..1.15
        mulc = node(nt, "ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY"); setin(mulc, "Factor", 1.0); nt.links.new(col, mulc.inputs[6])
        comb = node(nt, "ShaderNodeCombineColor"); nt.links.new(gain, comb.inputs[0]); nt.links.new(gain, comb.inputs[1]); nt.links.new(gain, comb.inputs[2]); link(nt, comb, 0, mulc, 7)
        col = mulc.outputs[2]
        if nrm_p:
            nimg = node(nt, "ShaderNodeTexImage"); nimg.image = bpy.data.images.load(nrm_p); nimg.image.colorspace_settings.name = "Non-Color"; nimg.extension = "REPEAT"; link(nt, mp, 0, nimg, "Vector")
            nm = node(nt, "ShaderNodeNormalMap"); setin(nm, "Strength", 0.5); link(nt, nimg, "Color", nm, "Color"); link(nt, bump, "Normal", nm, "Normal") if False else None
            link(nt, nm, "Normal", b, "Normal")
    nt.links.new(col, b.inputs["Base Color"]); link(nt, b, "BSDF", out, "Surface"); return m

def mat_sclera(P):
    m, nt = new_mat("esclera"); out = node(nt, "ShaderNodeOutputMaterial"); b = node(nt, "ShaderNodeBsdfPrincipled")
    setin(b, "Roughness", 0.18); setin(b, "Subsurface Weight", 0.4); setin(b, "Subsurface Radius", (1.0 * MM, 0.5 * MM, 0.3 * MM)); setin(b, "Coat Weight", 1.0); setin(b, "Coat Roughness", 0.04)
    ict = P["ictericia"]; base = tuple(np.array([0.82, 0.80, 0.77]) * (1 - ict) + np.array([0.82, 0.66, 0.22]) * ict)
    sc, sep = obj_mm(nt)
    # vasos: voronoi (distancia a borda) em coordenadas distorcidas, duas escalas; densidade e largura crescem com hiperemia
    hip = P["hiperemia"]
    # vasos radiais (do fornice para o limbo), tortuosos: ruido em (phi*K, r*T) limiarizado; phi distorcido por ruido
    rxy0 = math_(nt, "SQRT", math_(nt, "ADD", math_(nt, "MULTIPLY", sep.outputs[0], sep.outputs[0]), math_(nt, "MULTIPLY", sep.outputs[1], sep.outputs[1])))
    phi = node(nt, "ShaderNodeMath", operation="ARCTAN2"); nt.links.new(sep.outputs[1], phi.inputs[0]); nt.links.new(sep.outputs[0], phi.inputs[1])
    nzt = node(nt, "ShaderNodeTexNoise"); setin(nzt, "Scale", 0.22); setin(nzt, "Detail", 2); link(nt, sc, 0, nzt, "Vector")
    phit = math_(nt, "ADD", phi.outputs[0], math_(nt, "MULTIPLY", math_(nt, "SUBTRACT", nzt.outputs["Fac"], vb=0.5), vb=0.9))
    vasos = None
    for K, T, larg, thr, seed in ((9.0, 0.22, 0.030 + 0.03 * hip, 0.50 - 0.35 * hip, 0.0), (22.0, 0.45, 0.018 + 0.02 * hip, 0.62 - 0.45 * hip, 7.0)):
        comb = node(nt, "ShaderNodeCombineXYZ"); nt.links.new(math_(nt, "MULTIPLY", phit, vb=K), comb.inputs[0]); nt.links.new(math_(nt, "MULTIPLY", rxy0, vb=T), comb.inputs[1]); comb.inputs[2].default_value = seed
        vor = node(nt, "ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE"); setin(vor, "Scale", 1.0); setin(vor, "Randomness", 1.0); link(nt, comb, 0, vor, "Vector")
        v = math_(nt, "LESS_THAN", vor.outputs["Distance"], vb=larg)
        nzv = node(nt, "ShaderNodeTexNoise"); setin(nzv, "Scale", 0.18); setin(nzv, "Detail", 2); link(nt, sc, 0, nzv, "Vector"); setin(nzv, "Scale", 0.18 + 0.02 * seed)
        vv = math_(nt, "MULTIPLY", v, math_(nt, "GREATER_THAN", nzv.outputs["Fac"], vb=thr)); vasos = vv if vasos is None else math_(nt, "MAXIMUM", vasos, vv)
    # envelope: mais vasos longe do limbo (r > 7 mm), sumindo sobre a cornea
    env = clamp01(nt, math_(nt, "DIVIDE", math_(nt, "SUBTRACT", rxy0, vb=6.4), vb=1.5)); vasos = math_(nt, "MULTIPLY", vasos, math_(nt, "ADD", env, vb=0.0))
    # tinta difusa (conjuntivite/hiperemia), mais forte longe do limbo; e "injecao ciliar" da uveite/ceratite: anel vermelho junto ao limbo
    rxy = math_(nt, "SQRT", math_(nt, "ADD", math_(nt, "MULTIPLY", sep.outputs[0], sep.outputs[0]), math_(nt, "MULTIPLY", sep.outputs[1], sep.outputs[1])))
    perif = clamp01(nt, math_(nt, "DIVIDE", math_(nt, "SUBTRACT", rxy, vb=6.5), vb=5.0))
    tint = math_(nt, "MULTIPLY", perif, vb=0.55 * hip + 0.6 * P["conjuntivite"])
    ciliar = math_(nt, "MULTIPLY", math_(nt, "SUBTRACT", None, clamp01(nt, math_(nt, "DIVIDE", math_(nt, "SUBTRACT", rxy, vb=6.0), vb=3.5)), va=1.0), vb=0.9 * P["ciliar"])
    col = mix_rgb(nt, base, (0.82, 0.30, 0.25), tint); col = mix_rgb(nt, col, (0.78, 0.18, 0.16), ciliar); col = mix_rgb(nt, col, (0.60, 0.05, 0.04), math_(nt, "MULTIPLY", vasos, vb=0.9))
    if P["hemorragia_subconjuntival"]: col = mix_rgb(nt, col, (0.48, 0.02, 0.02), calota_mask(nt, sep, P["hem_centro"], P["hem_raio"], 0.8))
    if P["pinguecula"]: col = mix_rgb(nt, col, (0.86, 0.74, 0.34), calota_mask(nt, sep, P["ping_centro"], 1.3, 0.5))
    if P["lesao_pigmentada"]: col = mix_rgb(nt, col, (0.22, 0.13, 0.08), calota_mask(nt, sep, P["les_centro"], P["les_raio"], 0.4))
    # limbo: transicao escura/azulada
    band = math_(nt, "ABSOLUTE", math_(nt, "SUBTRACT", rxy, vb=6.3)); lim = math_(nt, "SUBTRACT", None, clamp01(nt, math_(nt, "DIVIDE", band, vb=0.6)), va=1.0)
    col = mix_rgb(nt, col, (0.55, 0.50, 0.50), math_(nt, "MULTIPLY", lim, vb=0.3))
    nt.links.new(col, b.inputs["Base Color"]); link(nt, b, "BSDF", out, "Surface"); return m

def mat_cornea(P):
    m, nt = new_mat("cornea"); out = node(nt, "ShaderNodeOutputMaterial")
    tr = node(nt, "ShaderNodeBsdfTransparent"); gl = node(nt, "ShaderNodeBsdfGlossy"); setin(gl, "Roughness", 0.03); fr = node(nt, "ShaderNodeFresnel"); setin(fr, "IOR", 1.376)
    g = node(nt, "ShaderNodeMixShader"); link(nt, fr, "Fac", g, "Fac"); link(nt, tr, "BSDF", g, 1); link(nt, gl, "BSDF", g, 2); last = g
    if P["opacidade_corneana"]:
        sc, sep = obj_mm(nt)
        tl = node(nt, "ShaderNodeBsdfTranslucent"); setin(tl, "Color", (0.92, 0.92, 0.90, 1)); df = node(nt, "ShaderNodeBsdfDiffuse"); setin(df, "Color", (0.92, 0.91, 0.88, 1))
        mx0 = node(nt, "ShaderNodeMixShader"); setin(mx0, "Fac", 0.5); link(nt, tl, "BSDF", mx0, 1); link(nt, df, "BSDF", mx0, 2)
        mask = calota_mask(nt, sep, P["opac_centro"], P["opac_raio"], 1.2)
        nz = node(nt, "ShaderNodeTexNoise"); setin(nz, "Scale", 0.9); setin(nz, "Detail", 4); link(nt, sc, 0, nz, "Vector")
        mk = math_(nt, "MINIMUM", math_(nt, "MULTIPLY", mask, math_(nt, "MULTIPLY", nz.outputs["Fac"], vb=1.7)), vb=0.97 if P["opac_densa"] else 0.75)
        mx = node(nt, "ShaderNodeMixShader"); nt.links.new(mk, mx.inputs["Fac"]); link(nt, g, "Shader", mx, 1); link(nt, mx0, "Shader", mx, 2); last = mx
    link(nt, last, "Shader", out, "Surface")
    for attr, val in (("surface_render_method", "DITHERED"), ("use_transparent_shadow", True), ("show_transparent_back", False)):
        try: setattr(m, attr, val)
        except Exception: pass
    return m

def mat_iris(P):
    m, nt = new_mat("iris"); out = node(nt, "ShaderNodeOutputMaterial"); b = node(nt, "ShaderNodeBsdfPrincipled"); setin(b, "Roughness", 0.7); setin(b, "Specular IOR Level", 0.2)
    sc, sep = obj_mm(nt)
    r = math_(nt, "SQRT", math_(nt, "ADD", math_(nt, "MULTIPLY", sep.outputs[0], sep.outputs[0]), math_(nt, "MULTIPLY", sep.outputs[1], sep.outputs[1])))
    rn = math_(nt, "DIVIDE", r, vb=6.0)
    if P.get("iris_tex") and os.path.exists(P["iris_tex"]):
        # foto de iris real (CC) mapeada em disco: uv = (x/12+0.5, y/12+0.5)
        img = node(nt, "ShaderNodeTexImage"); img.image = bpy.data.images.load(P["iris_tex"]); img.extension = "EXTEND"
        cx = math_(nt, "ADD", math_(nt, "DIVIDE", sep.outputs[0], vb=13.8), vb=0.5); cy = math_(nt, "ADD", math_(nt, "DIVIDE", sep.outputs[1], vb=13.8), vb=0.5)
        comb = node(nt, "ShaderNodeCombineXYZ"); nt.links.new(cx, comb.inputs[0]); nt.links.new(cy, comb.inputs[1]); link(nt, comb, 0, img, "Vector")
        col = img.outputs["Color"]
    else:
        ang = node(nt, "ShaderNodeMath", operation="ARCTAN2"); nt.links.new(sep.outputs[1], ang.inputs[0]); nt.links.new(sep.outputs[0], ang.inputs[1])
        comb = node(nt, "ShaderNodeCombineXYZ"); nt.links.new(math_(nt, "MULTIPLY", ang.outputs[0], vb=9.0), comb.inputs[0]); nt.links.new(math_(nt, "MULTIPLY", rn, vb=18.0), comb.inputs[1])
        nz = node(nt, "ShaderNodeTexNoise"); setin(nz, "Scale", 1.0); setin(nz, "Detail", 8); setin(nz, "Roughness", 0.7); link(nt, comb, 0, nz, "Vector")
        c1, c2 = P["iris_cor"]; ramp = node(nt, "ShaderNodeValToRGB"); ramp.color_ramp.elements[0].color = (*c1, 1); ramp.color_ramp.elements[1].color = (*c2, 1); link(nt, nz, "Fac", ramp, "Fac")
        col = mix_rgb(nt, ramp.outputs["Color"], (0.03, 0.02, 0.02), math_(nt, "MULTIPLY", math_(nt, "MULTIPLY", rn, rn), vb=0.85))
    # pupila
    pupil = math_(nt, "SUBTRACT", None, clamp01(nt, math_(nt, "DIVIDE", math_(nt, "SUBTRACT", r, vb=P["pupila_r"]), vb=0.25)), va=1.0)
    pc = (0.0, 0.0, 0.0)
    if P["catarata_leucocoria"]: pc = (0.85, 0.83, 0.75) if P["leucocoria_branca"] else (0.50, 0.47, 0.42)
    col = mix_rgb(nt, col, pc, pupil)
    if P["catarata_leucocoria"]:
        nz2 = node(nt, "ShaderNodeTexNoise"); setin(nz2, "Scale", 1.3); setin(nz2, "Detail", 5); link(nt, sc, 0, nz2, "Vector")
        col = mix_rgb(nt, col, (0.97, 0.95, 0.88), math_(nt, "MULTIPLY", pupil, math_(nt, "MULTIPLY", nz2.outputs["Fac"], vb=0.7)))
    nt.links.new(col, b.inputs["Base Color"]); link(nt, b, "BSDF", out, "Surface"); return m

# ---------- montagem ----------
def build_eye(P, eye_loc, escala=1.0, rot=(0, 0, 0)):
    """globo + cornea + iris + hipopio + asa de pterigio, centrados em eye_loc, olhando para +Z local; o pivo recebe
    a rotacao rot (Euler XYZ) e depois a do olhar. escala reescala o conjunto (raio do globo = 12 mm * escala)."""
    piv = bpy.data.objects.new("pivo", None); bpy.context.collection.objects.link(piv); piv.location = eye_loc; piv.scale = (escala, escala, escala)
    piv.rotation_euler = rot; bpy.context.view_layer.update()
    def adota(o):
        o.parent = piv; o.matrix_parent_inverse = Matrix.Identity(4)
    # objetos criados na origem (coordenadas locais do pivo)
    globo = esfera("globo", R_GLOBO, (0, 0, 0), corte_z=(1, math.sqrt(R_GLOBO ** 2 - R_ABERTURA ** 2) + 0.05 * MM)); globo.data.materials.append(mat_sclera(P)); adota(globo)
    cor = esfera("cornea", R_COR, C_COR, corte_z=(-1, C_COR.z + math.sqrt(R_COR ** 2 - R_ABERTURA ** 2) - 1.4 * MM)); cor.data.materials.append(mat_cornea(P)); adota(cor)
    bpy.ops.mesh.primitive_circle_add(vertices=160, radius=6.6 * MM, fill_type="NGON", location=(0, 0, 10.0 * MM)); iris = bpy.context.active_object; iris.name = "iris"; iris.data.materials.append(mat_iris(P)); adota(iris)
    if P["hipopio"]:
        h = P["hipopio_mm"] * MM; ylim = -6.0 * MM + h; rr = 6.2 * MM; bm = bmesh.new(); pts = []
        a0 = math.asin(max(-1.0, min(1.0, ylim / rr)))
        for k in range(49):
            ang = (-math.pi - a0) + ((a0) - (-math.pi - a0)) * k / 48
            pts.append(bm.verts.new((rr * math.cos(ang), rr * math.sin(ang), 10.05 * MM)))
        face = bm.faces.new(pts); res = bmesh.ops.extrude_face_region(bm, geom=[face]); bmesh.ops.translate(bm, verts=[v for v in res["geom"] if isinstance(v, bmesh.types.BMVert)], vec=(0, 0, 1.3 * MM))
        hp = mesh_obj("hipopio", bm, smooth=False); hp.data.materials.append(mat_plain("hipopio_m", (0.93, 0.92, 0.85), 0.7, 0.4)); adota(hp)
    if P["pterigio"]: w = asa_pterigio(P); adota(w)
    # olhar: rotacao extra do pivo
    from mathutils import Euler
    piv.rotation_euler = (Euler(rot).to_matrix() @ Matrix.Rotation(math.radians(P["olhar_x"]), 3, "X") @ Matrix.Rotation(math.radians(P["olhar_y"]), 3, "Y")).to_euler()
    return piv

def build(P):
    sc = reset(P); eye_loc = Vector((0, 0, P["proptose_mm"] * MM))
    piv = bpy.data.objects.new("pivo", None); bpy.context.collection.objects.link(piv); piv.location = eye_loc
    def adota(o):
        o.parent = piv; o.matrix_parent_inverse = piv.matrix_world.inverted()
    # fornice: tecido rosado atras do globo, para os cantos nao mostrarem vazio
    forn = esfera("fornice", 13.2 * MM, eye_loc + Vector((0, 0, -1.0 * MM)), seg=96, ring=64, corte_z=(1, 4.0 * MM)); forn.data.materials.append(mat_plain("fornice_m", (0.78, 0.45, 0.42), 0.4, 0.3))
    # globo com abertura para a cornea (z > 10.4 mm removido)
    globo = esfera("globo", R_GLOBO, eye_loc, corte_z=(1, math.sqrt(R_GLOBO ** 2 - R_ABERTURA ** 2) + 0.05 * MM)); globo.data.materials.append(mat_sclera(P)); adota(globo)
    cor = esfera("cornea", R_COR, eye_loc + C_COR, corte_z=(-1, C_COR.z + math.sqrt(R_COR ** 2 - R_ABERTURA ** 2) - 1.4 * MM)); cor.data.materials.append(mat_cornea(P)); adota(cor)
    bpy.ops.mesh.primitive_circle_add(vertices=160, radius=6.6 * MM, fill_type="NGON", location=eye_loc + Vector((0, 0, 10.0 * MM))); iris = bpy.context.active_object; iris.name = "iris"; iris.data.materials.append(mat_iris(P)); adota(iris)
    if P["hipopio"]:
        h = P["hipopio_mm"] * MM; ylim = -6.0 * MM + h; rr = 6.2 * MM; bm = bmesh.new(); pts = []
        a0 = math.asin(max(-1.0, min(1.0, ylim / rr)))       # angulo do corte: arco de -pi-a0 ate a0 por baixo
        for k in range(49):
            ang = -math.pi - a0 + (2 * a0 + math.pi) * k / 48 * 1.0
            ang = (-math.pi - a0) + ((a0) - (-math.pi - a0)) * k / 48
            pts.append(bm.verts.new((rr * math.cos(ang), rr * math.sin(ang), 10.05 * MM)))
        face = bm.faces.new(pts); res = bmesh.ops.extrude_face_region(bm, geom=[face]); bmesh.ops.translate(bm, verts=[v for v in res["geom"] if isinstance(v, bmesh.types.BMVert)], vec=(0, 0, 1.3 * MM))
        hp = mesh_obj("hipopio", bm, smooth=False); hp.location = eye_loc; hp.data.materials.append(mat_plain("hipopio_m", (0.93, 0.92, 0.85), 0.7, 0.4)); adota(hp)
    if P["pterigio"]: w = asa_pterigio(P); w.location = eye_loc; adota(w); print("DEBUG asa verts", len(w.data.vertices), "faces", len(w.data.polygons), "dim_mm", [round(v * 1000, 1) for v in w.dimensions], "loc", [round(v * 1000, 1) for v in w.matrix_world.translation], flush=True)
    piv.rotation_euler = (math.radians(P["olhar_x"]), math.radians(P["olhar_y"]), 0)
    if not NOSKIN:
        pele = skin_lids(P); pele.data.materials.append(mat_skin(P)); pele.data.materials.append(mat_plain("mucosa", (0.55, 0.30, 0.28), 0.35, 0.2)); cilios(P)
        if P["calazio"]:
            x, y = P["calazio_x"] * MM, P["calazio_y"] * MM
            bpy.ops.mesh.primitive_uv_sphere_add(radius=P["calazio_mm"] * MM, location=(x, y, skin_z(x, y, P) - 0.3 * P["calazio_mm"] * MM)); c = bpy.context.active_object; c.scale = (1, 0.85, 0.6); bpy.ops.object.shade_smooth()
            c.data.materials.append(mat_skin(P, tinta=(0.78, 0.38, 0.33) if P["calazio_vermelho"] else None))
    # mundo / luz
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True; bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (*P["luz_cor"], 1); bg.inputs[1].default_value = P["luz_mundo"]
    if HDRIS and P["usa_hdri"]:
        env = w.node_tree.nodes.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(HDRIS[P["hdri_i"] % len(HDRIS)])
        mp = w.node_tree.nodes.new("ShaderNodeMapping"); tc = w.node_tree.nodes.new("ShaderNodeTexCoord"); mp.inputs["Rotation"].default_value = (0, 0, P["hdri_rot"])
        w.node_tree.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); w.node_tree.links.new(mp.outputs["Vector"], env.inputs["Vector"]); w.node_tree.links.new(env.outputs["Color"], bg.inputs["Color"])
        bg.inputs[1].default_value = P["luz_mundo"] * 1.0
    bpy.ops.object.light_add(type="AREA", location=(P["luz_x"] * MM, P["luz_y"] * MM, 250 * MM)); la = bpy.context.active_object; la.data.energy = P["luz_area"]; la.data.size = 0.3; la.data.color = P["luz_cor"]
    # camera (equivalente full-frame; foco profundo como celular)
    dist = P["cam_mm"] * MM; ax, ay, lente = P["cam_ang_x"], P["cam_ang_y"], P["lente_mm"]
    if WIDE: dist, lente, ax, ay = 0.30, 50, 25, 20
    if TOPO: dist, lente, ax, ay = 0.15, 50, 0, 0
    loc = Vector((dist * math.sin(math.radians(ay)), dist * math.sin(math.radians(ax)), dist * math.cos(math.radians(max(abs(ax), abs(ay))))))
    bpy.ops.object.camera_add(location=loc); cam = bpy.context.active_object; sc.camera = cam; cam.data.clip_start = 0.003; cam.data.clip_end = 5.0
    cam.data.lens = lente; cam.data.sensor_width = 36; cam.data.dof.use_dof = False
    if TOPO: cam.data.type = "ORTHO"; cam.data.ortho_scale = 0.06
    tgt = Vector((P["mira_x"] * MM, P["mira_y"] * MM, 10 * MM)) if not (TOPO or WIDE) else Vector((0, 0, 10 * MM))
    fwd = (tgt - loc).normalized(); right = fwd.cross(Vector((0, 1, 0))).normalized(); upv = right.cross(fwd).normalized()
    cam.matrix_world = Matrix.Translation(loc) @ Matrix((right, upv, -fwd)).transposed().to_4x4() @ Matrix.Rotation(math.radians(P["rolagem"]), 4, "Z")
    if P["flash"]:
        bpy.ops.object.light_add(type="POINT", location=loc + Vector((8 * MM, 4 * MM, 0))); fl = bpy.context.active_object; fl.data.energy = P["flash_w"]; fl.data.shadow_soft_size = 0.004; fl.data.color = (1, 0.97, 0.92)
    return sc

# ---------- amostragem ----------
SKIN = [(0.80, 0.60, 0.50), (0.72, 0.52, 0.40), (0.62, 0.43, 0.31), (0.50, 0.33, 0.23), (0.38, 0.24, 0.16), (0.26, 0.16, 0.11), (0.18, 0.11, 0.08)]
IRIS = [((0.05, 0.03, 0.02), (0.30, 0.16, 0.08)), ((0.10, 0.06, 0.03), (0.45, 0.28, 0.12)), ((0.15, 0.20, 0.30), (0.55, 0.65, 0.75)), ((0.12, 0.18, 0.10), (0.45, 0.50, 0.30)), ((0.08, 0.05, 0.03), (0.35, 0.22, 0.10))]
SINAIS = [None, None, "hiperemia", "conjuntivite", "ictericia", "pterigio", "pinguecula", "hemorragia_subconjuntival", "catarata_leucocoria", "opacidade_corneana", "uveite", "alteracao_palpebral", "lesao_pigmentada", "ceratite"]
def sample(rng, force=None):
    P = {l: 0 for l in LABELS}; sign = force if force is not None else rng.choice(SINAIS); P["sinal"] = sign or "normal"
    P.update(hiperemia=0.0, conjuntivite=0.0, ictericia=0.0, ciliar=0.0, hipopio=0, calazio=0, ptose=0, opac_densa=0, proptose_mm=rng.uniform(-0.5, 0.5))
    if sign == "hiperemia": P["hiperemia"] = rng.uniform(0.5, 1.0)
    if sign == "conjuntivite": P["conjuntivite"] = rng.uniform(0.5, 1.0); P["hiperemia"] = rng.uniform(0.5, 1.0)
    if sign == "ictericia": P["ictericia"] = rng.uniform(0.5, 1.0)
    if sign == "pterigio": P["pterigio"] = 1; P["hiperemia"] = rng.uniform(0.0, 0.35)
    if sign == "pinguecula": P["pinguecula"] = 1
    if sign == "hemorragia_subconjuntival": P["hemorragia_subconjuntival"] = 1
    if sign == "catarata_leucocoria": P["catarata_leucocoria"] = 1; P["pupila_min"] = 2.0
    if sign == "opacidade_corneana": P["opacidade_corneana"] = 1; P["opac_densa"] = int(rng.random() < 0.5)
    if sign == "ceratite": P["ceratite"] = 1; P["opacidade_corneana"] = 1; P["hiperemia"] = rng.uniform(0.4, 0.9); P["ciliar"] = rng.uniform(0.6, 1.0)
    if sign == "uveite": P["uveite"] = 1; P["hiperemia"] = rng.uniform(0.2, 0.6); P["ciliar"] = rng.uniform(0.7, 1.0); P["hipopio"] = int(rng.random() < 0.4) if force is None else 1
    if sign == "alteracao_palpebral": P["alteracao_palpebral"] = 1; P["calazio"] = 1
    if sign == "lesao_pigmentada": P["lesao_pigmentada"] = 1
    if sign is None: P["hiperemia"] = rng.uniform(0.0, 0.25)
    P["pupila_r"] = max(P.get("pupila_min", 0), rng.uniform(1.1, 2.8) if not (sign == "uveite") else rng.uniform(0.9, 1.6)); P["leucocoria_branca"] = int(rng.random() < 0.5)
    P["pele_cor"] = rng.choice(SKIN); P["pele_tex_i"] = rng.randrange(1000); P["pele_tex_u"] = rng.uniform(0, 1); P["pele_tex_v"] = rng.uniform(0, 1); P["pele_tex_rot"] = rng.uniform(0, 6.28); P["iris_cor"] = rng.choice(IRIS); P["iris_tex"] = rng.choice(IRIS_TEX) if IRIS_TEX and rng.random() < 0.6 else ""
    P["fenda_w"] = rng.uniform(24, 29) * MM; P["fenda_h_sup"] = rng.uniform(4.0, 6.0) * MM; P["fenda_h_inf"] = rng.uniform(3.5, 5.0) * MM; P["fenda_cx"] = rng.uniform(-1.5, 1.5) * MM; P["fenda_cy"] = rng.uniform(-1.0, 1.0) * MM
    P["prega_mm"] = rng.uniform(1.2, 3.0)
    if sign == "alteracao_palpebral" and rng.random() < 0.4: P["fenda_h_sup"] = rng.uniform(1.5, 3.0) * MM; P["calazio"] = 0; P["ptose"] = 1
    P["olhar_x"] = rng.uniform(-8, 8); P["olhar_y"] = rng.uniform(-10, 10)
    lado = rng.choice([-1, 1]); P["pterigio_lado"] = lado; P["pterigio_mm"] = rng.uniform(1.0, 4.5)
    P["hem_centro"] = (lado * rng.uniform(5, 9), rng.uniform(-3, 3), rng.uniform(6, 9)); P["hem_raio"] = rng.uniform(3, 6)
    P["ping_centro"] = (lado * rng.uniform(7.0, 8.5), rng.uniform(-1.5, 1.5), 8.5)
    P["les_centro"] = (lado * rng.uniform(6.5, 9.5), rng.uniform(-3, 3), rng.uniform(7, 9)); P["les_raio"] = rng.uniform(0.8, 2.5)
    P["opac_centro"] = (rng.uniform(-3, 3), rng.uniform(-3, 3), 13.0); P["opac_raio"] = rng.uniform(1.5, 4.0)
    P["hipopio_mm"] = rng.uniform(2.0, 4.0)
    if P["hipopio"]: P["fenda_h_inf"] = rng.uniform(4.8, 5.8) * MM
    P["calazio_mm"] = rng.uniform(2.0, 4.0); P["calazio_x"] = rng.uniform(-8, 8); P["calazio_y"] = rng.choice([1, -1]) * rng.uniform(7.0, 10.0); P["calazio_vermelho"] = int(rng.random() < 0.5)
    P["luz_cor"] = rng.choice([(1, 1, 1), (1, 0.95, 0.85), (0.9, 0.95, 1), (1, 0.9, 0.75)]); P["luz_mundo"] = rng.uniform(0.15, 0.8); P["luz_area"] = rng.uniform(2, 14); P["luz_x"] = rng.uniform(-150, 150); P["luz_y"] = rng.uniform(-100, 200)
    P["usa_hdri"] = int(rng.random() < 0.8); P["hdri_i"] = rng.randrange(1000); P["hdri_rot"] = rng.uniform(0, 6.28)
    P["flash"] = int(rng.random() < 0.35); P["flash_w"] = rng.uniform(2, 8)
    P["cam_mm"] = rng.uniform(50, 95); P["cam_ang_x"] = rng.uniform(-14, 14); P["cam_ang_y"] = rng.uniform(-18, 18); P["lente_mm"] = max(30.0, min(110.0, P["cam_mm"] / rng.uniform(0.8, 1.45)))
    P["exposicao"] = rng.uniform(-1.7, -0.7); P["mira_x"] = rng.uniform(-4, 4); P["mira_y"] = rng.uniform(-3, 3); P["rolagem"] = rng.uniform(-12, 12)
    return P

def labels_of(P):
    y = {l: int(P.get(l, 0)) for l in LABELS}
    if P["hiperemia"] >= 0.45 or P["ciliar"] >= 0.5: y["hiperemia"] = 1
    if P.get("hipopio"): y["uveite"] = 1
    if P.get("calazio") or P.get("ptose"): y["alteracao_palpebral"] = 1
    return y

def main():
    rng = random.Random(SEED); rows = []
    forced = [None, "hiperemia", "conjuntivite", "ictericia", "pterigio", "pinguecula", "hemorragia_subconjuntival", "catarata_leucocoria", "opacidade_corneana", "uveite", "alteracao_palpebral", "ceratite"] if MOSTRUARIO else ([FORCAR] * N if FORCAR else [None] * N)
    for k, f in enumerate(forced):
        P = sample(rng, force=f); build(P)
        name = f"s{SEED:03d}_{k:04d}_{P['sinal']}"; path = os.path.abspath(os.path.join(OUT, name + ".jpg"))
        bpy.context.scene.render.filepath = path; bpy.ops.render.render(write_still=True)
        y = labels_of(P); rows.append({"file": name + ".jpg", "subject_id": name, "source": "sintese_blender", "domain": "synthetic", **y, "sinal": P["sinal"],
                                        "params": json.dumps({k2: (list(v) if isinstance(v, tuple) else v) for k2, v in P.items()})})
        print("render", name, "pele", P["pele_cor"], "expo %.2f hdri %d luz_mundo %.2f" % (P["exposicao"], P["usa_hdri"], P["luz_mundo"]), flush=True)
    csvp = os.path.join(OUT, "labels.csv"); new = not os.path.exists(csvp)
    with open(csvp, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "subject_id", "source", "domain", *LABELS, "sinal", "params"])
        if new: w.writeheader()
        w.writerows(rows)
if __name__ == "__main__":
    main()
