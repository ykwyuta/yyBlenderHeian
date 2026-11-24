"""殿舎の出入口の石段スクリプト（部品v18、モデルv32）

使い方：
    blender --background heian_daidairi_detail_v31.blend \
        --python build_refine_v32.py

モデルv31を開き、殿舎の扉の前に石段を付けて
heian_daidairi_detail_v32.blend として保存する。確認画像つき。

内容（2026-11-24）：
- 部品v6（v18）で付けた殿舎の扉は、土台（高さ0.4m前後）の上に
  ありながら、上がる段がない棟が多かった。扉の前に石段を付けた
  （段数は扉の床の高さから、1段あたり約0.26mで割って決めた）。
- すでに石段のある扉（正殿級の南面など、近くに Step を含む名の
  オブジェクトがある場合）は対象外。地面の高さの扉も対象外。
- 段の位置・向き・幅は各扉の実測bboxと殿舎の平面（基壇→土台→
  壁の順に参照）から求めた。
- 新規分は専用コレクション COL_19_ExteriorRefine15。
  CONJ_分には evidence=conjectural を引き継いだ。

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

ecol = bpy.data.collections.new("COL_19_ExteriorRefine15")
bpy.context.scene.collection.children.link(ecol)
ecol["layer"] = "exterior_refine_v18"

_cubes = {}
def fbox(name, loc, dims, mat, fid="", evidence=None):
    key = mat.name if mat else "None"
    mesh = _cubes.get(key)
    if mesh is None:
        mesh = bpy.data.meshes.new("Refine15Cube_" + key)
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

STONE = bpy.data.materials["MAT_Stone"]

byname = {}
for o in bpy.data.objects:
    byname.setdefault(base_name(o), []).append(o)

def footprint(prefix):
    """殿舎の平面（基壇→土台→壁→屋根の順）。中心と外形を返す。"""
    for suf in ("_Kidan", "_Base", "_Wall", "_Roof",
                "_WallS", "_WallN", "_WallE", "_WallW"):
        objs = byname.get(prefix + suf, [])
        if objs:
            return wbbox(objs[0])
    return None

step_centers = []
for o in bpy.data.objects:
    if "Step" in base_name(o):
        b = wbbox(o)
        step_centers.append(((b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0))

n_doors = 0
n_parts = 0
first_step = None
for o in list(bpy.data.objects):
    bn = base_name(o)
    if not bn.endswith("_OpenDoor"):
        continue
    prefix = bn[: -len("_OpenDoor")]
    fp = footprint(prefix)
    if fp is None:
        print("NOFOOT", bn, flush=True)
        continue
    fx0, fx1, fy0, fy1, fz0, fz1 = fp
    wcx, wcy = (fx0 + fx1) / 2.0, (fy0 + fy1) / 2.0
    x0, x1, y0, y1, z0, z1 = wbbox(o)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    w, d = x1 - x0, y1 - y0
    if z0 < 0.15:
        continue
    if any((sx - cx) ** 2 + (sy - cy) ** 2 < 2.2 ** 2 for sx, sy in step_centers):
        continue
    fid = o.get("facility_id", "")
    ev = o.get("evidence")
    nsteps = max(1, int(round(z0 / 0.26)) - 1) if z0 > 0.3 else 1
    if w >= d:
        axis = "y"
        sgn = 1 if cy >= wcy else -1
        edge = fy1 if sgn > 0 else fy0
        width = w + 0.3
        for i in range(nsteps):
            top = z0 * (nsteps - i) / (nsteps + 1) if nsteps > 1 else z0 * 0.55
            yc = edge + sgn * (0.21 + 0.42 * i)
            fbox(bn + "_DoorStep", (cx, yc, top / 2.0), (width, 0.42, top), STONE, fid, ev)
            n_parts += 1
        if first_step is None:
            first_step = (cx, cy, 0.0, sgn, z0)
    else:
        axis = "x"
        sgn = 1 if cx >= wcx else -1
        edge = fx1 if sgn > 0 else fx0
        width = d + 0.3
        for i in range(nsteps):
            top = z0 * (nsteps - i) / (nsteps + 1) if nsteps > 1 else z0 * 0.55
            xc = edge + sgn * (0.21 + 0.42 * i)
            fbox(bn + "_DoorStep", (xc, cy, top / 2.0), (0.42, width, top), STONE, fid, ev)
            n_parts += 1
        if first_step is None:
            first_step = (cx, cy, sgn, 0.0, z0)
    n_doors += 1
print("DOOR_STEPS_DONE doors=%d parts=%d" % (n_doors, n_parts), flush=True)
print("FIRST_STEP", first_step, flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v32.blend")
print("SAVED_V32", flush=True)

# ---------------------------------------------------------------- 確認描画
for c in bpy.data.collections:
    if c.name.startswith("COL_70"):
        c.hide_render = True
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
cam_data = bpy.data.cameras.new("V32Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V32Cam", cam_data)
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

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v32"
if first_step:
    dx, dy, sx, sy, fz = first_step
    setup_cam((dx + sx * 8 + 3.5, dy + sy * 8 - 3.5, fz + 1.5),
              (dx, dy, fz + 0.3), lens=42)
    render(OUT + "_door.png", 1280, 720, 48)
    print("DOOR_DONE", flush=True)
setup_cam((430, 60, 330), (0, 640, 0), lens=35)
render(OUT + "_top.png", 1400, 1400, 24)
print("TOP_DONE", flush=True)
