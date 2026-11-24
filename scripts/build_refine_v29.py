"""豊楽殿の高欄スクリプト（部品v15、モデルv29）

使い方：
    blender --background heian_daidairi_detail_v28.blend \
        --python build_refine_v29.py

モデルv28を開き、豊楽殿の基壇に朱の高欄と擬宝珠を付けて
heian_daidairi_detail_v29.blend として保存する。確認画像つき。

内容（2026-11-23）：
- 高欄は大極殿（部品v5）と内裏の正殿3棟（部品v12）に付けたが、
  豊楽殿は基壇（49×25m・高さ1.5m、紫宸殿と同格）がありながら
  付いていなかった。同じ形式で付け、柱頭には部品v14と同じ
  擬宝珠（共有メッシュ GiboshiMesh）を載せた。
- 南面の中央は石段（幅10m）の分を開けた。
- 新規分は専用コレクション COL_16_ExteriorRefine12。

利用者の提案 docs/proposal/01_non-building-enrichment.md の
E1〜E10 には手をつけていない。
"""
import bpy
from mathutils import Vector

def base_name(o):
    n = o.name
    return n.rsplit(".", 1)[0] if "." in n and n.rsplit(".", 1)[1].isdigit() else n

def wbbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

ecol = bpy.data.collections.new("COL_16_ExteriorRefine12")
bpy.context.scene.collection.children.link(ecol)
ecol["layer"] = "exterior_refine_v15"

_cubes = {}
def fbox(name, loc, dims, mat, fid=""):
    key = mat.name if mat else "None"
    mesh = _cubes.get(key)
    if mesh is None:
        mesh = bpy.data.meshes.new("Refine12Cube_" + key)
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
    ecol.objects.link(ob)
    return ob

VERMILION = bpy.data.materials["MAT_Vermilion"]
GIB_MESH = bpy.data.meshes["GiboshiMesh"]
IN = 0.35
n_parts = 0

def railing_run(name, ax, fixed, a0, a1, ktop, fid):
    global n_parts
    length = a1 - a0
    if length < 0.6:
        return
    npost = max(2, int(round(length / 2.2)) + 1)
    for i in range(npost):
        t = a0 + length * i / (npost - 1)
        loc = (t, fixed, ktop + 0.475) if ax == "x" else (fixed, t, ktop + 0.475)
        fbox(name + "_RailPost", loc, (0.14, 0.14, 0.95), VERMILION, fid)
        gib = bpy.data.objects.new(name + "_RailPost_Giboshi", GIB_MESH)
        gib.location = (loc[0], loc[1], ktop + 0.94)
        gib["facility_id"] = fid
        ecol.objects.link(gib)
        n_parts += 2
    for rz, rh in ((ktop + 0.90, 0.10), (ktop + 0.50, 0.08)):
        if ax == "x":
            fbox(name + "_Rail", ((a0 + a1) / 2.0, fixed, rz), (length, 0.16, rh), VERMILION, fid)
        else:
            fbox(name + "_Rail", (fixed, (a0 + a1) / 2.0, rz), (0.16, length, rh), VERMILION, fid)
        n_parts += 1

kidan = None
for o in bpy.data.objects:
    if base_name(o) == "BURAKUDEN_Kidan":
        kidan = o
        break
kx0, kx1, ky0, ky1, kz0, ktop = wbbox(kidan)
cx = (kx0 + kx1) / 2.0
fid = kidan.get("facility_id", "BURAKUDEN")
railing_run("BURAKUDEN_KidanS1", "x", ky0 + IN, kx0 + IN, cx - 5.2, ktop, fid)
railing_run("BURAKUDEN_KidanS2", "x", ky0 + IN, cx + 5.2, kx1 - IN, ktop, fid)
railing_run("BURAKUDEN_KidanN", "x", ky1 - IN, kx0 + IN, kx1 - IN, ktop, fid)
railing_run("BURAKUDEN_KidanE", "y", kx1 - IN, ky0 + IN, ky1 - IN, ktop, fid)
railing_run("BURAKUDEN_KidanW", "y", kx0 + IN, ky0 + IN, ky1 - IN, ktop, fid)
print("BURAKU_RAIL_DONE parts=%d" % n_parts, flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v29.blend")
print("SAVED_V29", flush=True)

# ---------------------------------------------------------------- 確認描画
for c in bpy.data.collections:
    if c.name.startswith("COL_70"):
        c.hide_render = True
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
cam_data = bpy.data.cameras.new("V29Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V29Cam", cam_data)
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

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v29"
setup_cam((-236, 396, 3.6), (-283, 435, 2.4), lens=38)
render(OUT + "_buraku.png", 1280, 720, 48)
print("BURAKU_DONE", flush=True)
setup_cam((-262, 402, 2.6), (-280, 420, 2.2), lens=42)
render(OUT + "_rail.png", 1280, 720, 48)
print("RAIL_DONE", flush=True)
