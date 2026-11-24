"""高欄の擬宝珠スクリプト（部品v14、モデルv28）

使い方：
    blender --background heian_daidairi_detail_v27.blend \
        --python build_refine_v28.py

モデルv27を開き、高欄の柱頭に擬宝珠を付けて
heian_daidairi_detail_v28.blend として保存する。確認画像つき。

内容（2026-11-23）：
- 朱の高欄（大極殿＝部品v5、内裏の正殿3棟＝部品v12）の柱は
  これまで角柱のままだった。柱頭に金銅の擬宝珠（玉ねぎ形の
  飾り、高さ約0.21m）を載せた。輪郭を旋盤状に起こした共有
  メッシュを使い、対象は両部品の高欄の柱すべて。
- 新規分は専用コレクション COL_15_ExteriorRefine11。

利用者の提案 docs/proposal/01_non-building-enrichment.md の
E1〜E10 には手をつけていない。
"""
import bpy
import math
from mathutils import Vector

def base_name(o):
    n = o.name
    return n.rsplit(".", 1)[0] if "." in n and n.rsplit(".", 1)[1].isdigit() else n

def wbbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

ecol = bpy.data.collections.new("COL_15_ExteriorRefine11")
bpy.context.scene.collection.children.link(ecol)
ecol["layer"] = "exterior_refine_v14"

GOLD = bpy.data.materials["MAT_Gold"]

# 擬宝珠の旋盤メッシュ（輪郭 (半径, 高さ) を12角で回す）
PROFILE = [(0.001, 0.00), (0.058, 0.00), (0.062, 0.03), (0.030, 0.07),
           (0.052, 0.12), (0.036, 0.165), (0.012, 0.20), (0.001, 0.215)]
SEG = 12
verts = []
faces = []
for ri, (r, z) in enumerate(PROFILE):
    for si in range(SEG):
        a = 2.0 * math.pi * si / SEG
        verts.append((r * math.cos(a), r * math.sin(a), z))
for ri in range(len(PROFILE) - 1):
    for si in range(SEG):
        a = ri * SEG + si
        b = ri * SEG + (si + 1) % SEG
        c = (ri + 1) * SEG + (si + 1) % SEG
        d = (ri + 1) * SEG + si
        faces.append((a, b, c, d))
gib_mesh = bpy.data.meshes.new("GiboshiMesh")
gib_mesh.from_pydata(verts, [], faces)
gib_mesh.update()
gib_mesh.materials.append(GOLD)

n_gib = 0
for o in list(bpy.data.objects):
    bn = base_name(o)
    if not bn.endswith("_RailPost"):
        continue
    cols = [c.name for c in o.users_collection]
    if not any(c.startswith(("COL_06", "COL_13")) for c in cols):
        continue
    x0, x1, y0, y1, z0, z1 = wbbox(o)
    ob = bpy.data.objects.new(bn + "_Giboshi", gib_mesh)
    ob.location = ((x0 + x1) / 2.0, (y0 + y1) / 2.0, z1 - 0.01)
    fid = o.get("facility_id", "")
    if fid:
        ob["facility_id"] = fid
    ecol.objects.link(ob)
    n_gib += 1
print("GIBOSHI_DONE count=%d" % n_gib, flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v28.blend")
print("SAVED_V28", flush=True)

# ---------------------------------------------------------------- 確認描画
for c in bpy.data.collections:
    if c.name.startswith("COL_70"):
        c.hide_render = True
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
cam_data = bpy.data.cameras.new("V28Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V28Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

def setup_cam(loc, target, lens=35):
    cam.location = loc
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam_data.lens = lens

def render(path, w, h, samples):
    scene.render.resolution_x = w
    scene.render.resolution_y = h
    scene.cycles.samples = samples
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v28"
setup_cam((13, 541, 3.6), (1, 554.5, 3.1), lens=42)
render(OUT + "_daigoku.png", 1280, 720, 48)
print("DAIGOKU_DONE", flush=True)
setup_cam((246.5, 755.5, 2.3), (237.5, 764.5, 2.0), lens=42)
render(OUT + "_seiryo.png", 1280, 720, 48)
print("SEIRYO_DONE", flush=True)
