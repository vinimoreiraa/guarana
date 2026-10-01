"""
Protótipo de olho paramétrico para dados sintéticos (Guaraná / Ocular.IA).
Blender 5.x, headless:
  /Applications/Blender.app/Contents/MacOS/Blender -b -P olho_prototipo.py -- --sinal hemorragia --seed 3 --out /caminho/img.png
Unidades: metros (1 mm = 0.001). Eixo óptico = +Z (câmera olha de +Z para -Z). Nasal = -X (olho direito).
"""
import bpy, sys, math, random, argparse, os

# ---------------- argumentos ----------------
argv = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--sinal", default="normal",
    choices=["normal","hemorragia","ictericia","hiperemia","pterigio","pinguecula","catarata",
             "opacidade","hipopio","ptose","calazio","proptose"])
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--out", default="/tmp/olho.png")
ap.add_argument("--hdri", default="")
ap.add_argument("--res", type=int, default=512)
ap.add_argument("--samples", type=int, default=64)
ap.add_argument("--engine", default="CYCLES")
ap.add_argument("--flash", type=float, default=0.0, help="potência do flash pontual em W (0 = sem flash; 1–3 W a 12 cm ≈ flash de celular)")
A = ap.parse_args(argv)
random.seed(A.seed)
MM = 0.001

# ---------------- cena limpa ----------------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = A.engine
sc.render.resolution_x = sc.render.resolution_y = A.res
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = A.out
if A.engine == "CYCLES":
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "METAL"; prefs.get_devices()
        for d in prefs.devices: d.use = (d.type == "METAL")
        sc.cycles.device = "GPU"
    except Exception as e:
        print("GPU indisponível, CPU:", e)
    sc.cycles.samples = A.samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 8; sc.cycles.transmission_bounces = 8; sc.cycles.transparent_max_bounces = 8
    sc.cycles.caustics_refractive = True

# ---------------- helpers de nós ----------------
def new_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return m, nt, out

def node(nt, tipo, **kw):
    n = nt.nodes.new(tipo)
    for k, v in kw.items():
        if k == "inputs":
            for ik, iv in v.items(): n.inputs[ik].default_value = iv
        else: setattr(n, k, v)
    return n

def link(nt, a, ao, b, bi): nt.links.new(a.outputs[ao], b.inputs[bi])

def sphere(name, r, loc=(0,0,0), seg=96, ring=64, smooth=True):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=seg, ring_count=ring)
    o = bpy.context.active_object; o.name = name
    if smooth: bpy.ops.object.shade_smooth()
    return o

# ---------------- parâmetros anatômicos (mm) ----------------
R_SCLERA = 12.0                 # raio do globo (diâmetro ~24 mm)
R_CORNEA = 7.8                  # raio de curvatura anterior da córnea
Z_CORNEA = 5.6                  # centro da esfera corneana → ápice em 13.4 mm, limbo em z≈10.2, Ø limbo ≈12.6 mm
Z_LIMBO  = 10.2
Z_IRIS   = 9.9                  # plano da íris (câmara anterior ≈3 mm)
R_IRIS   = 6.0
R_PUPILA = random.uniform(1.5, 4.0)   # raio da pupila (3–8 mm de diâmetro)
IOR_CORNEA = 1.376
PROPTOSE = 3.0 if A.sinal == "proptose" else 0.0   # mm de deslocamento anterior do globo

# ---------------- geometria do globo ----------------
esclera = sphere("Esclera", R_SCLERA*MM)
cornea  = sphere("Cornea", R_CORNEA*MM, loc=(0,0,Z_CORNEA*MM))
bpy.ops.mesh.primitive_circle_add(radius=R_IRIS*MM, location=(0,0,Z_IRIS*MM), fill_type="NGON", vertices=128)
iris = bpy.context.active_object; iris.name = "Iris"
bpy.ops.mesh.primitive_circle_add(radius=(R_PUPILA+0.3)*MM, location=(0,0,(Z_IRIS-0.6)*MM), fill_type="NGON", vertices=96)
lente = bpy.context.active_object; lente.name = "Cristalino"   # o que se vê pela pupila
for o in (esclera, cornea, iris, lente):
    o.parent = None
globo = bpy.data.objects.new("Globo", None); sc.collection.objects.link(globo)
for o in (esclera, cornea, iris, lente): o.parent = globo
globo.location = (0, 0, PROPTOSE*MM)

# ---------------- material: ESCLERA (+ conjuntiva, vasos, sinais) ----------------
m, nt, out = new_mat("M_Esclera"); esclera.data.materials.append(m)
tc = node(nt, "ShaderNodeTexCoord")                 # Object coords em metros, centro do globo
sep = node(nt, "ShaderNodeSeparateXYZ"); link(nt, tc, "Object", sep, "Vector")
# --- vasos: Voronoi distance-to-edge distorcido por noise ---
noise_d = node(nt, "ShaderNodeTexNoise", inputs={"Scale": 400.0, "Detail": 3.0, "Roughness": 0.6})
link(nt, tc, "Object", noise_d, "Vector")
mapn = node(nt, "ShaderNodeVectorMath", operation="MULTIPLY_ADD")
link(nt, noise_d, "Color", mapn, 0); mapn.inputs[1].default_value = (0.0006,0.0006,0.0006); link(nt, tc, "Object", mapn, 2)
# polar: phi = atan2(y,x) (azimute), theta = acos(z/R) (distância angular ao ápice). Vasos correm ao longo de theta.
sepn = node(nt, "ShaderNodeSeparateXYZ"); link(nt, mapn, "Vector", sepn, "Vector")
phi = node(nt, "ShaderNodeMath", operation="ARCTAN2"); link(nt, sepn, "Y", phi, 0); link(nt, sepn, "X", phi, 1)
zn = node(nt, "ShaderNodeMath", operation="DIVIDE", inputs={1: R_SCLERA*MM}); link(nt, sepn, "Z", zn, 0)
theta = node(nt, "ShaderNodeMath", operation="ARCCOSINE"); link(nt, zn, "Value", theta, 0)
pol = node(nt, "ShaderNodeCombineXYZ"); link(nt, phi, "Value", pol, "X"); link(nt, theta, "Value", pol, "Y")
ANISO = node(nt, "ShaderNodeVectorMath", operation="MULTIPLY"); link(nt, pol, "Vector", ANISO, 0)
ANISO.inputs[1].default_value = (1.0, 0.18, 1.0)      # <1 em theta → células esticadas radialmente → vasos radiais
vor = node(nt, "ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
DENS_VASOS = {"hiperemia": random.uniform(28, 45)}.get(A.sinal, random.uniform(10, 18))   # escala em rad^-1
vor.inputs["Scale"].default_value = DENS_VASOS
link(nt, ANISO, "Vector", vor, "Vector")
ramp_v = node(nt, "ShaderNodeValToRGB"); link(nt, vor, "Distance", ramp_v, "Fac")
LARG = 0.016 if A.sinal == "hiperemia" else 0.005            # meia-largura dos vasos (unidade da distância voronoi)
ramp_v.color_ramp.elements[0].position = 0.0; ramp_v.color_ramp.elements[0].color = (1,1,1,1)
ramp_v.color_ramp.elements[1].position = LARG; ramp_v.color_ramp.elements[1].color = (0,0,0,1)
# só na parte anterior (conjuntiva visível), mais denso perto do limbo e do fórnice
vis = node(nt, "ShaderNodeMath", operation="GREATER_THAN", inputs={1: 0.0}); link(nt, sep, "Z", vis, 0)
vasos = node(nt, "ShaderNodeMath", operation="MULTIPLY"); link(nt, ramp_v, "Color", vasos, 0); link(nt, vis, "Value", vasos, 1)
# --- cor base da esclera (branco levemente azulado; icterícia → amarelo) ---
cor_base = (0.86, 0.84, 0.80, 1) if A.sinal != "ictericia" else (0.90, 0.78, 0.30, 1)
if A.sinal == "ictericia":
    k = random.uniform(0.35, 1.0)     # intensidade da icterícia
    cor_base = tuple(0.86*(1-k) + c*k for c in (0.90, 0.78, 0.30)) + (1,)
if A.sinal == "hiperemia":   # injeção conjuntival: tinta rosada difusa, mais forte perto do fórnice (longe do limbo)
    k = random.uniform(0.35, 0.7); cor_base = tuple(cor_base[i]*(1-k) + (0.80, 0.42, 0.38)[i]*k for i in range(3)) + (1,)
    globo["hiperemia_grau"] = k
rgb = node(nt, "ShaderNodeRGB"); rgb.outputs[0].default_value = cor_base
mix_v = node(nt, "ShaderNodeMix", data_type="RGBA"); mix_v.inputs["B"].default_value = (0.55, 0.03, 0.02, 1)
link(nt, vasos, "Value", mix_v, "Factor"); link(nt, rgb, "Color", mix_v, "A")
# --- hemorragia subconjuntival: mancha lisa, borda nítida, vermelho vivo ---
cor_atual = mix_v
if A.sinal == "hemorragia":
    theta = math.radians(random.uniform(38, 55))                      # 0° = ápice; limbo ≈ 32°; borda palpebral ≈ 60°
    phi = random.choice([0, math.pi]) + random.uniform(-0.6, 0.6)     # temporal ou nasal (vertical fica sob as pálpebras)
    centro = (R_SCLERA*MM*math.sin(theta)*math.cos(phi), R_SCLERA*MM*math.sin(theta)*math.sin(phi), R_SCLERA*MM*math.cos(theta))
    d = node(nt, "ShaderNodeVectorMath", operation="DISTANCE"); link(nt, tc, "Object", d, 0); d.inputs[1].default_value = centro
    nz = node(nt, "ShaderNodeTexNoise", inputs={"Scale": 300.0, "Detail": 2.0}); link(nt, tc, "Object", nz, "Vector")
    dist_n = node(nt, "ShaderNodeMath", operation="MULTIPLY_ADD"); link(nt, nz, "Fac", dist_n, 0)
    dist_n.inputs[1].default_value = 0.0015; link(nt, d, "Value", dist_n, 2)
    raio = random.uniform(3.0, 7.0)*MM
    m_h = node(nt, "ShaderNodeMapRange", inputs={"From Min": raio, "From Max": raio+0.0004, "To Min": 1.0, "To Max": 0.0}, clamp=True)
    link(nt, dist_n, "Value", m_h, "Value")
    mix_h = node(nt, "ShaderNodeMix", data_type="RGBA"); mix_h.inputs["B"].default_value = (0.42, 0.015, 0.01, 1)
    link(nt, m_h, "Result", mix_h, "Factor"); link(nt, cor_atual, "Result", mix_h, "A"); cor_atual = mix_h
# --- pterígio / pinguécula: cunha ou bolha carnosa no lado nasal (-X) ---
if A.sinal in ("pterigio", "pinguecula"):
    ang_max = math.radians(random.uniform(12, 22))           # semi-abertura da cunha
    x_apex = (R_IRIS - random.uniform(0.5, 3.5))*MM if A.sinal == "pterigio" else (R_IRIS + 1.0)*MM
    # ângulo azimutal em torno do eixo -X no plano XY: |atan2(y, -x)| < ang_max
    negx = node(nt, "ShaderNodeMath", operation="MULTIPLY", inputs={1: -1.0}); link(nt, sep, "X", negx, 0)
    at = node(nt, "ShaderNodeMath", operation="ARCTAN2"); link(nt, sep, "Y", at, 0); link(nt, negx, "Value", at, 1)
    ab = node(nt, "ShaderNodeMath", operation="ABSOLUTE"); link(nt, at, "Value", ab, 0)
    cunha = node(nt, "ShaderNodeMath", operation="LESS_THAN", inputs={1: ang_max}); link(nt, ab, "Value", cunha, 0)
    pos = node(nt, "ShaderNodeMath", operation="GREATER_THAN", inputs={1: 0.0}); link(nt, negx, "Value", pos, 0)
    pt = node(nt, "ShaderNodeMath", operation="MULTIPLY"); link(nt, cunha, "Value", pt, 0); link(nt, pos, "Value", pt, 1)
    if A.sinal == "pinguecula":   # bolha ~2 mm perto do limbo
        d2 = node(nt, "ShaderNodeVectorMath", operation="DISTANCE"); link(nt, tc, "Object", d2, 0)
        d2.inputs[1].default_value = (-(R_IRIS+1.5)*MM, 0, (Z_LIMBO-0.8)*MM)
        m2 = node(nt, "ShaderNodeMapRange", inputs={"From Min": 0.0010, "From Max": 0.0016, "To Min": 1.0, "To Max": 0.0}, clamp=True)
        link(nt, d2, "Value", m2, "Value"); pt = m2
    cor_carne = (0.75, 0.55, 0.40, 1) if A.sinal == "pterigio" else (0.85, 0.75, 0.40, 1)
    mix_p = node(nt, "ShaderNodeMix", data_type="RGBA"); mix_p.inputs["B"].default_value = cor_carne
    link(nt, pt, "Value" if A.sinal == "pterigio" else "Result", mix_p, "Factor"); link(nt, cor_atual, "Result", mix_p, "A"); cor_atual = mix_p
    bpy.types.Scene.pterigio_apex = bpy.props.FloatProperty()  # (só para registro)
    globo["pterigio_apex_mm"] = x_apex/MM; globo["pterigio_ang_deg"] = math.degrees(ang_max)
# --- BSDF: pele/conjuntiva úmida com coat molhado; backface = fundo escuro (retina) ---
bsdf = node(nt, "ShaderNodeBsdfPrincipled", inputs={"Roughness": 0.35, "Coat Weight": 1.0, "Coat Roughness": 0.05,
                                                     "Subsurface Weight": 0.3, "Subsurface Radius": (0.002, 0.001, 0.001)})
link(nt, cor_atual, "Result", bsdf, "Base Color")
retina = node(nt, "ShaderNodeBsdfDiffuse", inputs={"Color": (0.02, 0.004, 0.002, 1)})
geo = node(nt, "ShaderNodeNewGeometry")
mixs = node(nt, "ShaderNodeMixShader"); link(nt, geo, "Backfacing", mixs, "Fac"); link(nt, bsdf, "BSDF", mixs, 1); link(nt, retina, "BSDF", mixs, 2)
# esconde a calota da esclera sob a córnea (z > Z_LIMBO) → transparente
transp = node(nt, "ShaderNodeBsdfTransparent")
sob = node(nt, "ShaderNodeMath", operation="GREATER_THAN", inputs={1: (Z_LIMBO-0.05)*MM}); link(nt, sep, "Z", sob, 0)
mixt = node(nt, "ShaderNodeMixShader"); link(nt, sob, "Value", mixt, "Fac"); link(nt, mixs, "Shader", mixt, 1); link(nt, transp, "BSDF", mixt, 2)
link(nt, mixt, "Shader", out, "Surface")

# ---------------- material: CÓRNEA (vidro IOR 1.376; opacidade/pterígio opcionais) ----------------
m, nt, out = new_mat("M_Cornea"); cornea.data.materials.append(m)
glass = node(nt, "ShaderNodeBsdfGlass", inputs={"Color": (1,1,1,1), "Roughness": 0.0, "IOR": IOR_CORNEA})
shader_c = glass
tc2 = node(nt, "ShaderNodeTexCoord"); tc2.object = esclera        # coords do globo, compartilhadas com a esclera
if A.sinal == "opacidade":
    centro = (random.uniform(-3,3)*MM, random.uniform(-3,3)*MM, 13.0*MM); raio = random.uniform(1.5, 4.0)*MM
    d = node(nt, "ShaderNodeVectorMath", operation="DISTANCE"); link(nt, tc2, "Object", d, 0); d.inputs[1].default_value = centro
    nz = node(nt, "ShaderNodeTexNoise", inputs={"Scale": 250.0, "Detail": 4.0}); link(nt, tc2, "Object", nz, "Vector")
    dd = node(nt, "ShaderNodeMath", operation="MULTIPLY_ADD"); link(nt, nz, "Fac", dd, 0); dd.inputs[1].default_value = 0.002; link(nt, d, "Value", dd, 2)
    mr = node(nt, "ShaderNodeMapRange", inputs={"From Min": raio*0.4, "From Max": raio*1.3, "To Min": random.uniform(0.5, 0.95), "To Max": 0.0}, clamp=True)
    link(nt, dd, "Value", mr, "Value")
    leite = node(nt, "ShaderNodeBsdfPrincipled", inputs={"Base Color": (0.85, 0.85, 0.82, 1), "Roughness": 0.4, "Subsurface Weight": 1.0,
                                                          "Subsurface Radius": (0.001,0.001,0.001), "Transmission Weight": 0.3})
    mx = node(nt, "ShaderNodeMixShader"); link(nt, mr, "Result", mx, "Fac"); link(nt, glass, "BSDF", mx, 1); link(nt, leite, "BSDF", mx, 2); shader_c = mx
if A.sinal == "pterigio":   # a cabeça do pterígio invade a córnea: cunha opaca carnosa com vasos
    sep2 = node(nt, "ShaderNodeSeparateXYZ"); link(nt, tc2, "Object", sep2, "Vector")
    negx = node(nt, "ShaderNodeMath", operation="MULTIPLY", inputs={1: -1.0}); link(nt, sep2, "X", negx, 0)
    at = node(nt, "ShaderNodeMath", operation="ARCTAN2"); link(nt, sep2, "Y", at, 0); link(nt, negx, "Value", at, 1)
    ab = node(nt, "ShaderNodeMath", operation="ABSOLUTE"); link(nt, at, "Value", ab, 0)
    # a cunha estreita conforme avança: ângulo permitido cai linearmente até o ápice em x_apex
    prog = node(nt, "ShaderNodeMapRange", inputs={"From Min": globo["pterigio_apex_mm"]*MM, "From Max": R_IRIS*MM + 0.0006,
                                                 "To Min": 0.0, "To Max": math.radians(globo["pterigio_ang_deg"])}, clamp=True)
    link(nt, negx, "Value", prog, "Value")
    cunha = node(nt, "ShaderNodeMath", operation="LESS_THAN"); link(nt, ab, "Value", cunha, 0); link(nt, prog, "Result", cunha, 1)
    zpos = node(nt, "ShaderNodeMath", operation="GREATER_THAN", inputs={1: Z_IRIS*MM}); link(nt, sep2, "Z", zpos, 0)
    msk = node(nt, "ShaderNodeMath", operation="MULTIPLY"); link(nt, cunha, "Value", msk, 0); link(nt, zpos, "Value", msk, 1)
    carne = node(nt, "ShaderNodeBsdfPrincipled", inputs={"Base Color": (0.78, 0.50, 0.38, 1), "Roughness": 0.3, "Coat Weight": 1.0, "Subsurface Weight": 0.4})
    mx = node(nt, "ShaderNodeMixShader"); link(nt, msk, "Value", mx, "Fac"); link(nt, shader_c, "BSDF" if shader_c is glass else "Shader", mx, 1); link(nt, carne, "BSDF", mx, 2); shader_c = mx
link(nt, shader_c, "BSDF" if shader_c is glass else "Shader", out, "Surface")

# ---------------- material: ÍRIS (fibras radiais + pupila variável + hipópio) ----------------
m, nt, out = new_mat("M_Iris"); iris.data.materials.append(m)
tc3 = node(nt, "ShaderNodeTexCoord")
rad = node(nt, "ShaderNodeVectorMath", operation="LENGTH"); link(nt, tc3, "Object", rad, 0)    # distância ao centro (m)
sep3 = node(nt, "ShaderNodeSeparateXYZ"); link(nt, tc3, "Object", sep3, "Vector")
ang = node(nt, "ShaderNodeMath", operation="ARCTAN2"); link(nt, sep3, "Y", ang, 0); link(nt, sep3, "X", ang, 1)
# fibras radiais: noise 1D em ângulo*alto e raio*baixo
combo = node(nt, "ShaderNodeCombineXYZ"); link(nt, ang, "Value", combo, "X"); link(nt, rad, "Value", combo, "Y")
scl = node(nt, "ShaderNodeVectorMath", operation="MULTIPLY"); scl.inputs[1].default_value = (9.0, 900.0, 1.0); link(nt, combo, "Vector", scl, 0)
fib = node(nt, "ShaderNodeTexNoise", inputs={"Scale": 1.0, "Detail": 6.0, "Roughness": 0.7}); link(nt, scl, "Vector", fib, "Vector")
cores_iris = [((0.30,0.17,0.08),(0.55,0.35,0.15)), ((0.10,0.25,0.35),(0.45,0.65,0.75)), ((0.20,0.30,0.15),(0.55,0.60,0.30)), ((0.12,0.08,0.05),(0.35,0.22,0.12))]
c1, c2 = random.choice(cores_iris)
ramp_i = node(nt, "ShaderNodeValToRGB"); link(nt, fib, "Fac", ramp_i, "Fac")
ramp_i.color_ramp.elements[0].color = c1+(1,); ramp_i.color_ramp.elements[1].color = c2+(1,)
# colarete/anel limbar mais escuro
lim = node(nt, "ShaderNodeMapRange", inputs={"From Min": (R_IRIS-1.2)*MM, "From Max": R_IRIS*MM, "To Min": 1.0, "To Max": 0.35}, clamp=True); link(nt, rad, "Value", lim, "Value")
cor_i = node(nt, "ShaderNodeMix", data_type="RGBA"); cor_i.inputs["A"].default_value = (0,0,0,1)
link(nt, lim, "Result", cor_i, "Factor"); link(nt, ramp_i, "Color", cor_i, "B")
bsdf_i = node(nt, "ShaderNodeBsdfPrincipled", inputs={"Roughness": 0.6, "Specular IOR Level": 0.2}); link(nt, cor_i, "Result", bsdf_i, "Base Color")
# pupila = furo transparente (deixa ver o "Cristalino" atrás)
pup = node(nt, "ShaderNodeMath", operation="LESS_THAN", inputs={1: R_PUPILA*MM}); link(nt, rad, "Value", pup, 0)
transp_i = node(nt, "ShaderNodeBsdfTransparent")
mx_i = node(nt, "ShaderNodeMixShader"); link(nt, pup, "Value", mx_i, "Fac"); link(nt, bsdf_i, "BSDF", mx_i, 1); link(nt, transp_i, "BSDF", mx_i, 2)
shader_i = mx_i
if A.sinal == "hipopio":   # nível branco horizontal na parte inferior da câmara anterior (cobre íris e pupila)
    nivel = -random.uniform(1.0, 4.0)*MM       # altura do menisco (y), 1–4 mm de nível
    hip = node(nt, "ShaderNodeMapRange", inputs={"From Min": nivel-0.00015, "From Max": nivel+0.00015, "To Min": 1.0, "To Max": 0.0}, clamp=True)
    link(nt, sep3, "Y", hip, "Value")
    pus = node(nt, "ShaderNodeBsdfPrincipled", inputs={"Base Color": (0.92, 0.90, 0.80, 1), "Roughness": 0.5, "Subsurface Weight": 0.8})
    mx_h = node(nt, "ShaderNodeMixShader"); link(nt, hip, "Result", mx_h, "Fac"); link(nt, shader_i, "Shader", mx_h, 1); link(nt, pus, "BSDF", mx_h, 2); shader_i = mx_h
link(nt, shader_i, "Shader", out, "Surface")

# ---------------- material: CRISTALINO (preto normal; catarata → cinza/branco com leucocoria) ----------------
m, nt, out = new_mat("M_Cristalino"); lente.data.materials.append(m)
if A.sinal == "catarata":
    g = random.uniform(0.45, 0.9)     # maturidade: 0.45 (nuclear amarelada) → 0.9 (madura branca)
    cor = (g, g*random.uniform(0.85, 1.0), g*random.uniform(0.6, 0.95), 1)
    b = node(nt, "ShaderNodeBsdfPrincipled", inputs={"Base Color": cor, "Roughness": 0.5, "Subsurface Weight": 1.0, "Subsurface Radius": (0.002,0.0015,0.001)})
    globo["catarata_grau"] = g
else:
    b = node(nt, "ShaderNodeBsdfPrincipled", inputs={"Base Color": (0.01, 0.003, 0.002, 1), "Roughness": 0.2})
link(nt, b, "BSDF", out, "Surface")

# ---------------- pele / pálpebras (protótipo simples: bloco de pele com fenda elíptica) ----------------
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, 0, -6.0*MM), segments=128, ring_count=64)
pele = bpy.context.active_object; pele.name = "Pele"; pele.scale = (45*MM, 40*MM, 19*MM)
bpy.ops.object.shade_smooth()
FENDA_L = random.uniform(13.0, 15.5)*MM       # semi-largura da fenda palpebral (~28–31 mm)
FENDA_H = random.uniform(4.5, 5.5)*MM         # semi-altura (~9–11 mm)
PTOSE = random.uniform(1.5, 3.5)*MM if A.sinal == "ptose" else 0.0
if A.sinal == "proptose": FENDA_H *= 1.25
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, -PTOSE/2, 12*MM), segments=96, ring_count=48)
cut = bpy.context.active_object; cut.name = "Fenda"; cut.scale = (FENDA_L, FENDA_H - PTOSE/2, 20*MM); cut.hide_render = True
bo = pele.modifiers.new("fenda", "BOOLEAN"); bo.operation = "DIFFERENCE"; bo.object = cut; bo.solver = "EXACT"
if A.sinal == "calazio":   # bolinha na pálpebra superior
    bpy.ops.mesh.primitive_uv_sphere_add(radius=random.uniform(2.0, 4.0)*MM, location=(random.uniform(-6, 6)*MM, (FENDA_H/MM + 4.0)*MM, 11.5*MM))
    cal = bpy.context.active_object; cal.name = "Calazio"; bpy.ops.object.shade_smooth()
m, nt, out = new_mat("M_Pele")
tcp = node(nt, "ShaderNodeTexCoord")
TONS_PELE = [(0.85,0.62,0.50), (0.72,0.48,0.36), (0.55,0.35,0.25), (0.40,0.25,0.17), (0.25,0.15,0.10)]   # Fitzpatrick I–VI aprox.
tom = random.choice(TONS_PELE)
nzp = node(nt, "ShaderNodeTexNoise", inputs={"Scale": 800.0, "Detail": 8.0, "Roughness": 0.65}); link(nt, tcp, "Object", nzp, "Vector")
rp = node(nt, "ShaderNodeValToRGB"); link(nt, nzp, "Fac", rp, "Fac")
rp.color_ramp.elements[0].color = tuple(c*0.85 for c in tom)+(1,); rp.color_ramp.elements[1].color = tuple(min(1,c*1.1) for c in tom)+(1,)
bp = node(nt, "ShaderNodeBsdfPrincipled", inputs={"Roughness": 0.55, "Subsurface Weight": 0.6, "Subsurface Radius": (0.0036, 0.0014, 0.0007), "Specular IOR Level": 0.35})
link(nt, rp, "Color", bp, "Base Color")
bump = node(nt, "ShaderNodeBump", inputs={"Strength": 0.15, "Distance": 0.0002}); link(nt, nzp, "Fac", bump, "Height"); link(nt, bump, "Normal", bp, "Normal")
link(nt, bp, "BSDF", out, "Surface")
pele.data.materials.append(m)
if A.sinal == "calazio": cal.data.materials.append(m)
globo["tom_pele"] = str(tom)

# ---------------- iluminação: HDRI + flash opcional ----------------
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
wn = w.node_tree; bg = wn.nodes["Background"]
if A.hdri and os.path.exists(A.hdri):
    env = wn.nodes.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(A.hdri)
    mp = wn.nodes.new("ShaderNodeMapping"); mp.inputs["Rotation"].default_value = (0, 0, random.uniform(0, 2*math.pi))
    tcw = wn.nodes.new("ShaderNodeTexCoord"); wn.links.new(tcw.outputs["Generated"], mp.inputs["Vector"]); wn.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    wn.links.new(env.outputs["Color"], bg.inputs["Color"]); bg.inputs["Strength"].default_value = random.uniform(0.6, 1.6)
else:
    bg.inputs["Color"].default_value = (0.4, 0.4, 0.45, 1); bg.inputs["Strength"].default_value = 1.0

# ---------------- câmera (celular a 5–20 cm, DOF) ----------------
DIST = random.uniform(55, 120)*MM       # 5,5–12 cm: macro de celular
bpy.ops.object.camera_add(location=(random.uniform(-15,15)*MM, random.uniform(-10,10)*MM, DIST))
cam = bpy.context.active_object; sc.camera = cam
# ÓTICA FÍSICA de celular: sensor ~7 mm e distância focal FÍSICA 5,5–9 mm (≈26–43 mm equiv.). Com lens=26 mm num sensor
# de 7 mm a abertura física (lens/f) fica ~15 mm e a DOF cai para <1 mm — erro clássico. Assim a DOF fica em ±3–5 mm a 8 cm.
cam.data.sensor_width = 7.0; cam.data.sensor_fit = "HORIZONTAL"
cam.data.lens = random.uniform(5.5, 9.0)
cam.data.clip_start = 0.005
cam.data.dof.use_dof = True; cam.data.dof.focus_distance = DIST - 10*MM     # foco no plano da íris (z≈10 mm)
cam.data.dof.aperture_fstop = random.uniform(1.7, 2.4)
# ATENÇÃO: Track To / to_track_quat usam o +Z do mundo como "up" → degenera quando a câmera olha ao longo de Z.
# Construímos a rotação à mão: -Z da câmera aponta para o alvo, +Y da câmera ≈ +Y do mundo (topo da imagem = superior).
import mathutils
alvo_loc = mathutils.Vector((0, 0, (13+PROPTOSE)*MM))
zc = (cam.location - alvo_loc).normalized()                       # eixo Z da câmera aponta para trás
xc = mathutils.Vector((0, 1, 0)).cross(zc).normalized()           # direita
yc = zc.cross(xc)                                                 # cima
cam.rotation_euler = mathutils.Matrix((xc, yc, zc)).transposed().to_euler()
# enquadramento resultante: largura do quadro = DIST*sensor/lens ≈ 43–150 mm → o olho (≈30 mm) ocupa 20–70% do quadro,
# como numa foto real antes do crop. Recortar depois pelo bbox da máscara se quiser o olho centralizado.
# balanço de branco imperfeito (AWB de celular): temperatura 4300–6800 K
try:
    sc.view_settings.use_white_balance = True
    sc.view_settings.white_balance_temperature = random.uniform(4300, 6800)
    sc.view_settings.white_balance_tint = random.uniform(-5, 5)
except Exception as e:
    print("sem white balance na API:", e)
sc.view_settings.exposure = random.uniform(-0.5, 0.5)   # auto-exposição variável

if A.flash > 0:   # flash do celular: ponto pequeno junto à lente (~8 mm), coaxial → reflexo de Purkinje e leucocoria
    bpy.ops.object.light_add(type="POINT", location=(cam.location.x + 8*MM, cam.location.y + 4*MM, cam.location.z))
    fl = bpy.context.active_object; fl.data.energy = A.flash * (DIST/(120*MM))**2; fl.data.shadow_soft_size = 2*MM; fl.data.color = (1.0, 0.95, 0.9)
    globo["flash_W"] = fl.data.energy

# ---------------- render ----------------
globo["sinal"] = A.sinal; globo["pupila_mm"] = R_PUPILA*2; globo["seed"] = A.seed
print("PARAMS", {k: globo[k] for k in globo.keys()})
bpy.ops.render.render(write_still=True)
print("RENDER OK ->", A.out)
