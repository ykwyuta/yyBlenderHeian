"""軒先の瓦列スクリプト（部品v13、モデルv27）

使い方：
    blender --background heian_daidairi_detail_v26.blend \
        --python build_refine_v27.py

モデルv26を開き、瓦屋根の軒先に丸瓦の列を付けて
heian_daidairi_detail_v27.blend として保存する。確認画像つき。

内容（2026-11-23）：
- 軒先はこれまで屋根の箱の縁そのままだった。瓦屋根（瓦色と
  大極殿の緑釉瓦）の長辺の軒先に、軒丸瓦の円盤（半径0.11m）を
  約0.46m間隔で並べ、その下に瓦列の帯を添えた。対象は部品v11
  の垂木と同じ範囲の屋根（長辺7m以上、市街レイヤーは除く）。
- 檜皮葺の屋根（内裏・後宮。素材 MAT_HiwadaBark）には瓦の軒先が
  ないため対象外。入母屋の破風側の小屋根（_RoofGable）も対象外。
- 円盤の傾きは屋根ごとに実勾配（bbox の高さと奥行き）から求めた。
- 新規分は専用コレクション COL_14_ExteriorRefine10。推定レイヤー
  分には evidence=conjectural を付けた。

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

ecol = bpy.data.collections.new("COL_14_ExteriorRefine10")
bpy.context.scene.collection.children.link(ecol)
ecol["layer"] = "exterior_refine_v13"

_cubes = {}
def fbox(name, loc, dims, mat, fid="", evidence=None):
    key = mat.name if mat else "None"
    mesh = _cubes.get(key)
    if mesh is None:
        mesh = bpy.data.meshes.new("Refine10Cube_" + key)
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

_disc_meshes = {}
def disc_mesh(mat):
    key = mat.name
    if key in _disc_meshes:
        return _disc_meshes[key]
    import bmesh
    mesh = bpy.data.meshes.new("EaveDisc_" + key)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=14,
                          radius1=0.115, radius2=0.115, depth=0.07)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    _disc_meshes[key] = mesh
    return mesh

def fdisc(name, loc, rot, mat, fid="", evidence=None):
    ob = bpy.data.objects.new(name, disc_mesh(mat))
    ob.location = loc
    ob.rotation_euler = rot
    if fid:
        ob["facility_id"] = fid
    if evidence:
        ob["evidence"] = evidence
    ecol.objects.link(ob)
    return ob

fid_by_prefix = {}
for o in bpy.data.objects:
    fid = o.get("facility_id", "")
    if fid:
        bn = base_name(o)
        for suf in ("_Wall", "_Kidan", "_Base", "_Pillar", "_Roof"):
            if bn.endswith(suf):
                fid_by_prefix.setdefault(bn[: -len(suf)], fid)
                break

def in_city(o):
    return any(c.name.startswith("COL_70") for c in o.users_collection)

TILE_MATS = {"MAT_RoofTile", "MAT_RoofGreenGlaze"}
n_disc = 0
n_roofs = 0
e1_roof = None
for o in list(bpy.data.objects):
    if o.type != "MESH":
        continue
    bn = base_name(o)
    if not (bn.endswith("_Roof") or bn.endswith("_Roof2")):
        continue
    if in_city(o):
        continue
    if not o.data.materials or o.data.materials[0].name not in TILE_MATS:
        continue
    mat = o.data.materials[0]
    prefix = bn[: -len("_Roof")] if bn.endswith("_Roof") else bn[: -len("_Roof2")]
    x0, x1, y0, y1, z0, z1 = wbbox(o)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    w, d = x1 - x0, y1 - y0
    if max(w, d) < 7.0:
        continue
    fid = fid_by_prefix.get(prefix, "")
    ev = "conjectural" if prefix.startswith("CONJ_") else None
    if w >= d:
        ang = math.atan2(z1 - z0, d / 2.0)
        span = w * 0.94
        cnt = max(4, int(span / 0.46))
        for sy in (-1, 1):
            ey = cy + sy * (d / 2.0 + 0.03)
            band = fbox(bn + "_EaveBand", (cx, cy + sy * (d / 2.0 - 0.05), z0 + 0.17),
                        (span, 0.22, 0.05), mat, fid, ev)
            band.rotation_euler.x = -sy * ang
            for i in range(cnt + 1):
                x = cx - span / 2.0 + span * i / cnt
                fdisc(bn + "_EaveTile", (x, ey, z0 + 0.10),
                      (-sy * (math.pi / 2.0 + ang), 0, 0), mat, fid, ev)
                n_disc += 1
    else:
        ang = math.atan2(z1 - z0, w / 2.0)
        span = d * 0.94
        cnt = max(4, int(span / 0.46))
        for sx in (-1, 1):
            ex = cx + sx * (w / 2.0 + 0.03)
            band = fbox(bn + "_EaveBand", (cx + sx * (w / 2.0 - 0.05), cy, z0 + 0.17),
                        (0.22, span, 0.05), mat, fid, ev)
            band.rotation_euler.y = sx * ang
            for i in range(cnt + 1):
                y = cy - span / 2.0 + span * i / cnt
                fdisc(bn + "_EaveTile", (ex, y, z0 + 0.10),
                      (0, sx * (math.pi / 2.0 + ang), 0), mat, fid, ev)
                n_disc += 1
    n_roofs += 1
    if bn == "CHD_E1_Roof":
        e1_roof = (cx, cy, w, d, z0)
print("EAVE_TILE_DONE roofs=%d discs=%d" % (n_roofs, n_disc), flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v27.blend")
print("SAVED_V27", flush=True)

# ---------------------------------------------------------------- 確認描画
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
cam_data = bpy.data.cameras.new("V27Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V27Cam", cam_data)
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

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v27"
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
