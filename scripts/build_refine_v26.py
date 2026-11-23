"""内裏の正殿の高欄スクリプト（部品v12、モデルv26）

使い方：
    blender --background heian_daidairi_detail_v25.blend \
        --python build_refine_v26.py

モデルv25を開き、内裏の正殿級3棟の基壇に朱の高欄を付けて
heian_daidairi_detail_v26.blend として保存する。確認画像つき。

内容（2026-11-23）：
- 基壇の高欄はこれまで大極殿（部品v5）にだけ付いていた。同じ
  形式（基壇の縁に沿う朱の柱と2段の横木、南面中央は石段の分を
  開ける）を、基壇のある内裏の正殿級3棟――紫宸殿（基壇高1.5m）・
  清涼殿・仁寿殿（同1.0m）――にも付けた。
- 飛香舎は基壇を持たない（土台のみ）ため対象外。
- 新規分は専用コレクション COL_13_ExteriorRefine9。

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

ecol = bpy.data.collections.new("COL_13_ExteriorRefine9")
bpy.context.scene.collection.children.link(ecol)
ecol["layer"] = "exterior_refine_v12"

_cubes = {}
def fbox(name, loc, dims, mat, fid=""):
    key = mat.name if mat else "None"
    mesh = _cubes.get(key)
    if mesh is None:
        mesh = bpy.data.meshes.new("Refine9Cube_" + key)
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
IN = 0.35
n_rail = 0

def railing_run(name, ax, fixed, a0, a1, ktop, fid):
    global n_rail
    length = a1 - a0
    if length < 0.6:
        return
    npost = max(2, int(round(length / 2.2)) + 1)
    for i in range(npost):
        t = a0 + length * i / (npost - 1)
        loc = (t, fixed, ktop + 0.475) if ax == "x" else (fixed, t, ktop + 0.475)
        fbox(name + "_RailPost", loc, (0.14, 0.14, 0.95), VERMILION, fid)
        n_rail += 1
    for rz, rh in ((ktop + 0.90, 0.10), (ktop + 0.50, 0.08)):
        if ax == "x":
            fbox(name + "_Rail", ((a0 + a1) / 2.0, fixed, rz), (length, 0.16, rh), VERMILION, fid)
        else:
            fbox(name + "_Rail", (fixed, (a0 + a1) / 2.0, rz), (0.16, length, rh), VERMILION, fid)
        n_rail += 1

HALLS = {"DAIRI_SHISHINDEN": "DAIRI_SHISHINDEN",
         "DAIRI_SEIRYODEN": "DAIRI_SEIRYODEN",
         "DAIRI_JIJU_JOKYO": "DAIRI_JIJU_JOKYO"}
for prefix, fid in HALLS.items():
    kidan = None
    for o in bpy.data.objects:
        if base_name(o) == prefix + "_Kidan":
            kidan = o
            break
    if kidan is None:
        print("NOKIDAN", prefix, flush=True)
        continue
    kx0, kx1, ky0, ky1, kz0, ktop = wbbox(kidan)
    cx = (kx0 + kx1) / 2.0
    railing_run(prefix + "_KidanS1", "x", ky0 + IN, kx0 + IN, cx - 1.7, ktop, fid)
    railing_run(prefix + "_KidanS2", "x", ky0 + IN, cx + 1.7, kx1 - IN, ktop, fid)
    railing_run(prefix + "_KidanN", "x", ky1 - IN, kx0 + IN, kx1 - IN, ktop, fid)
    railing_run(prefix + "_KidanE", "y", kx1 - IN, ky0 + IN, ky1 - IN, ktop, fid)
    railing_run(prefix + "_KidanW", "y", kx0 + IN, ky0 + IN, ky1 - IN, ktop, fid)
print("RAIL2_DONE parts=%d" % n_rail, flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v26.blend")
print("SAVED_V26", flush=True)

# ---------------------------------------------------------------- 確認描画
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
cam_data = bpy.data.cameras.new("V26Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V26Cam", cam_data)
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

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v26"
setup_cam((313, 705, 3.4), (281, 741, 2.2), lens=38)
render(OUT + "_shishin.png", 1280, 720, 64)
print("SHISHIN_DONE", flush=True)
setup_cam((265, 747, 3.0), (239, 777, 1.9), lens=38)
render(OUT + "_seiryo.png", 1280, 720, 64)
print("SEIRYO_DONE", flush=True)
setup_cam((430, 60, 330), (0, 640, 0), lens=35)
render(OUT + "_top.png", 1600, 1600, 32)
print("TOP_DONE", flush=True)
