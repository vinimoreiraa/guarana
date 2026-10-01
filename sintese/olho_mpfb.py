"""Olho sintetico v3: cabeca MPFB (pele, palpebras, cilios, sobrancelhas; CC0) + globo proprio com os sinais (sintese/olho.py).
Uso: /Applications/Blender.app/Contents/MacOS/Blender -b -P sintese/olho_mpfb.py -- --n 20 --out sintese/render/mpfb1/s0 --seed 0 [--size 512] [--samples 48] [--por-humano 8] [--mostruario] [--engine cycles|eevee]
Cada humano (macros, pele, olhos) e reutilizado por --por-humano imagens; sinais, olhar, camera, luz mudam a cada imagem.
"""
import bpy, sys, os, math, random, json, csv, traceback
from mathutils import Vector, Matrix
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import olho as O
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d): return type(d)(argv[argv.index(k) + 1]) if k in argv else d
N = arg("--n", 4); OUT = arg("--out", "sintese/render/mpfb"); SEED = arg("--seed", 0); SIZE = arg("--size", 512); SAMPLES = arg("--samples", 48); POR_HUMANO = arg("--por-humano", 8)
ENGINE = arg("--engine", "cycles"); MOSTRUARIO = "--mostruario" in argv; FORCAR = arg("--forcar", "")
os.makedirs(OUT, exist_ok=True)
from bl_ext.blender_org.mpfb.services.humanservice import HumanService
from bl_ext.blender_org.mpfb.services.assetservice import AssetService
from bl_ext.blender_org.mpfb.services.locationservice import LocationService
UD = LocationService.get_user_data(); MM = 0.001

def asset(sub, frag):
    p = AssetService.find_asset_absolute_path(frag, sub)
    if not p:
        for root, _, files in os.walk(os.path.join(UD, sub)):
            for f in files:
                if f.endswith(frag.split("/")[-1]): return os.path.join(root, f)
    return p

def ajusta_esfera(pts):
    """ajuste algebrico de esfera (minimos quadrados) e refino com os pontos a ate 1,5 mm da superficie: o globo do MPFB
    tem iris/cornea/interior que puxam o centroide para a frente."""
    import numpy as np
    P = np.array([[p.x, p.y, p.z] for p in pts]); sel = np.ones(len(P), bool)
    for _ in range(4):
        Q = P[sel]; A = np.c_[2 * Q, np.ones(len(Q))]; b = (Q ** 2).sum(1); x = np.linalg.lstsq(A, b, rcond=None)[0]
        c = x[:3]; r = math.sqrt(max(x[3] + (c ** 2).sum(), 1e-12)); d = np.abs(np.linalg.norm(P - c, axis=1) - r); sel = d < 1.5 * MM
        if sel.sum() < 30: break
    print(f"ESFERA centro {[round(v, 4) for v in c]} raio {r * 1000:.2f} mm inliers {int(sel.sum())}/{len(P)}", flush=True)
    return Vector(c), float(r)

def novo_humano(rng):
    """cabeca MPFB com macros sorteados; devolve (human, eyes, centro do olho direito, raio do olho, skin)"""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    etnia = rng.choice([{"african": 1.0, "asian": 0.0, "caucasian": 0.0}, {"african": 0.0, "asian": 1.0, "caucasian": 0.0}, {"african": 0.0, "asian": 0.0, "caucasian": 1.0},
                        {"african": 0.5, "asian": 0.1, "caucasian": 0.4}, {"african": 0.3, "asian": 0.4, "caucasian": 0.3}, {"african": 0.7, "asian": 0.0, "caucasian": 0.3}])
    macros = {"gender": rng.random(), "age": rng.uniform(0.15, 0.95), "muscle": 0.5, "weight": rng.uniform(0.3, 0.75), "proportions": rng.uniform(0.3, 0.7), "height": 0.5, "cupsize": 0.5, "firmness": 0.5, "race": etnia}
    human = HumanService.create_human(macro_detail_dict=macros)
    eyes = HumanService.add_mhclo_asset(asset("eyes", "high-poly/high-poly.mhclo"), human, asset_type="Eyes", material_type="PROCEDURAL_EYES")
    lash = asset("eyelashes", "eyelashes01/eyelashes01.mhclo"); brow = asset("eyebrows", "eyebrow001/eyebrow001.mhclo")
    if lash: HumanService.add_mhclo_asset(lash, human, asset_type="Eyelashes")
    if brow: HumanService.add_mhclo_asset(brow, human, asset_type="Eyebrows")
    skins = sorted(d for d in os.listdir(os.path.join(UD, "skins")) if not d.startswith("toon") and "special" not in d)
    skin = rng.choice(skins); HumanService.set_character_skin(os.path.join(UD, "skins", skin, skin + ".mhmat"), human, skin_type="ENHANCED_SSS")
    # olho esquerdo do MPFB fica; o direito (x<0) sai da malha e entra o nosso globo
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); ev = eyes.evaluated_get(dg)
    pts = [ev.matrix_world @ v.co for v in ev.data.vertices]; pts_d = [p for p in pts if p.x < 0]
    centro, raio = ajusta_esfera(pts_d)
    import bmesh
    bm = bmesh.new(); bm.from_mesh(eyes.data); mw = eyes.matrix_world
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if (mw @ v.co).x < 0], context="VERTS"); bm.to_mesh(eyes.data); bm.free()
    # cabeca inteira e pesada demais para renderizar: esconde o que nao e cabeca? (manter; a camera so ve o olho)
    return human, eyes, centro, raio, skin, macros

def cena_luz_camera(P, centro, rng):
    sc = bpy.context.scene
    if ENGINE == "cycles":
        sc.render.engine = "CYCLES"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True; sc.cycles.transmission_bounces = 8; sc.cycles.transparent_max_bounces = 16
        prefs = bpy.context.preferences.addons["cycles"].preferences; prefs.compute_device_type = "METAL"; prefs.get_devices()
        for d in prefs.devices: d.use = (d.type == "METAL")
        sc.cycles.device = "GPU"
    else:
        sc.render.engine = "BLENDER_EEVEE"; sc.eevee.taa_render_samples = SAMPLES
        for attr, val in (("use_raytracing", True), ("use_shadows", True)):
            if hasattr(sc.eevee, attr): setattr(sc.eevee, attr, val)
    sc.render.resolution_x = sc.render.resolution_y = SIZE; sc.render.image_settings.file_format = "JPEG"; sc.render.image_settings.quality = 90
    sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Base Contrast"; sc.view_settings.exposure = P["exposicao"] + 0.2
    try: sc.view_settings.use_white_balance = True; sc.view_settings.white_balance_temperature = rng.uniform(4300, 6800)
    except Exception: pass
    # mundo
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True; bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (*P["luz_cor"], 1); bg.inputs[1].default_value = P["luz_mundo"] * 1.4
    if O.HDRIS and P["usa_hdri"]:
        env = w.node_tree.nodes.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(O.HDRIS[P["hdri_i"] % len(O.HDRIS)])
        mp = w.node_tree.nodes.new("ShaderNodeMapping"); tc = w.node_tree.nodes.new("ShaderNodeTexCoord"); mp.inputs["Rotation"].default_value = (0, 0, P["hdri_rot"])
        w.node_tree.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); w.node_tree.links.new(mp.outputs["Vector"], env.inputs["Vector"]); w.node_tree.links.new(env.outputs["Color"], bg.inputs["Color"])
        bg.inputs[1].default_value = P["luz_mundo"] * 1.2
    # luz de area (janela / lampada) na frente-cima do rosto (MPFB olha para -Y)
    bpy.ops.object.light_add(type="AREA", location=centro + Vector((P["luz_x"] * MM * 1.5, -0.35, 0.25 + P["luz_y"] * MM))); la = bpy.context.active_object
    la.data.energy = P["luz_area"] * 6; la.data.size = 0.5; la.data.color = P["luz_cor"]; la.rotation_euler = (math.radians(55), 0, 0)
    # camera fisica de celular: sensor 7 mm, lente 5.5-9 mm, f/1.7-2.4, 6-11 cm, foco na cornea
    DIST = rng.uniform(0.035, 0.075); apice = centro + Vector((0, -12 * MM, 0))
    loc = apice + Vector((rng.uniform(-0.015, 0.015), -DIST, rng.uniform(-0.008, 0.012)))
    bpy.ops.object.camera_add(location=loc); cam = bpy.context.active_object; sc.camera = cam
    alvo = apice + Vector((P["mira_x"] * MM, 0, P["mira_y"] * MM)); fwd = (alvo - loc).normalized(); right = fwd.cross(Vector((0, 0, 1))).normalized(); upv = right.cross(fwd).normalized()
    cam.matrix_world = Matrix.Translation(loc) @ Matrix((right, upv, -fwd)).transposed().to_4x4() @ Matrix.Rotation(math.radians(P["rolagem"]), 4, "Z")
    cam.data.sensor_width = 7.0; cam.data.sensor_fit = "HORIZONTAL"; cam.data.lens = rng.uniform(7.0, 11.0); cam.data.clip_start = 0.004
    cam.data.dof.use_dof = True; cam.data.dof.focus_distance = (alvo - loc).length; cam.data.dof.aperture_fstop = rng.uniform(1.7, 2.4)
    if P["flash"]:
        bpy.ops.object.light_add(type="POINT", location=loc + right * 0.008); fl = bpy.context.active_object; fl.data.energy = rng.uniform(0.8, 2.5) * (DIST / 0.12) ** 2; fl.data.shadow_soft_size = 0.002; fl.data.color = (1, 0.95, 0.9)
    return dict(dist_cm=round(DIST * 100, 1), lente=round(cam.data.lens, 1), fstop=round(cam.data.dof.aperture_fstop, 2))

def render_mascara(caminho_png):
    """Segundo render rapido com material de sobreposicao: cor = f(indice do objeto) via Object Info.
    R = fenda (globo/cornea/hipopio, indice 1) | G = iris (2) | B = lesao/asa (3); resto preto. Sem luz, sem mundo."""
    sc = bpy.context.scene; vl = bpy.context.view_layer
    m = bpy.data.materials.new("override_mask"); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Strength"].default_value = 1.0
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    def eq(v):
        a = nt.nodes.new("ShaderNodeMath"); a.operation = "COMPARE"; a.inputs[1].default_value = v; a.inputs[2].default_value = 0.1; nt.links.new(oi.outputs["Object Index"], a.inputs[0]); return a.outputs[0]
    comb = nt.nodes.new("ShaderNodeCombineColor"); nt.links.new(eq(1), comb.inputs[0]); nt.links.new(eq(2), comb.inputs[1]); nt.links.new(eq(3), comb.inputs[2])
    nt.links.new(comb.outputs[0], em.inputs["Color"]); nt.links.new(em.outputs[0], out.inputs["Surface"])
    vl.material_override = m
    old = (sc.render.engine, getattr(sc.cycles, "samples", 0), sc.cycles.use_denoising, sc.view_settings.view_transform, sc.view_settings.exposure, sc.render.image_settings.file_format, sc.render.filepath, sc.world)
    sc.render.engine = "CYCLES"; sc.cycles.samples = 4; sc.cycles.use_denoising = False; sc.view_settings.view_transform = "Standard"; sc.view_settings.exposure = 0
    sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGB"; sc.render.filepath = caminho_png
    wb = bpy.data.worlds.new("preto"); wb.use_nodes = True; wb.node_tree.nodes["Background"].inputs[1].default_value = 0.0; sc.world = wb
    for o in bpy.data.objects:
        if o.type == "LIGHT": o.hide_render = True
    bpy.ops.render.render(write_still=True)
    for o in bpy.data.objects:
        if o.type == "LIGHT": o.hide_render = False
    vl.material_override = None
    sc.render.engine, sc.cycles.samples, sc.cycles.use_denoising, sc.view_settings.view_transform, sc.view_settings.exposure, sc.render.image_settings.file_format, sc.render.filepath, sc.world = old

def main():
    rng = random.Random(SEED); rows = []
    forced = [None, "hiperemia", "conjuntivite", "ictericia", "pterigio", "pinguecula", "hemorragia_subconjuntival", "catarata_leucocoria", "opacidade_corneana", "uveite", "alteracao_palpebral", "ceratite"] if MOSTRUARIO else ([FORCAR] * N if FORCAR else [None] * N)
    humano = None
    for k, f in enumerate(forced):
        if humano is None or k % POR_HUMANO == 0:
            human, eyes, centro, raio, skin, macros = novo_humano(rng); humano = (human, centro, raio)
            print(f"HUMANO {k // POR_HUMANO}: pele {skin} raio_olho {raio * 1000:.2f} mm centro {[round(c, 4) for c in centro]}", flush=True)
        else:
            # limpa o que e da imagem anterior (pivo do olho e filhos, luzes, camera, mundo)
            for o in list(bpy.data.objects):
                if o.name.startswith(("pivo", "globo", "cornea", "iris", "hipopio", "pterigio", "Area", "Point", "Camera")): bpy.data.objects.remove(o, do_unlink=True)
        P = O.sample(rng, force=f); P["pterigio_lado"] = 1   # olho direito: nasal = +x
        P["calazio"] = 0; P["ptose"] = 0                      # palpebra vem do MPFB (calazio/ptose ainda nao modelados aqui)
        if P["sinal"] == "alteracao_palpebral": P["sinal"] = "normal"; P["alteracao_palpebral"] = 0
        escala = (raio + 0.15 * MM) / O.R_GLOBO
        # nosso olho olha para +Z local; MPFB olha para -Y: rotacao X +90 leva +Z em -Y
        O.build_eye(P, centro, escala=escala, rot=(math.radians(90), 0, 0))
        cam_info = cena_luz_camera(P, centro, rng)
        for o in bpy.data.objects:
            if o.name.startswith(("globo", "cornea", "hipopio")): o.pass_index = 1
            elif o.name.startswith("iris"): o.pass_index = 2
            elif o.name.startswith("pterigio"): o.pass_index = 3
        name = f"m{SEED:03d}_{k:04d}_{P['sinal']}"; path = os.path.abspath(os.path.join(OUT, name + ".jpg")); bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        render_mascara(path[:-4] + "_mask.png")
        y = O.labels_of(P); rows.append({"file": name + ".jpg", "subject_id": f"m{SEED:03d}_h{k // POR_HUMANO}", "source": "sintese_mpfb", "domain": "synthetic", **y, "sinal": P["sinal"],
                                           "params": json.dumps({"pele": skin, "macros": macros, **cam_info, **{k2: (list(v) if isinstance(v, tuple) else v) for k2, v in P.items() if k2 in ("hiperemia", "ictericia", "pterigio_mm", "pupila_r", "hipopio", "flash", "usa_hdri", "hdri_i")}})})
        print("render", name, flush=True)
        csvp = os.path.join(OUT, "labels.csv"); new = not os.path.exists(csvp)
        with open(csvp, "a", newline="") as fh:   # incremental: sobrevive a interrupcao
            w = csv.DictWriter(fh, fieldnames=["file", "subject_id", "source", "domain", *O.LABELS, "sinal", "params"])
            if new: w.writeheader()
            w.writerow(rows[-1])
try: main()
except Exception: traceback.print_exc(); sys.exit(1)
