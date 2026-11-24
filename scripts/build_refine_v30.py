"""門の石段と敷石スクリプト（部品v16、モデルv30）

使い方：
    blender --background heian_daidairi_detail_v29.blend \
        --python build_refine_v30.py

モデルv29を開き、門の基壇に石段と敷石を付けて
heian_daidairi_detail_v30.blend として保存する。確認画像つき。

内容（2026-11-23）：
- 通り抜けのある門26門（朝堂院3・内裏10・宮城12・羅城門）は
  いずれも高さ1.0mの基壇の上に建ち、扉も基壇の上面から始まって
  いるのに、基壇へ上がる段がなかった。通り抜けの両面に石段
  （3段）を付け、基壇の上の通り抜け部分に敷石を敷いた。
- 段の位置と幅は、各門の壁2枚の隙間（＝通り抜け）から求めた。
- 新規分は専用コレクション COL_17_ExteriorRefine13。

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

ecol = bpy.data.collections.new("COL_17_ExteriorRefine13")
bpy.context.scene.collection.children.link(ecol)
ecol["layer"] = "exterior_refine_v16"

_cubes = {}
def fbox(name, loc, dims, mat, fid=""):
    key = mat.name if mat else "None"
    mesh = _cubes.get(key)
    if mesh is None:
        mesh = bpy.data.meshes.new("Refine13Cube_" + key)
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

STONE = bpy.data.materials["MAT_Stone"]

byname = {}
for o in bpy.data.objects:
    byname.setdefault(base_name(o), []).append(o)

prefixes = sorted({base_name(o)[: -len("_Lintel")] for o in bpy.data.objects
                   if base_name(o).endswith("_Lintel")
                   and base_name(o).startswith(("CHD_", "DAIRI_", "GATE_", "LM_"))})
n_parts = 0
n_gates = 0
for p in prefixes:
    walls = byname.get(p + "_Wall", [])
    kidans = byname.get(p + "_Kidan", [])
    if len(walls) != 2 or not kidans:
        print("SKIP", p, len(walls), len(kidans), flush=True)
        continue
    kidan = kidans[0]
    kx0, kx1, ky0, ky1, kz0, ktop = wbbox(kidan)
    wa, wb = wbbox(walls[0]), wbbox(walls[1])
    fid = kidan.get("facility_id", p)
    if wa[1] <= wb[0] or wb[1] <= wa[0]:
        # 隙間はX方向 → 通り抜けはY方向
        lo, hi = (wa, wb) if wa[1] <= wb[0] else (wb, wa)
        pc = (lo[1] + hi[0]) / 2.0
        pw = hi[0] - lo[1]
        fbox(p + "_PassPave", (pc, (ky0 + ky1) / 2.0, ktop + 0.04),
             (pw + 0.4, ky1 - ky0, 0.08), STONE, fid)
        n_parts += 1
        for face, fy in ((-1, ky0), (1, ky1)):
            for i in range(3):
                top = 0.75 - 0.25 * i
                yc = fy + face * (0.225 + 0.45 * i)
                fbox(p + "_PassStep", (pc, yc, top / 2.0), (pw, 0.45, top), STONE, fid)
                n_parts += 1
    elif wa[3] <= wb[2] or wb[3] <= wa[2]:
        # 隙間はY方向 → 通り抜けはX方向
        lo, hi = (wa, wb) if wa[3] <= wb[2] else (wb, wa)
        pc = (lo[3] + hi[2]) / 2.0
        pw = hi[2] - lo[3]
        fbox(p + "_PassPave", ((kx0 + kx1) / 2.0, pc, ktop + 0.04),
             (kx1 - kx0, pw + 0.4, 0.08), STONE, fid)
        n_parts += 1
        for face, fx in ((-1, kx0), (1, kx1)):
            for i in range(3):
                top = 0.75 - 0.25 * i
                xc = fx + face * (0.225 + 0.45 * i)
                fbox(p + "_PassStep", (xc, pc, top / 2.0), (0.45, pw, top), STONE, fid)
                n_parts += 1
    else:
        print("NOGAP", p, flush=True)
        continue
    n_gates += 1
print("GATE_STEPS_DONE gates=%d parts=%d" % (n_gates, n_parts), flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v30.blend")
print("SAVED_V30", flush=True)

# ---------------------------------------------------------------- 確認描画
for c in bpy.data.collections:
    if c.name.startswith("COL_70"):
        c.hide_render = True
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
cam_data = bpy.data.cameras.new("V30Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V30Cam", cam_data)
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

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v30"
setup_cam((10, -17, 1.7), (0, 3, 1.7), lens=38)
render(OUT + "_suzaku.png", 1280, 720, 48)
print("SUZAKU_DONE", flush=True)
setup_cam((9, 158, 1.9), (0, 184, 1.7), lens=38)
render(OUT + "_oten.png", 1280, 720, 48)
print("OTEN_DONE", flush=True)
