"""
Teste headless: cabeça MPFB completa (pele CC0 + olhos procedurais + cílios + sobrancelhas) e close-up do olho direito.
Requer: MPFB instalado e makehuman_system_assets_cc0.zip descompactado em
~/Library/Application Support/Blender/5.2/extensions/.user/blender_org/mpfb/data/
Uso: Blender -b -P mpfb_closeup.py -- --out img.png --hdri x.hdr --seed 1
"""
import bpy, sys, os, random, argparse, math, mathutils, traceback
argv = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser(); ap.add_argument("--out", default="/tmp/mpfb.png"); ap.add_argument("--hdri", default="")
ap.add_argument("--seed", type=int, default=0); ap.add_argument("--res", type=int, default=640); ap.add_argument("--samples", type=int, default=64)
A = ap.parse_args(argv); random.seed(A.seed)
bpy.ops.wm.read_factory_settings(use_empty=True)
from bl_ext.blender_org.mpfb.services.humanservice import HumanService
from bl_ext.blender_org.mpfb.services.assetservice import AssetService
from bl_ext.blender_org.mpfb.services.locationservice import LocationService
UD = LocationService.get_user_data()

# --- humano com macros sorteados ---
etnia = random.choice([{"african":1.0,"asian":0.0,"caucasian":0.0},{"african":0.0,"asian":1.0,"caucasian":0.0},{"african":0.0,"asian":0.0,"caucasian":1.0},{"african":0.5,"asian":0.1,"caucasian":0.4}])
macros = {"gender": random.random(), "age": random.uniform(0.2, 0.9), "muscle": 0.5, "weight": random.uniform(0.3, 0.7),
          "proportions": 0.5, "height": 0.5, "cupsize": 0.5, "firmness": 0.5, "race": etnia}
human = HumanService.create_human(macro_detail_dict=macros)
print("HUMAN", human.name, len(human.data.vertices))

# --- assets do pacote CC0 ---
def asset(sub, frag):
    p = AssetService.find_asset_absolute_path(frag, sub)
    if not p:  # fallback: procurar no disco
        for root, _, files in os.walk(os.path.join(UD, sub)):
            for f in files:
                if f.endswith(frag.split("/")[-1]): return os.path.join(root, f)
    return p
eyes_p = asset("eyes", "high-poly/high-poly.mhclo"); print("EYES MHCLO", eyes_p)
eyes = HumanService.add_mhclo_asset(eyes_p, human, asset_type="Eyes", material_type="PROCEDURAL_EYES")
print("EYES OBJ", eyes.name, len(eyes.data.vertices), [m.name for m in eyes.data.materials])
lash = asset("eyelashes", "eyelashes01/eyelashes01.mhclo"); brow = asset("eyebrows", "eyebrow001/eyebrow001.mhclo")
if lash: HumanService.add_mhclo_asset(lash, human, asset_type="Eyelashes")
if brow: HumanService.add_mhclo_asset(brow, human, asset_type="Eyebrows")
skins = sorted(d for d in os.listdir(os.path.join(UD, "skins")) if not d.startswith("toon") and "special" not in d)
skin = random.choice(skins); mh = os.path.join(UD, "skins", skin, skin + ".mhmat")
HumanService.set_character_skin(mh, human, skin_type="ENHANCED_SSS"); print("SKIN", skin)

# --- parâmetros do olho procedural (grupo EnhancedEye) ---
iris_cores = {"castanho": ((0.30,0.17,0.08,1),(0.12,0.07,0.03,1)), "mel": ((0.55,0.35,0.12,1),(0.25,0.14,0.05,1)),
              "verde": ((0.30,0.45,0.20,1),(0.12,0.20,0.08,1)), "azul": ((0.18,0.49,0.91,1),(0.11,0.16,0.41,1)), "cinza": ((0.45,0.50,0.55,1),(0.20,0.22,0.25,1))}
nome, (c1, c2) = random.choice(list(iris_cores.items()))
pupila = random.uniform(0.2, 0.45)
for m in eyes.data.materials:
    for n in m.node_tree.nodes:
        if n.type == "GROUP" and n.node_tree and "EnhancedEye" in n.node_tree.name:
            n.inputs["IrisMajorColor"].default_value = c1; n.inputs["IrisMinorColor"].default_value = c2
            n.inputs["PupilSize"].default_value = pupila; n.inputs["OuterLayerIOR"].default_value = 1.376
            print("EYE GROUP SET", m.name, nome, round(pupila, 2))

# --- centro do olho direito: usar a malha AVALIADA do objeto de olhos (shape keys dos macros aplicados).
# ATENÇÃO: human.data.vertices[i].co é a base mesh SEM os targets (o humano pode ter outra altura) e os
# "joint cubes" (joint-r-eye) são helpers mascarados → não usar. Olho direito do personagem = x < 0 (ele olha para -Y).
bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
ev = eyes.evaluated_get(dg)
pts = [ev.matrix_world @ v.co for v in ev.data.vertices]
pts_d = [p for p in pts if p.x < 0]
centro = sum(pts_d, mathutils.Vector()) / len(pts_d)
print("CENTRO OLHO D (m)", tuple(round(c, 4) for c in centro), "| n verts olho D", len(pts_d), "| altura humano", round(human.evaluated_get(dg).dimensions.z, 3))

# --- câmera macro: 8 cm à frente (MPFB olha para -Y), lente física 8 mm, f/2 ---
sc = bpy.context.scene
DIST = random.uniform(0.06, 0.11)
cam_loc = centro + mathutils.Vector((random.uniform(-0.015, 0.015), -DIST, random.uniform(-0.01, 0.01)))
bpy.ops.object.camera_add(location=cam_loc); cam = bpy.context.active_object; sc.camera = cam
alvo = centro + mathutils.Vector((0, -0.012, 0))       # ápice corneano ≈ 12 mm à frente do centro
zc = (cam.location - alvo).normalized(); xc = mathutils.Vector((0,0,1)).cross(zc).normalized(); yc = zc.cross(xc)
cam.rotation_euler = mathutils.Matrix((xc, yc, zc)).transposed().to_euler()
cam.data.sensor_width = 7.0; cam.data.lens = random.uniform(6.0, 9.0); cam.data.clip_start = 0.005
cam.data.dof.use_dof = True; cam.data.dof.focus_distance = (alvo - cam.location).length; cam.data.dof.aperture_fstop = random.uniform(1.7, 2.4)

# --- mundo / render ---
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; bg = w.node_tree.nodes["Background"]
if A.hdri and os.path.exists(A.hdri):
    env = w.node_tree.nodes.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(A.hdri)
    mp = w.node_tree.nodes.new("ShaderNodeMapping"); mp.inputs["Rotation"].default_value = (0, 0, random.uniform(0, 6.28))
    tc = w.node_tree.nodes.new("ShaderNodeTexCoord"); w.node_tree.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    w.node_tree.links.new(mp.outputs["Vector"], env.inputs["Vector"]); w.node_tree.links.new(env.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 1.0
sc.render.engine = "CYCLES"; sc.cycles.samples = A.samples; sc.cycles.use_denoising = True
sc.cycles.transmission_bounces = 8; sc.cycles.transparent_max_bounces = 16
prefs = bpy.context.preferences.addons["cycles"].preferences; prefs.compute_device_type = "METAL"; prefs.get_devices()
for d in prefs.devices: d.use = (d.type == "METAL")
sc.cycles.device = "GPU"
sc.render.resolution_x = sc.render.resolution_y = A.res; sc.render.filepath = A.out
try:
    sc.view_settings.use_white_balance = True; sc.view_settings.white_balance_temperature = random.uniform(4500, 6500)
except Exception: pass
print("PARAMS", {"skin": skin, "iris": nome, "pupila": round(pupila, 2), "macros": macros, "dist_cm": round(DIST*100, 1)})
bpy.ops.render.render(write_still=True); print("RENDER OK", A.out)
