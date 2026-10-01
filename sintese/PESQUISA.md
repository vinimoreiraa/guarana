# Síntese de dados com Blender — pesquisa, recursos abertos e receitas

*Projeto Guaraná — olho externo fotografado com celular. Pesquisa feita em 2026-09-30 nesta máquina (Mac, Apple M5 Pro).*

Este documento reúne: (1) o que foi verificado no ambiente local; (2) os recursos **abertos** (CC0/CC-BY/CC-BY-SA/GPL) que foram baixados para `sintese/assets/` e os que **não** dá para baixar sem login; (3) como usar o MPFB (MakeHuman Plugin For Blender) headless para ter cabeça, pálpebras e olhos; (4) a receita do olho paramétrico em Cycles, já **implementada e testada** em `sintese/scripts/olho_prototipo.py`; (5) como pintar cada sinal clínico de forma procedural, com parâmetros e faixas; (6) o que a literatura diz sobre sim-to-real para imagens de olho; (7) checagens e próximos passos.

---

## 0. Resumo executivo

- **Blender 5.2.0 LTS** roda headless em `/Applications/Blender.app/Contents/MacOS/Blender`, com **Cycles em GPU Metal** (Apple M5 Pro, 16 núcleos). Primeiro render compila kernels (~100 s); depois **~3 s por imagem** a 320² / 32 spp e **13 s a 1024² / 128 spp** (~280 img/h). Ver §1.
- **MPFB 2.0.17** instalado por linha de comando (`--online-mode --command extension install mpfb -e`) e o pacote `makehuman_system_assets_cc0` (281 MB) descompactado no diretório de dados dele. **Pipeline completo testado headless**: humano com macros sorteados + olhos procedurais (grupo `EnhancedEye`, 22 parâmetros) + cílios + sobrancelhas + pele SSS → close-up do olho em 16 s (`scripts/mpfb_closeup.py`, `saida_teste/mpfb_closeup_3.png`). Ver §3.
- **Baixado (~700 MB, tudo sem login)**: 14 HDRIs 2k do Poly Haven (CC0, 91 MB); 17 texturas de olho da Blender Foundation (CC0) + 10 macros de íris do Wikimedia (CC0/CC-BY/CC-BY-SA); 4 sets de pele CC0 (153 MB); pacote CC0 do MakeHuman com **globo ocular (córnea separada), 10 texturas de olho, cílios, sobrancelhas e 24 peles** (281 MB); **assets do UnityEyes2 sob MIT** (globo, retalho de pele periocular com texturas 2K de 5 sujeitos, cílios, menisco lacrimal); Z-Anatomy (CC BY-SA) e BodyParts3D (CC BY) como gabarito anatômico; 20 fotos de referência dos sinais. Licenças em §2 e nos `LICENCAS.md` de cada pasta.
- **Não abertos / exigem login**: Sketchfab, BlendSwap, BlenderKit, TurboSquid, CGTrader, Free3D; UnityEyes, SynthesEyes, NVGaze, RIT-Eyes e Face Synthetics **não liberam o modelo de olho** (só binários/datasets "para pesquisa"). Ver §2.4.
- **Receita mais promissora** (§4): globo paramétrico (esclera r=12 mm + córnea r=7,8 mm com Glass IOR 1,376 + íris procedural com pupila variável + cristalino) **dentro de uma cabeça MPFB** para pálpebras/pele reais, HDRI do Poly Haven + flash pontual coaxial, câmera 6–20 cm com DOF f/1,8–2,8; sinais pintados por máscaras em coordenadas de objeto (§5). O protótipo já produz os 12 sinais: `sintese/saida_teste/folha_contato_v3.png`.
- **Sim-to-real** (§6): misturar sintético com real ~1:1 (nunca >2:1), variar muito textura de esclera/pele/íris e iluminação, simular sensor de celular, e refinar renders com img2img/ControlNet a força 0,3–0,5. Sintético puro sempre deixa gap; poucas fotos reais no treino fecham a maior parte.

---

## 1. Ambiente verificado

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender
$B -b --python-expr "import bpy, sys; print(bpy.app.version_string, sys.version)"
# → 5.2.0 LTS, Python 3.13.13
```

| item | resultado |
|---|---|
| Engines | `CYCLES`, `BLENDER_EEVEE` (EEVEE Next), `BLENDER_WORKBENCH` |
| Cycles GPU | `prefs.compute_device_type = "METAL"` → `Apple M5 Pro (GPU - 16 cores)`; `scene.cycles.device = "GPU"` |
| 1º render | ~100 s (compilação dos kernels Metal, uma vez por versão) |
| Renders seguintes | ~3 s (320², 32 spp) e **13 s medidos a 1024², 128 spp** (denoise OIDN, 8 bounces de transmissão) → ~280 imagens/h por processo |
| Extensões por CLI | precisam de `--online-mode` para `sync`/`install` (senão "Online access required") |
| Add-ons já habilitados | `io_scene_gltf2`, `io_scene_fbx`, `cycles`, `bl_pkg` (gestor de extensões) |

Script de teste (12 sinais, HDRI, flash, DOF): `sintese/scripts/olho_prototipo.py` — uso (nota: existe também `sintese/olho.py` v2 e `sintese/render/`, criados em paralelo por outro processo durante esta pesquisa, com colunas de rótulo do treino; as receitas abaixo valem para ambos):

```bash
cd sintese
$B -b -P scripts/olho_prototipo.py -- --sinal pterigio --seed 3 --res 768 --samples 96 \
   --hdri assets/hdri/childrens_hospital_2k.hdr --flash 0.15 --out saida_teste/pterigio_3.png
```

Os parâmetros sorteados (pupila, tom de pele, grau do sinal, ápice do pterígio…) são impressos em `PARAMS {...}` e gravados como *custom properties* do objeto `Globo` — servem de rótulo.

---

## 2. Recursos abertos: o que foi baixado e o que não dá

### 2.1 HDRIs — Poly Haven (CC0) — `assets/hdri/` (91 MB)

API pública: `https://api.polyhaven.com/assets?t=hdris` (997 HDRIs; 301 *indoor*, 96 *studio*, 61 *night*) e `https://api.polyhaven.com/files/<id>` (precisa de header `User-Agent`, senão 403). Baixados 14 em 2k `.hdr`, escolhidos para cobrir os cenários de uma UBS/domicílio:

`childrens_hospital` (hospital, fluorescente) · `empty_play_room` · `bathroom` · `comfy_cafe` · `blinds` (janela lateral) · `small_empty_room_1` · `courtyard` (sol) · `braustuble_alley` (rua nublada) · `farmland_overcast` · `urban_alley_01` (sombra) · `brown_photostudio_02` · `cyclorama_hard_light` (luz dura ≈ flash) · `lebombo` (sol forte) · `kloofendal_48d_partly_cloudy_puresky`.

Licença CC0 (https://polyhaven.com/license). Tabela completa em `assets/hdri/LICENCAS.md`. Poly Haven **não tem texturas de pele nem olho** (as 863 texturas são materiais de superfície; o mais próximo é couro).

### 2.2 Texturas de olho, íris e pele — `assets/iris_texturas/` (77 MB) e `assets/pele/` (153 MB)

| pasta | conteúdo | licença | observações |
|---|---|---|---|
| `iris_texturas/blender_institute_eyes/` | as 17 texturas do arquivo da Blender Foundation (https://download.blender.org/archive/textures/eyes/): 7 íris (256 px: blue saturated, blue greyish detailed, brown saturated, green, hazel, redish) e 10 "olhos inteiros" 1024–2048 px (blue 01/02, blue bright, brown dark, green dark, grey dotted, yellow bright + 4 não-humanas: hyena, chicken, dragon, insect) | **CC0** — texto verificado em https://download.blender.org/archive/textures/ ("All textures are licensed as CC-0. Free to use anywhere, for any purpose.") | só mapa de cor; as íris são pequenas (256 px) — servem de base para o procedural, não como textura final |
| `iris_texturas/wikimedia_iris_macro/` | 10 fotos macro de íris humana em resolução original (4000–5472 px), metadados em `_wikimedia_meta.jsonl` | 1 CC0, 6 CC-BY, 3 CC-BY-SA (autor/URL por arquivo no `LICENCAS.md`) | para dataset redistribuível usar só CC0/CC-BY; CC-BY-SA pode "contaminar" renders derivados |
| `pele/texturecan_skin_0001/{1k,2k}` | única textura de pele humana do TextureCan: color, normal (GL/DX), roughness, height, AO, subsurface | **CC0 1.0** (https://www.texturecan.com/terms/) | tileável genérica, poucos poros; o site bloqueia `curl` sem User-Agent de navegador, mas não pede conta |
| `pele/cc0textures_sharetextures/human_skin_{1,3,4}` | 3 sets 4K (escura / média / clara) de cc0-textures.com | **CC0** (verificado por item; download direto de download.cc0-textures.com) | sets 2, 5, 6 existem e não foram baixados por orçamento |
| `refs/` (18 MB, 20 fotos) | referências visuais dos sinais (≤2 por condição): pterígio, pinguécula, hemorragia subconjuntival, icterícia, leucocoria, catarata, opacidade corneana, hipópio, ptose, calázio, proptose — curadas manualmente | CC0/CC-BY/CC-BY-SA por arquivo (Wikimedia Commons) | **só referência** para calibrar cor/forma dos shaders; não entram no produto. Ptose e pinguécula têm material fraco |

Não deu: **ambientCG** (CC0) não tem nada de pele/olho (q=skin devolve só Leather008); **rawcatalog.com** é espelho do mesmo skin_0001 e pede registro; **Poly Haven** não tem pele. Scans faciais de qualidade (3dscanstore, Texturing.xyz) são comerciais.

### 2.3 Modelos 3D de olho e cabeça — `assets/olho_modelos/` (355 MB)

Inventário completo, hashes, comandos de reprodução e tabela "investigado e não baixado" em `assets/olho_modelos/LICENCAS.md`. Resumo:

| pasta | fonte | licença | o que contém | utilidade |
|---|---|---|---|---|
| `makehuman/makehuman_system_assets_cc0.zip` (281 MB) | https://files.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip | **CC0 1.0** | **eyes/high-poly** (2 shells por olho: globo 276 v + **casca de córnea separada** 256 v, com UV) e low-poly; **10 texturas de olho 1024²** (blue, brown, brownlight, green, grey, ice…); eyelashes01–04 e eyebrows001–012 (cartões alfa); **24 texturas de pele 2048²** (jovem/meia-idade/idoso × africano/asiático/caucasiano × M/F) no UV da base mesh; dentes, língua, proxies | **é o pacote que dá olhos, cílios e sobrancelhas ao MPFB** (instalado nesta máquina, ver §3) |
| `makehuman/eyebrows01_cc0.zip`, `eyelashes01_cc0.zip` (15 MB) | Mindfront, files.makehumancommunity.org | **CC0** | 14 sobrancelhas e 5 cílios em **geometria de fios** (ex.: 789 fios × 12 v) | melhor que cartões alfa para macro |
| `makehuman/mpfb2_basemesh/base.obj` | github.com/makehumancommunity/mpfb2 | **CC0** (LICENSE.ASSETS.md) | base mesh hm08, 19 158 v, com UV | a mesma malha que o MPFB cria |
| `unityeyes2/` (28 MB) | https://github.com/alexanderdsmith/UnityEyes2 (LICENSE **MIT**, © 2018 Erroll Wood; © 2025 A. D. Smith, B. Muthumanickam) | **MIT** | `Assets/Eyeball/eyeball.obj` (626 v, **globo + casca de córnea**, UV, heightmap/glossmap 1024²), 5 texturas de olho 1024²; **`eye_region.obj` = retalho de pele periocular ~7 cm com UV** + `syntheseyes.obj` (8 variantes escaneadas f01–m05, mesma topologia = morph targets) + **texturas de pele 2048² cor + displacement 16 bit** de 5 sujeitos; cílios (malha + 4 alfas), menisco lacrimal ("wetness"), shaders HLSL (refração/paralaxe da íris), modelo PCA de forma | **os assets do SynthesEyes/UnityEyes, finalmente com licença aberta**; `.3ds` convertidos para `.obj` por script (Blender 5 não importa 3DS) |
| `z_anatomy/zanatomy_olho_orbita.{blend,glb}` (7 MB) | https://github.com/Z-Anatomy/Models-of-human-anatomy | **CC BY-SA 4.0** (+ atribuição BodyParts3D) | 77 malhas: córnea, esclera, íris, cristalino, câmaras, retina, vítreo, placas tarsais, glândula lacrimal, 6 músculos extraoculares, orbicular, pele das regiões orbital/frontal/nasal…; metros, coordenadas de corpo inteiro | gabarito anatômico de escala/posição (baixa resolução, sem texturas) |
| `bodyparts3d/obj/FJ*.obj` (48 arquivos, 32 MB) + `INDICE_FMA.tsv` | https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/partof_BP3D_4.0_obj_99.zip | **CC BY 4.0** (página 2025; cabeçalhos antigos CC BY-SA 2.1 JP) | córnea (~3 000 v), esclera (~20 000 v), íris, cristalino, câmara anterior, coroide, placas tarsais, levantador, aparelho lacrimal, músculos, pele de corpo inteiro (102 k v); mm | referência anatômica mais densa; sem UV |

**Modelo mais usável para o close-up realista**: globo `eyes/high-poly` do MakeHuman (CC0) ou `unityeyes2/Assets/Eyeball` (MIT) — ambos têm **casca de córnea separada** para receber `Glass IOR 1,376` e UV para as texturas de íris; pele periocular texturizada só existe no `unityeyes2/eye_region` (MIT, 5 sujeitos com displacement) ou na cabeça MPFB inteira (CC0, 24 peles).

Não abertos encontrados no caminho: `MikkoNurminenn/eye-face-asset` (rig MIT, mas cabeça e olho são assets BlenderKit royalty-free), `ElKalou/Procedural-Eyes-Tetxure` (sem licença), SynthesEyes dataset (CC BY-NC-SA, só imagens), NIH 3D Print Exchange (licenças por item, download direto, mas busca só client-side — passo manual descrito no `LICENCAS.md`).

### 2.4 O que exige login ou não é aberto (verificado)

| fonte | situação |
|---|---|
| Sketchfab | download só com conta (mesmo CC0); API precisa de token. Não usado. |
| BlendSwap | download exige conta (há modelos CC0 de olho: "Five Color Iris Textures" #21752, "Eye Texture Pack" #4952, "Procedural Anime Eye" #23319). Se quiser, criar conta e baixar manualmente — licença CC0 permite. |
| BlenderKit | precisa de conta/API key mesmo para assets gratuitos (há "Procedural Eye" de Oleg Sharonov e "Realistic Rigged Procedural Eye" de Joshua Jennings, licença Royalty Free — não CC0). |
| TurboSquid, CGTrader, Free3D | contas obrigatórias; licenças próprias (não CC). |
| UnityEyes (Wood 2016) | site original: só binário Windows/Linux, sem licença; **mas o repo UnityEyes2 (MIT, assinado por Erroll Wood) traz os assets** — baixados em `assets/olho_modelos/unityeyes2/`. |
| SynthesEyes (Wood 2015) | dataset 291 MB (DOI 10.17863/CAM.57942) é **CC BY-NC-SA 4.0** (só imagens); as malhas escaneadas f01–m05 estão no UnityEyes2 (MIT). |
| NVGaze (NVIDIA 2019) | página exige login; licença não verificada. |
| RIT-Eyes (2020, Blender) | 4 datasets em download direto, sem licença publicada; **pipeline Blender e assets não liberados**. |
| Face Synthetics (Microsoft 2021) | não comercial; assets não liberados. |
| OpenEDS (Meta) | acesso mediante pedido/termos. |
| Human Generator, Photorealistic Eye Generator, Andy Cuccaro | pagos. |

---

## 3. MPFB — cabeça, pálpebras e olhos abertos, headless

**O que é**: gerador de humanos open source dentro do Blender (sucessor do MakeHuman). Código GPL-3.0-or-later; malha-base e assets do MakeHuman são **CC0** (os renders são seus, sem restrição). Requer Blender ≥ 4.2. Fontes: https://extensions.blender.org/add-ons/mpfb/ · https://github.com/makehumancommunity/mpfb2 · docs https://static.makehumancommunity.org/mpfb/docs.html · exemplos de script https://github.com/makehumancommunity/mpfb2/blob/master/script_samples/index.md

**Instalação reproduzível (feita nesta máquina)**:

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender
$B -b --online-mode --command extension sync
$B -b --online-mode --command extension install mpfb -e
$B -b --command extension list | grep mpfb     # → mpfb [installed]: "MPFB"  (v2.0.17, build 20260722, 82 MB)
```

Instala em `~/Library/Application Support/Blender/5.2/extensions/blender_org/mpfb/`. Dados do usuário (asset packs) em `~/Library/Application Support/Blender/5.2/extensions/.user/blender_org/mpfb/data/`.

**O que vem embutido** (`mpfb/data/`): `3dobjs/base.obj` (malha hm08, 19.158 vértices, grupos `helper-l-eye`, `joint-l-eye`, `joint-l-lowerlid`, `helper-l-eyelashes-1/2`…), `targets/` (macro: gênero, idade, peso, proporções, etnia; e centenas de alvos de face, incluindo olhos/pálpebras), `textures/` (face, eyelids, lips… CC0), `node_trees/procedural_eyes.json`, `enhanced_skin.json`, `makeskin.json`, `rigs/`, `expressions/`.

**O que NÃO vem embutido**: os **globos oculares** (`eyes/`), cílios, sobrancelhas e peles-fotográficas — estão no pacote `makehuman_system_assets` (ver §2.3 / `assets/olho_modelos/LICENCAS.md`). Instalar: descompactar o zip dentro de `.../.user/blender_org/mpfb/data/` (fica `data/eyes/…`, `data/eyebrows/…`, `data/eyelashes/…`, `data/skins/…`), ou pela UI "Apply assets → Library settings → Load pack from zip".

**API headless (testado)** — o módulo chama-se `bl_ext.blender_org.mpfb`, não `mpfb`:

```python
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
from bl_ext.blender_org.mpfb.services.humanservice import HumanService
from bl_ext.blender_org.mpfb.services.assetservice import AssetService
from bl_ext.blender_org.mpfb.services.locationservice import LocationService

basemesh = HumanService.create_human(macro_detail_dict={
    "gender": 0.5, "age": 0.5, "muscle": 0.5, "weight": 0.5, "proportions": 0.5,
    "height": 0.5, "cupsize": 0.5, "firmness": 0.5,
    "race": {"asian": 0.33, "caucasian": 0.33, "african": 0.34}})
# → objeto "Human", 19.158 vértices, 1,66 m de altura; sem filhos até adicionar assets
```

Assinaturas exatas (lidas do código instalado, `services/humanservice.py`):

```python
HumanService.create_human(mask_helpers=True, detailed_helpers=True, extra_vertex_groups=True,
                          feet_on_ground=True, scale=0.1, macro_detail_dict=None)
HumanService.add_mhclo_asset(mhclo_file, basemesh, asset_type="Clothes", subdiv_levels=1,
                             material_type="MAKESKIN", alternative_materials=None, color_adjustments=None,
                             set_up_rigging=True, interpolate_weights=True, import_subrig=True, import_weights=True)
HumanService.set_character_skin(mhmat_file, basemesh, bodyproxy=None, skin_type="ENHANCED_SSS",
                                material_instances=True, slot_overrides=None)
AssetService.rescan_pack_metadata(); AssetService.get_pack_names()          # [] enquanto não houver pacote
AssetService.find_asset_absolute_path("eyes/high-poly/high-poly.mhclo", "eyes")   # após instalar o pacote
```

Sequência completa com o pacote instalado (adaptada de `script_samples/05_setting_skin.py` e `06_adding_basic_assets.py`):

```python
from bl_ext.blender_org.mpfb.services.assetservice import AssetService
from bl_ext.blender_org.mpfb.services.targetservice import TargetService
eyes = AssetService.find_asset_absolute_path("eyes/high-poly/high-poly.mhclo", "eyes")       # nome pode variar: listar com AssetService.get_asset_list("eyes")
olhos = HumanService.add_mhclo_asset(eyes, basemesh, asset_type="Eyes", material_type="PROCEDURAL_EYES")
HumanService.add_mhclo_asset(AssetService.find_asset_absolute_path("eyelashes/eyelashes01/eyelashes01.mhclo", "eyelashes"), basemesh, asset_type="Eyelashes")
HumanService.add_mhclo_asset(AssetService.find_asset_absolute_path("eyebrows/eyebrow001/eyebrow001.mhclo", "eyebrows"), basemesh, asset_type="Eyebrows")
HumanService.set_character_skin(AssetService.find_asset_absolute_path("skins/young_caucasian_female/young_caucasian_female.mhmat", "skins"), basemesh, skin_type="ENHANCED_SSS")
TargetService.load_target(basemesh, "<caminho>/eyes/r-eye-height2-decr.target", 0.6)        # exemplo: pálpebra mais fechada (ptose)
```

Confirmado no código (`services/humanservice.py:224`): o tipo de material de olhos usado pelo próprio MPFB é `"PROCEDURAL_EYES"` (`human_info["eyes_material_type"]`), e `materialservice.py:86` mapeia para o node tree `procedural_eyes`. Página oficial dos pacotes de assets (link embutido no plugin): http://static.makehumancommunity.org/assets/assetpacks.html

**Teste headless completo — funcionou** (`scripts/mpfb_closeup.py`, resultado em `saida_teste/mpfb_closeup_3.png` e `_8.png`): pacote CC0 descompactado em `.../.user/blender_org/mpfb/data/` (286 MB: `eyes/high-poly`, `eyelashes01–04`, `eyebrows001–012`, 24 `skins/*.mhmat`) → `create_human` com macros sorteados → `add_mhclo_asset(..., asset_type="Eyes", material_type="PROCEDURAL_EYES")` → cílios e sobrancelhas → `set_character_skin(..., skin_type="ENHANCED_SSS")` → cor da íris/pupila/IOR ajustados no grupo `EnhancedEye` → câmera macro no olho direito → Cycles GPU 640², 64 spp em **16 s** (1º render 108 s por compilação). O render mostra pele com SSS, sobrancelhas, cílios, íris procedural com refração e reflexo do ambiente.

```bash
$B -b -P scripts/mpfb_closeup.py -- --seed 3 --res 640 --samples 64 --hdri assets/hdri/empty_play_room_2k.hdr --out saida_teste/mpfb_closeup_3.png
```

Armadilhas encontradas (já tratadas no script):
- O módulo é `bl_ext.blender_org.mpfb` (não `mpfb`).
- **Não** usar `human.data.vertices[i].co` nem os grupos `joint-r-eye` para achar o olho: são coordenadas da base mesh **sem** os shape keys dos macros (um humano jovem tem outra altura) e os *joint cubes* são helpers mascarados. Usar a malha **avaliada** do objeto de olhos (`eyes.evaluated_get(depsgraph)`), olho direito = vértices com x < 0 (o personagem olha para −Y, +Z para cima).
- Câmera: colocar em `centro + (0, −DIST, 0)` olhando para `centro + (0, −0,012, 0)` (ápice corneano), "up" = +Z; para o olho encher o quadro usar DIST 5–7 cm ou lente 12–16 mm.
- `age` < 0,4 gera adolescentes/crianças; para o público-alvo usar `age` 0,4–0,95.
- Ptose/abertura: alvos em `data/targets/eyes/` (`r-eye-height2-decr` etc.) via `TargetService.load_target`; proptose: `*-eye-push1-out`; ou mover o objeto de olhos e aplicar expressões de pálpebra.

**Olho procedural do MPFB** (`node_trees/procedural_eyes.json`, grupo `EnhancedEye`, subgrupos `IrisMain`, `IrisBorder`, `IrisInnermostRing`, `RadiatingFromCoord`, `DistanceFromCenter`…). Entradas e defaults — todos randomizáveis via `NodeService.set_socket_default_values` ou direto em `node.inputs["..."].default_value`:

| entrada | default | uso na síntese |
|---|---|---|
| `PupilSize` | 0,30 | tamanho relativo da pupila (0,15–0,55 ≈ 2–8 mm) |
| `IrisMajorColor` / `IrisMinorColor` | azul (0,18; 0,49; 0,91) / (0,11; 0,16; 0,41) | cores da íris; sortear entre castanho-escuro, castanho, mel, verde, cinza, azul |
| `IrisSection1End`, `2End`, `3End`, `IrisSection4Color` | 0,10 / 0,80 / 0,85 / cinza-escuro | anéis (colarete, zona ciliar, anel limbar) |
| `IrisFeatureScale`, `IrisRadialMult`, `IrisClockwiseMult`, `IrisBumpStrength` | 16,9 / 0,3 / 3,5 / 0,3 | fibras radiais e criptas |
| `IrisToEyeWhiteRelation` | 0,39 | raio da íris relativo à esclera |
| `EyeWhiteColor` | branco | **icterícia** = puxar para (0,90; 0,78; 0,30); hiperemia = leve rosa |
| `OuterLayerIOR`, `OuterLayerTransmission`, `OuterLayerRoughness`, `OuterLayerAlpha` | 1,33 / 1,0 / 0,0 / 1,0 | camada externa (córnea) — subir IOR para 1,376 |
| `Clearcoat`, `Clearcoat Roughness`, `InnerLayerRoughness` | 0,4 / 0,0 / 0,05 | brilho úmido |
| `PupilColor` | preto | **catarata/leucocoria** = cinza/branco |

Limitações do olho MPFB para o nosso caso: a esclera é lisa (sem vasos) e a córnea é uma camada do mesmo mesh (não há bulbo corneano separado com refração geométrica). Por isso a receita recomendada (§4) usa a **cabeça do MPFB** (pele, pálpebras, cílios, expressões) e **substitui o globo** pelo olho paramétrico próprio, posicionado no centro do grupo `joint-l-eye`/`joint-r-eye`.

Como pegar o centro do olho na malha MPFB (para posicionar o globo próprio):

```python
import numpy as np
me = basemesh.data; gi = basemesh.vertex_groups["joint-r-eye"].index
pts = np.array([basemesh.matrix_world @ v.co for v in me.vertices if any(g.group == gi for g in v.groups)])
centro_olho_dir = pts.mean(axis=0)     # o "joint cube" é um cubinho centrado no centro do globo
```

Ptose/abertura palpebral no MPFB: usar alvos de face `eyes/…` (ex.: `l-eye-height2-decr|incr`, `r-eye-eyefold-*`, `*-eye-push1-in|out` = proptose/enoftalmia) via `TargetService.load_target(basemesh, caminho, weight)`, e as expressões (`expressions/`) para pálpebra caída/fechada parcial.

---

## 4. Receita do olho paramétrico em Cycles (implementada em `scripts/olho_prototipo.py`)

Unidades em metros (1 mm = 0,001). Eixo óptico = +Z, câmera em +Z olhando para −Z, nasal = −X (olho direito), superior = +Y.

### 4.1 Geometria (mm)

| peça | primitiva | valores | por quê |
|---|---|---|---|
| Esclera | UV sphere r=12 | centro na origem | globo Ø24 mm |
| Córnea | UV sphere r=7,8 centrada em z=+5,6 | ápice em z=13,4; intersecta a esclera em z≈10,2 → **limbo Ø≈12,6 mm**, protrusão 1,4 mm | raio corneano médio 7,8 mm; câmara anterior ≈3 mm |
| Íris | disco (círculo NGON) r=6,0 em z=9,9 | dentro do "vidro" da córnea | plano da íris ~3 mm atrás do ápice |
| Pupila | furo no shader da íris (não na malha) | r = 1,5–4,0 mm sorteado | permite miose/midríase sem remalhar |
| Cristalino | disco r=(pupila+0,3) em z=9,3 | material preto (normal) ou branco/cinza (catarata) | é o que se vê pela pupila |
| Pele/pálpebras (protótipo) | elipsoide 45×40×19 mm com boolean de um elipsoide 14×5×20 mm | fenda 28–31 × 9–11 mm | placeholder; usar a cabeça MPFB na versão final |

A esclera é *sólida*; a calota dela que ficaria sob a córnea (z > 10,15) é tornada **transparente no shader** (mix com `Transparent BSDF` por `Object.Z > 0,01015`) para não bloquear o raio que entra pela córnea. O **interior** do globo (faces traseiras, `Geometry.Backfacing`) recebe um `Diffuse` quase preto-avermelhado (0,02; 0,004; 0,002) = fundo de olho.

### 4.2 Materiais (nós, valores)

**Córnea** — `Glass BSDF` cor branca, `Roughness 0`, **`IOR 1,376`**. Opcional: `Principled` com `Transmission 1`, `IOR 1,376`, `Coat 1` (dá filme lacrimal). Cycles: `transmission_bounces ≥ 8`, `caustics_refractive = True`. Checagem: a íris vista pela córnea aparece **~13% maior** que o disco geométrico e o reflexo especular do HDRI/flash (1ª imagem de Purkinje) fica nítido e pequeno.

**Esclera/conjuntiva** — `Principled BSDF`: `Base Color` (0,86; 0,84; 0,80) ligeiramente quente, `Roughness 0,35`, `Coat Weight 1,0`/`Coat Roughness 0,05` (umidade), `Subsurface Weight 0,3`, `Subsurface Radius` (2; 1; 1 mm). Vasos:
1. `Texture Coordinate → Object` (centro do globo) → `Noise` (Scale 400, Detail 3) → `Vector Math MULTIPLY_ADD` (×0,0006) = coordenada distorcida.
2. Converter para polares: `phi = atan2(y, x)`, `theta = acos(z / 0,012)`; `Combine XYZ(phi, theta)` → `Vector Math MULTIPLY (1, 0,18, 1)` — a anisotropia em *theta* alonga as células no sentido **radial ao limbo**, como os vasos conjuntivais.
3. `Voronoi` (`Distance to Edge`, Scale 10–18 normal / 28–45 hiperemia) → `ColorRamp` (branco em 0 → preto em 0,005 normal / 0,016 hiperemia) → fator do `Mix Color` entre a cor-base e vermelho de vaso (0,55; 0,03; 0,02).
4. Máscara `Object.Z > 0` para os vasos existirem só na metade anterior.

**Íris** — coordenadas polares no disco: `r = length(Object)`, `ang = atan2(y, x)`; `Combine(ang×9, r×900)` → `Noise` (Detail 6, Roughness 0,7) → `ColorRamp` entre duas cores da íris (pares testados: castanho (0,30;0,17;0,08)/(0,55;0,35;0,15), azul-cinza (0,10;0,25;0,35)/(0,45;0,65;0,75), verde (0,20;0,30;0,15)/(0,55;0,60;0,30), castanho-escuro (0,12;0,08;0,05)/(0,35;0,22;0,12)). Anel limbar: `Map Range` de r∈[4,8; 6,0] mm → fator 1→0,35 multiplicando para preto. `Principled` `Roughness 0,6`, `Specular IOR Level 0,2`. **Pupila**: `r < R_PUPILA` → `Mix Shader` para `Transparent BSDF` (vê-se o cristalino atrás). Alternativa mais rica: substituir o `Noise` por foto de íris (§2.2) em UV polar.

**Pele (placeholder)** — `Principled` com tom sorteado entre 5 tons Fitzpatrick-like ((0,85;0,62;0,50) … (0,25;0,15;0,10)), `Noise` Scale 800 modulando ±10% e `Bump` 0,15/0,2 mm, `Subsurface Weight 0,6`, `Radius` (3,6; 1,4; 0,7 mm), `Roughness 0,55`. Na versão final: pele do MPFB (`enhanced_skin`) ou textura CC0 de `assets/pele/`.

### 4.3 Câmera (celular a 5–12 cm) — ótica FÍSICA, não "equivalente 35 mm"

- Posição: `DIST` = 55–120 mm em +Z, offset lateral ±15 mm, vertical ±10 mm.
- **Não use `Track To` nem `to_track_quat('-Z','Y')`**: ambos tomam o +Z do mundo como "up" e a câmera olha justamente ao longo de Z → roll indefinido (bug encontrado no protótipo). Construir a rotação: `zc = (cam − alvo).normalized()`, `xc = (0,1,0) × zc`, `yc = zc × xc`, `rotation_euler = Matrix((xc, yc, zc)).transposed().to_euler()`.
- Ótica: `sensor_width 7 mm` (sensor 1/1.7"–1/1.3") e **distância focal física 5,5–9 mm** (≈26–43 mm equiv.). Erro clássico (cometido na 1ª versão): pôr `lens = 26–70 mm` num sensor de 7 mm — a abertura física `lens/f` vira 15–40 mm e a DOF cai para < 1 mm, tudo fica borrado. Com 5,5–9 mm e f/1,7–2,4 a DOF fica em ±3–5 mm a 8 cm: íris nítida, cílios levemente suaves, como nas fotos reais.
- **DOF**: `dof.use_dof = True`, `focus_distance = DIST − 10 mm` (plano da íris), `aperture_fstop` 1,7–2,4.
- Enquadramento resultante: largura do quadro = `DIST × sensor / lens` ≈ 43–150 mm → o olho (~30 mm) ocupa 20–70% do quadro, como numa foto antes do crop. Recortar depois pelo bbox da máscara da esclera (renderizar `IndexOB`) se o modelo esperar o olho centralizado; para a 3ª câmera tele (~77 mm equiv.) usar `lens 16 mm`.
- **Balanço de branco / exposição** (simula AWB e AE do celular): `view_settings.use_white_balance = True`, `white_balance_temperature` 4300–6800 K, `white_balance_tint` ±5, `exposure` ±0,5 EV. Sem isso o HDRI quente ("blinds") deixa tudo laranja (visto no teste v3).

### 4.4 Iluminação

- World: `Environment Texture` (HDRI 2k de `assets/hdri/`) → `Background Strength` 0,6–1,6; `Mapping.Rotation.Z` aleatório 0–360°.
- **Flash** opcional: `Point` light **junto à lente** (offset 8 mm em X, 4 mm em Y), `shadow_soft_size 2 mm`, cor (1,0; 0,95; 0,90). Potência: 0,1–0,3 W **a 12 cm**, escalada por `(DIST/0,12)²` para manter a irradiância no olho (0,6 W já superexpõe a pele com AgX). O flash coaxial produz o reflexo de Purkinje pontual e a **leucocoria** quando o cristalino é branco.
- View transform padrão AgX; para simular auto-exposição do celular, sortear `scene.view_settings.exposure` em ±0,7 EV.

### 4.5 Render

`CYCLES`, `device GPU`, 64–128 spp, `use_denoising True`, `max_bounces 8`, `transmission_bounces 8`, `transparent_max_bounces 8`. Saída PNG 8 bits (depois aplicar pipeline de sensor: ruído dependente de ISO, aberração cromática, vinheta, balanço de branco, JPEG q 70–95 — §6).

---

## 5. Pintando cada sinal proceduralmente — parâmetros e faixas

Todas as máscaras são calculadas em **coordenadas de objeto do globo** (`Texture Coordinate → Object`, com `object = Esclera` também no material da córnea, para compartilhar o referencial). Grau/posição sorteados viram rótulos.

| sinal | onde | máscara / geometria | parâmetros (faixa) | cor / shader |
|---|---|---|---|---|
| **Pterígio** | conjuntiva nasal (−X) → córnea | cunha: `|atan2(y, −x)| < ang` e `−x > 0`; na córnea a abertura angular cai linearmente até o ápice (`Map Range` de −x∈[x_apex, R_iris]) | semi-ângulo 12–22°; ápice invadindo 0,5–3,5 mm da córnea (grau I–III); opcional lado temporal 10% | carne rosada (0,75–0,78; 0,50–0,55; 0,38–0,40), `Coat 1`, `Subsurface 0,4`, vasos radiais mais densos dentro da cunha. **Melhoria**: extrudar a cunha como malha 0,3–0,6 mm de espessura sobre a esclera (`Solidify`) para ter borda com sombra. |
| **Pinguécula** | limbo nasal/temporal, 3 ou 9 h | blob: distância a ponto (−7,5; 0; 9,4) mm < 1,0–1,6 mm, suavizada por `Map Range` | Ø 1,5–3 mm; leve `Bump` 0,2 mm | amarelo-pálido (0,85; 0,75; 0,40); não invade a córnea |
| **Hemorragia subconjuntival** | esclera anterior visível | distância a ponto sobre a esfera com ângulo polar **38–55°** do ápice (limbo ≈32°, borda palpebral ≈60°), azimute perto de 0°/180° (temporal/nasal); borda **nítida** (`Map Range` de 0,4 mm) ligeiramente irregular por `Noise` ×1,5 mm | raio 3–7 mm; opcional 2ª mancha; grau "difuso" cobrindo 180° | vermelho vivo homogêneo (0,42; 0,015; 0,01), **sem** vasos visíveis por cima, mesma umidade (`Coat`) |
| **Hiperemia / injeção conjuntival** | toda a conjuntiva bulbar | densidade e calibre dos vasos + tinta difusa | Voronoi Scale 28–45 (vs 10–18 normal), meia-largura 0,016 (vs 0,005), tinta k=0,35–0,7 para (0,80; 0,42; 0,38); variante **ciliar** (perilimbar): peso maior perto do limbo (theta<45°) | vaso (0,55; 0,03; 0,02) |
| **Icterícia** | esclera inteira | uniforme | k=0,35–1,0 entre (0,86; 0,84; 0,80) e (0,90; 0,78; 0,30) | manter vasos normais; opcional pele levemente amarelada (k/2) |
| **Catarata / leucocoria** | cristalino atrás da pupila | disco "Cristalino" | grau 0,45 (nuclear amarelada) – 0,9 (madura branca); pupila 3–8 mm; **com flash coaxial** a leucocoria salta | `Principled` cor (g; g·0,85–1,0; g·0,6–0,95), `Subsurface 1`, `Roughness 0,5` |
| **Opacidade corneana / leucoma** | córnea | blob no material da córnea: distância a ponto (±3, ±3, 13) mm, `Noise` 2 mm, `Map Range` r·0,4→r·1,3 | raio 1,5–4 mm; opacidade 0,5–0,95; pode cobrir a pupila | `Mix Shader` Glass → `Principled` leitoso (0,85; 0,85; 0,82), `Subsurface 1`, `Transmission 0,3` |
| **Hipópio** | câmara anterior inferior | no material da íris: `Object.Y < nível` (menisco horizontal, transição 0,3 mm) cobrindo íris **e** pupila | nível 1–4 mm acima da borda inferior do limbo | creme (0,92; 0,90; 0,80), `Subsurface 0,8`. **Melhoria**: malha-calota entre íris e córnea para o menisco ter espessura vista de lado. |
| **Ptose** | pálpebra superior | protótipo: cortador da fenda desce e encolhe (1,5–3,5 mm); MPFB: alvos `*-eye-height*`/expressão de pálpebra | MRD1 normal 4–5 mm → leve 3 mm, moderada 2, grave ≤1 (pupila coberta) | pele |
| **Calázio** | pálpebra (sup. 70%) | esfera r=2–4 mm no tarso, 4 mm acima da fenda; ideal: `Displace` com textura esférica na malha da pálpebra para fundir com a pele | Ø 3–8 mm; leve eritema (mix vermelho 0,1–0,3 ao redor) | pele |
| **Proptose** | globo | translação do globo +2–5 mm em Z, fenda 25% mais alta, esclera visível acima da íris ("scleral show") | 2–5 mm (bilateral vs unilateral) | — |
| **Normal** | — | tudo acima em 0; pupila 3–6 mm; vasos normais | — | — |

Notas para realismo dos sinais (das referências visuais em `assets/refs/`):
- Pterígio real tem **cabeça** (ponta na córnea, cinza-esbranquiçada), **corpo** vascularizado em leque e "linha de Stocker" (ferro) à frente; a superfície é elevada — vale o `Solidify`.
- Hemorragia: cor **uniforme** e limite nítido é o que a distingue da hiperemia (vasos individualizados). Não pôr vasos por cima.
- Catarata em foto de celular: sem flash aparece **cinza/esbranquiçada na pupila**; com flash coaxial, reflexo branco (leucocoria) em vez de reflexo vermelho. Para ter reflexo vermelho normal, dar ao fundo do olho (backfacing) cor (0,35; 0,05; 0,02) e `Roughness 0,3`.
- Hipópio: menisco **horizontal** independente da inclinação da cabeça (é gravidade) — se randomizar roll da câmera, manter o nível horizontal no mundo.

---

## 6. Sim-to-real para imagens de olho — o que a literatura diz

Resumo por trabalho (números do texto dos artigos; relatório completo do levantamento em `assets/refs/LITERATURA_sim2real.md`):

| trabalho | como fez | resultado-chave | assets abertos? |
|---|---|---|---|
| **SynthesEyes** (Wood et al., ICCV 2015) | 10 regiões oculares escaneadas, globo com córnea refrativa n=1,376, 3 camadas de textura (tinta da esclera, 4 íris, veias), **Blender Cycles** 150 spp, 4 HDRIs rotacionados | ablação: iluminação real variada + movimento de pálpebra são o que mais importa; gaze MPIIGaze 13,55° (sintético) → 7,90° com síntese dirigida + fine-tuning real | dataset sem licença explícita; modelo 3D não liberado |
| **UnityEyes** (Wood et al., ETRA 2016) | Unity, modelo PCA da região ocular, refração por shader, 20 HDR, íris de fotos | k-NN só-sintético 9,95° em MPIIGaze; sem variação de aparência 10,62° | só binário "para pesquisa" |
| **SimGAN** (Shrivastava et al., CVPR 2017) | refinador GAN sobre UnityEyes (1,2 M) com 214 k reais não rotuladas | refinador **adiciona textura de pele, ruído de sensor e aparência de íris**; erro 11,2° → 7,8°; Turing test humano 51,7% | código de terceiros |
| **NVGaze** (Kim et al., CHI 2019) | 2 M imagens IR, globo do SynthesEyes corrigido (24 mm, córnea 7,8 mm, n=1,38), pupila 2–8 mm, ray tracing 30 s/img | geometria anatômica + reflectância na iluminação-alvo são o que conta; só-sintético 3,1° → **+3 sujeitos reais 2,1°**; razão sintético:real ≈ 2:1 | página com login; licença não verificada |
| **RIT-Eyes** (Nair et al., 2020, **Blender 2.8 + Cycles**) | 24 cabeças 3dscanstore, córnea asférica (Q −0,13…−0,37), 9 íris, **1 esclera**, 25 HDRIs, filme lacrimal, carúncula | mIoU 95 (sint→sint) cai para 74–85 em real; gap é de **aparência de pixel, não de pose**; esclera real mIoU 34–49 por falta de variedade | datasets sim, pipeline não |
| Nguyen et al. 2024 (RIT-Eyes → OpenEDS) | CycleGAN com preservação de estrutura + DANN | mIoU 0,49–0,56 → **0,64**; falta nos renders: cílios, textura de pele e de íris | código https://github.com/PerForm-Lab-RIT/domain-adaptation-eye-tracking |
| Domain randomization (Tobin 2017; SDR Prakash 2019) | texturas/luz/câmera aleatórias; DR *estruturada* | > 1 000 texturas; ruído gaussiano irrelevante; **pré-treino SDR + poucos reais > reais sozinhos**, mais ganho quanto menor o real | — |
| Sensor Transfer (Carlson 2018/19) | aprende aberração cromática, exposição, ruído, WB por perda de estilo | +1,7 a +5,4 AP; blur gaussiano converge a zero (blur real não é gaussiano) | — |
| Difusão como augmentação (Azizi TMLR 2023; He ICLR 2023; Fan CVPR 2024; DA-Fusion ICLR 2024) | Imagen/SD fine-tuned; img2img sobre reais | +1,2–1,8 pp a 1:1; **mais sintético piora** (−1,35 a 9:1); few-shot até +10 pp; ajuda quando real < 0,5 M e OOD | DA-Fusion: https://github.com/brandontrabucco/da-fusion |
| **Cureus 2026** (Keshav, Das et al., AIIMS; DOI 10.7759/cureus.109409) | 100 sintéticas (IA generativa) + 100 fotos de smartphone; YOLOv8-seg esclera/íris/pupila | **mista 50/50: pupila 88,5 ± 5,9%** e sem falhas; só-IA 0% numa foto real, só-real 50% numa sintética; dobrar para 200 não ajudou (p=0,95). "Composição, não tamanho" | — |
| Wang et al., Ocular Surface 2026 | SD fine-tuned com 17 853 fotos de lâmpada de fenda, 8 doenças | classificador treinado em sintético: micro-AUC 0,977, superou baseline real | — |
| NeoJaundice-AI 2026; anemia conjuntival HIR 2025 | augmentação físico-informada YCbCr; DCGAN 764 → 4 315 | icterícia 91,8% acc; anemia 82,4 → 89,5% | — |
| **SLID** (Front. Digit. Health 2025) | 2 617 fotos de lâmpada de fenda, 13 lesões (pterígio 163, catarata 225, hiperemia 307, hemorragia 181…) | dataset **real CC-BY** — âncora para medir o gap; já está em `dados/labels_slid.csv` | https://github.com/xumingyu-hub/SLID |

**Resumo em 10 linhas — o que funcionou**
1. Realismo *físico* rende mais que "beleza": geometria anatômica do globo, refração da córnea, texturas na iluminação-alvo, HDRIs variados e pálpebra acoplada ao olhar (ablações NVGaze/SynthesEyes).
2. Sintético puro sempre deixa gap (RIT-Eyes 95 → 74–85 mIoU; NVGaze 3,1° vs 0,84°; SynthesEyes 13,5° vs 6,3°).
3. O gap é de **aparência/estatística de pixel** (pele, cílios, íris, esclera, ruído), não de pose de câmera.
4. Poucos dados reais no treino fecham a maior parte: NVGaze +3 sujeitos → −32% de erro; SDR + poucos reais > reais sozinhos; Cureus 50/50 elimina falhas catastróficas.
5. Razão ótima ≈ **1:1 a 2:1 sintético:real**; acima disso piora (Azizi; He: ~5× sintético para igualar real).
6. Refino sim2real (SimGAN, CycleGAN estrutural, img2img/ControlNet sobre renders) dá +10 pp a −30% de erro sem novos rótulos.
7. **Variedade de textura** conta mais que fotorrealismo (Tobin > 1 000 texturas; RIT-Eyes falhou na esclera com 1 textura).
8. Simular o sensor importa (Sensor Transfer), mas ruído gaussiano e JPEG isolados quase não mudam nada.
9. Difusão fine-tuned no domínio já supera baseline real em lâmpada de fenda (Wang 2026), com risco de viés e vazamento de identidade.
10. Modos de falha: renders limpos demais (texture bias), esclera/pele sem variedade, cílios/maquiagem ausentes, highlights e reflexos errados, rótulos anatômicos divergentes, tons de pele restritos.

**Recomendações concretas para o nosso dataset Blender (olho externo, macro de celular)**
1. Cycles com globo anatômico: córnea r≈7,8 mm (opcional asférica Q≈−0,25 ± 0,12), IOR 1,376, esclera 12 mm, filme lacrimal, carúncula.
2. Íris com pupila 2–8 mm e **≥ 20 texturas** fotográficas rotacionadas; **≥ 10 texturas de esclera** com veias, tintas (branca/rosa/amarela) e vasos procedurais — ponto fraco documentado.
3. ≥ 20 cabeças cobrindo Fitzpatrick I–VI (MPFB: macros de etnia/idade/gênero + alvos de olho), pálpebras rigadas, piscadas parciais, cílios, maquiagem.
4. ≥ 25 HDRIs (já temos 14) com rotação 360° e ±50% de intensidade, + flash/LED coaxial de celular + luz de teto de UBS.
5. Randomização **estruturada** (distribuições plausíveis de distância 5–15 cm, ângulo, oclusão palpebral), não uniforme.
6. Simulação de sensor no pós: aberração cromática, vinheta, WB variado, ruído dependente de ISO, motion/defocus blur não gaussiano, tone mapping tipo ISP; JPEG só na entrega.
7. Patologias como camadas parametrizadas com máscaras de ground truth automáticas (§5).
8. Refino img2img/ControlNet (Canny/depth do render) com força 0,3–0,5, ou CycleGAN com preservação de estrutura; filtrar amostras mal reconstruídas.
9. Treinar **misto ~1:1** com as fotos reais do projeto, depois fine-tuning só-real; comparar com pré-treino sintético → fine-tuning; avaliar em teste real separado por centro.
10. Usar o sintético para cobrir **caudas** (peles escuras, olhos pequenos, sinais raros: hipópio, leucocoria, proptose), não para inflar volume; não passar de 2:1.
11. Alinhar taxonomia de rótulos (carúncula, limbo, pálpebra) com o dataset real antes de renderizar; validar com FID/KID e Turing test com oftalmologista.
12. Licenças: Poly Haven CC0, texturas CC0 listadas, SLID CC-BY como âncora real; UnityEyes/NVGaze/Face Synthetics são só-pesquisa e não liberam assets — o rig próprio no Blender é o caminho.

Fontes: SynthesEyes https://arxiv.org/abs/1505.05916 · UnityEyes https://www.cl.cam.ac.uk/research/rainbow/projects/unityeyes/ · SimGAN https://arxiv.org/abs/1612.07828 · NVGaze https://research.nvidia.com/publication/2019-05_nvgaze-anatomically-informed-dataset-low-latency-near-eye-gaze-estimation · RIT-Eyes https://arxiv.org/abs/2006.03642 · Nguyen 2024 https://arxiv.org/abs/2403.15947 · Tobin 2017 https://arxiv.org/abs/1703.06907 · SDR https://arxiv.org/abs/1810.10093 · Sensor Transfer https://arxiv.org/abs/1809.06256 · Azizi 2023 https://arxiv.org/abs/2304.08466 · He 2023 https://arxiv.org/abs/2210.07574 · Fan 2024 https://arxiv.org/abs/2312.04567 · DA-Fusion https://arxiv.org/abs/2302.07944 · Cureus 2026 https://www.cureus.com/articles/493842 · Wang 2026 https://pubmed.ncbi.nlm.nih.gov/42324026/ · SLID https://pmc.ncbi.nlm.nih.gov/articles/PMC12832839/ · Face Synthetics https://microsoft.github.io/FaceSynthetics/

---

## 7. Checagens (QA) e próximos passos

**Checagens automáticas sugeridas** (podem virar `assert`s no script):
1. Diâmetro do limbo em px ≈ 12,6 mm × escala (medir a partir da máscara da íris renderizada com `View Layer → Object Index`).
2. Presença de 1 reflexo especular pequeno na córnea (máximo local > 0,9 em luminância dentro da máscara da córnea) — Purkinje.
3. Refração: razão diâmetro-da-íris-aparente / geométrico ∈ [1,08; 1,18].
4. Histograma: mediana da pele entre 0,25 e 0,75 (nem estourada nem escura); nada de clipping > 2% dos px fora do reflexo.
5. Máscaras de rótulo por *pass index*: esclera=1, íris=2, pupila=3, pele=4, sinal=5 (renderizar `IndexOB`), para segmentação e para verificar que o sinal está visível (área do sinal ≥ 0,5% do quadro).
6. Tempo por imagem e seed reproduzível (`random.seed`).

**Próximos passos**
1. Trocar a pele-placeholder pela cabeça MPFB com o pacote de assets (§3): pálpebras reais, cílios, carúncula, expressões; sortear macros (idade 15–80, etnia, gênero) e alvos de olho.
2. Ligar as fotos de íris/esclera de `assets/iris_texturas/` como textura-base (UV polar) com o procedural por cima.
3. Pipeline de "sensor" pós-render (§6): ruído, aberração cromática, vinheta, WB, motion blur, JPEG.
4. Gerar 300–500 imagens por sinal com máscaras, medir FID vs. fotos reais do projeto (`dados/`) e treinar misto ~1:1 vs. só-real, avaliando no conjunto real por centro.
5. Refino img2img/ControlNet (força 0,3–0,5) sobre os renders para fechar o gap de textura.
