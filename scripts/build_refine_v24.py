"""棟まわりの装飾の作り込みスクリプト（部品v10、モデルv24）

使い方：
    blender --background heian_daidairi_detail_v23.blend \
        --python build_refine_v24.py

モデルv23を開き、既存の棟まわりの装飾（鴟尾・懸魚・鬼瓦）を
形のあるものに置き換えて heian_daidairi_detail_v24.blend として
保存する。確認画像つき。

内容（2026-11-22）：
- 大内裏の生成時から、鴟尾・懸魚・鬼瓦はすべて単純な箱で置かれて
  いた。これらを輪郭（プロファイル）を押し出した形に置き換えた。
  - **鴟尾**：金の箱 → 魚尾の輪郭を持つ形（外へ反る尾の先端つき）。
    殿舎と門の楼の分すべて
  - **懸魚**：木の箱 → 鋤形（スペード形）の輪郭。入母屋5棟の破風
  - **鬼瓦**：石の箱 → 上部が広がる瓦の輪郭（瓦の素材に変更）。
    寄棟の殿舎の分すべて
- 置き換えた新規分は専用コレクション COL_11_ExteriorRefine7。
  位置と大きさは元の箱から引き継いだ。

利用者の提案 docs/proposal/01_non-building-enrichment.md の
E1〜E10 には手をつけていない。扁額の文字は利用者の判断で
入れない（v23）。
"""
import bpy
import math
from mathutils import Vector

def base_name(o):
    n = o.name
    return n.rsplit(".", 1)[0] if "." in n and n.rsplit(".", 1)[1].isdigit() else n

ecol = bpy.data.collections.new("COL_11_ExteriorRefine7")
bpy.context.scene.collection.children.link(ecol)
ecol["layer"] = "exterior_refine_v10"

GOLD = bpy.data.materials["MAT_Gold"]
WOOD = bpy.data.materials["MAT_WoodDark"]
TILE = bpy.data.materials["MAT_RoofTile"]

def prism_mesh(name, profile, thickness, mat):
    """profile: [(u, v), ...]（u=水平、v=上）。y方向に押し出す。"""
    n = len(profile)
    verts = []
    for yy in (-thickness / 2.0, thickness / 2.0):
        for (u, v) in profile:
            verts.append((u, yy, v))
    faces = []
    faces.append(tuple(range(n - 1, -1, -1)))            # 背面
    faces.append(tuple(range(n, 2 * n)))                 # 前面
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))               # 側面
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    if mat:
        mesh.materials.append(mat)
    return mesh

# 鴟尾の輪郭（u は棟の外向き、v は上。原点は底面の中心）
SHIBI_PROFILE = [(-0.48, 0.0), (0.30, 0.0), (0.36, 0.45), (0.30, 0.85),
                 (0.55, 1.32), (0.34, 1.42), (0.05, 1.10), (-0.16, 0.95),
                 (-0.30, 0.55), (-0.42, 0.22)]
# 懸魚の輪郭（u は破風の水平、v は上。原点は上端の中心）
GEGYO_PROFILE = [(-0.27, 0.0), (0.27, 0.0), (0.27, -0.42), (0.14, -0.70),
                 (0.0, -1.02), (-0.14, -0.70), (-0.27, -0.42)]
# 鬼瓦の輪郭（u は棟方向、v は上。原点は底面の中心）
ONI_PROFILE = [(-0.30, 0.0), (0.30, 0.0), (0.37, 0.40), (0.31, 0.60),
               (0.13, 0.72), (-0.13, 0.72), (-0.31, 0.60), (-0.37, 0.40)]

SHIBI_MESH = prism_mesh("ShibiMesh", SHIBI_PROFILE, 0.46, GOLD)
GEGYO_MESH = prism_mesh("GegyoMesh", GEGYO_PROFILE, 0.13, WOOD)
ONI_MESH = prism_mesh("OniMesh", ONI_PROFILE, 0.50, TILE)

def place(name, mesh, loc, rot_z, scale, fid, evidence=None):
    ob = bpy.data.objects.new(name, mesh)
    ob.location = loc
    ob.rotation_euler = (0, 0, rot_z)
    ob.scale = (scale, scale, scale)
    if fid:
        ob["facility_id"] = fid
    if evidence:
        ob["evidence"] = evidence
    ecol.objects.link(ob)
    return ob

def anchors(suffix):
    out = []
    for o in list(bpy.data.objects):
        if base_name(o).endswith(suffix):
            out.append(o)
    return out

n_shibi = 0
shibi_objs = anchors("_Shibi")
by_prefix = {}
for o in shibi_objs:
    by_prefix.setdefault(base_name(o)[: -len("_Shibi")], []).append(o)
dgk_shibi_pos = None
for prefix, ps in by_prefix.items():
    fid = ps[0].get("facility_id", "")
    for o in ps:
        loc = o.location.copy()
        sx, sy, sz = o.scale.x, o.scale.y, o.scale.z
        s = sz / 1.3
        along_x = sx <= sy  # 棟が X 方向（箱が薄い方が棟方向）
        if along_x:
            cx = sum(p.location.x for p in ps) / len(ps)
            sign = 1 if loc.x >= cx else -1
            rot = 0.0 if sign > 0 else math.pi
            base = (loc.x, loc.y, loc.z - sz / 2.0)
        else:
            cy = sum(p.location.y for p in ps) / len(ps)
            sign = 1 if loc.y >= cy else -1
            rot = math.pi / 2.0 if sign > 0 else -math.pi / 2.0
            base = (loc.x, loc.y, loc.z - sz / 2.0)
        place(prefix + "_ShibiS", SHIBI_MESH, base, rot, s, fid, ps[0].get("evidence"))
        if prefix == "CHD_Daigokuden" and sign > 0 and along_x:
            dgk_shibi_pos = base
        n_shibi += 1
for o in shibi_objs:
    bpy.data.objects.remove(o, do_unlink=True)
print("SHIBI_DONE", n_shibi, flush=True)

n_gegyo = 0
gegyo_objs = anchors("_Gegyo")
for o in gegyo_objs:
    loc = o.location.copy()
    sz = o.scale.z
    s = sz / 0.85
    fid = o.get("facility_id", "")
    prefix = base_name(o)[: -len("_Gegyo")]
    top = (loc.x, loc.y, loc.z + sz / 2.0)
    place(prefix + "_GegyoS", GEGYO_MESH, top, math.pi / 2.0, s, fid, o.get("evidence"))
    n_gegyo += 1
for o in gegyo_objs:
    bpy.data.objects.remove(o, do_unlink=True)
print("GEGYO_DONE", n_gegyo, flush=True)

n_oni = 0
oni_objs = anchors("_Onigawara")
oni_cam = None
for o in oni_objs:
    loc = o.location.copy()
    sx, sy, sz = o.scale.x, o.scale.y, o.scale.z
    s = sz / 0.65
    fid = o.get("facility_id", "")
    prefix = base_name(o)[: -len("_Onigawara")]
    rot = 0.0 if sx <= sy else math.pi / 2.0
    base = (loc.x, loc.y, loc.z - sz / 2.0)
    place(prefix + "_OniS", ONI_MESH, base, rot, s, fid, o.get("evidence"))
    if prefix == "CHD_E1":
        oni_cam = base
    n_oni += 1
for o in oni_objs:
    bpy.data.objects.remove(o, do_unlink=True)
print("ONI_DONE", n_oni, flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v24.blend")
print("SAVED_V24", flush=True)

# ---------------------------------------------------------------- 確認描画
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
cam_data = bpy.data.cameras.new("V24Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V24Cam", cam_data)
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

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v24"
if dgk_shibi_pos:
    bx, by, bz = dgk_shibi_pos
    setup_cam((bx + 11, by - 13, bz - 1.5), (bx - 1, by, bz + 0.8), lens=40)
    render(OUT + "_shibi.png", 1280, 720, 64)
    print("SHIBI_CAM_DONE", flush=True)
if oni_cam:
    bx, by, bz = oni_cam
    setup_cam((bx + 5, by - 9, bz + 0.5), (bx, by, bz + 0.3), lens=40)
    render(OUT + "_oni.png", 1280, 720, 64)
    print("ONI_CAM_DONE", flush=True)
setup_cam((430, 60, 330), (0, 640, 0), lens=35)
render(OUT + "_top.png", 1600, 1600, 32)
print("TOP_DONE", flush=True)
