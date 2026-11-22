"""垂木の全展開スクリプト（部品v11、モデルv25）

使い方：
    blender --background heian_daidairi_detail_v24.blend \
        --python build_refine_v25.py

モデルv24を開き、軒の垂木を残りの屋根にも広げて
heian_daidairi_detail_v25.blend として保存する。確認画像つき。

内容（2026-11-22）：
- 垂木はこれまで大極殿と入母屋5棟（部品v4）と回廊（部品v5）に
  だけ付いていた。残りの大内裏の屋根（殿舎・官衙の庁舎・門の
  上下の屋根・入母屋の切妻屋根）にも、同じ方式（長辺の軒下に
  約0.92m間隔、勾配に沿う傾き）で垂木を付けた。
- 対象は大内裏側の屋根で、長辺7m以上のもの。市街レイヤー
  （COL_70_City）の屋根には付けない。推定レイヤーの建物の分には
  evidence=conjectural を付けた。新規分は専用コレクション
  COL_12_ExteriorRefine8。

利用者の提案 docs/proposal/01_non-building-enrichment.md の
E1〜E10 には手をつけていない。
"""
import bpy
from collections import defaultdict
from mathutils import Vector

def base_name(o):
    n = o.name
    return n.rsplit(".", 1)[0] if "." in n and n.rsplit(".", 1)[1].isdigit() else n

def wbbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

ecol = bpy.data.collections.new("COL_12_ExteriorRefine8")
bpy.context.scene.collection.children.link(ecol)
ecol["layer"] = "exterior_refine_v11"

_cubes = {}
def fbox(name, loc, dims, mat, fid="", evidence=None):
    key = mat.name if mat else "None"
    mesh = _cubes.get(key)
    if mesh is None:
        mesh = bpy.data.meshes.new("Refine8Cube_" + key)
        mesh.from_pydata(
            [(-.5, -.5, -.5), (.5, -.5, -.5), (.5, .5, -.5), (-.5, .5, -.5),
             (-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5)],
            [],
            [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2),
             (2, 6, 7, 3), (3, 7, 4, 0)])
        mesh.update()
        if mat:
            mesh.materials.append(mat)
        _cubes[key] = mesh
    ob = bpy.data.objects.new(name, mesh)
    ob.location = loc
    ob.scale = dims
    if fid:
        ob["facility_id"] = fid
    if evidence:
        ob["evidence"] = evidence
    ecol.objects.link(ob)
    return ob

WOOD = bpy.data.materials["MAT_WoodDark"]

# 接頭辞 → facility_id（屋根には付いていないので他の部品から引く）
fid_by_prefix = {}
for o in bpy.data.objects:
    fid = o.get("facility_id", "")
    if fid:
        bn = base_name(o)
        for suf in ("_Wall", "_Col", "_Kidan", "_Base", "_Roof", "_Roof2"):
            if bn.endswith(suf):
                fid_by_prefix.setdefault(bn[: -len(suf)], fid)
                break

# すでに垂木のある屋根は除く
has_rafter = set()
for o in bpy.data.objects:
    b = base_name(o)
    if "_Rafter" in b:
        has_rafter.add(b.split("_Rafter")[0])

def in_city(o):
    return any(c.name.startswith("COL_70") for c in o.users_collection)

n_raft = 0
n_roofs = 0
e1_roof = None
for o in list(bpy.data.objects):
    if o.type != "MESH":
        continue
    bn = base_name(o)
    if not (bn.endswith("_Roof") or bn.endswith("_Roof2") or bn.endswith("_RoofGable")):
        continue
    if bn in has_rafter or in_city(o):
        continue
    prefix = bn.rsplit("_", 1)[0] if not bn.endswith("_RoofGable") else bn[: -len("_RoofGable")]
    if bn.endswith("_Roof"):
        prefix = bn[: -len("_Roof")]
    elif bn.endswith("_Roof2"):
        prefix = bn[: -len("_Roof2")]
    x0, x1, y0, y1, z0, z1 = wbbox(o)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    w, d = x1 - x0, y1 - y0
    if max(w, d) < 7.0:
        continue
    fid = fid_by_prefix.get(prefix, "")
    ev = "conjectural" if prefix.startswith("CONJ_") else None
    eave_z = z0 + 0.35
    if w >= d:
        span = w * 0.80
        cnt = max(4, int(span / 0.92))
        for sy in (-1, 1):
            for i in range(cnt + 1):
                x = cx - span / 2.0 + span * i / cnt
                ob = fbox(bn + "_Rafter", (x, cy + sy * (d / 2.0 - 0.30), eave_z - 0.28),
                          (0.13, 0.55, 0.10), WOOD, fid, ev)
                ob.rotation_euler.x = -sy * 0.6
                n_raft += 1
    else:
        span = d * 0.80
        cnt = max(4, int(span / 0.92))
        for sx in (-1, 1):
            for i in range(cnt + 1):
                y = cy - span / 2.0 + span * i / cnt
                ob = fbox(bn + "_Rafter", (cx + sx * (w / 2.0 - 0.30), y, eave_z - 0.28),
                          (0.55, 0.13, 0.10), WOOD, fid, ev)
                ob.rotation_euler.y = sx * 0.6
                n_raft += 1
    n_roofs += 1
    if bn == "CHD_E1_Roof":
        e1_roof = (cx, cy, w, d, eave_z)
print("RAFTER_ALL_DONE roofs=%d rafters=%d" % (n_roofs, n_raft), flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v25.blend")
print("SAVED_V25", flush=True)

# ---------------------------------------------------------------- 確認描画
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
cam_data = bpy.data.cameras.new("V25Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V25Cam", cam_data)
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

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v25"
setup_cam((11, -15, 2.0), (0, -1, 6.8), lens=38)
render(OUT + "_suzaku.png", 1280, 720, 64)
print("SUZAKU_DONE", flush=True)
if e1_roof:
    cx, cy, w, d, ez = e1_roof
    setup_cam((cx + w / 2.0 + 7, cy - d / 2.0 - 9, ez - 1.6), (cx, cy - d / 2.0 + 1, ez + 0.4), lens=38)
    render(OUT + "_eave.png", 1280, 720, 64)
    print("EAVE_DONE", flush=True)
setup_cam((430, 60, 330), (0, 640, 0), lens=35)
render(OUT + "_top.png", 1600, 1600, 32)
print("TOP_DONE", flush=True)
