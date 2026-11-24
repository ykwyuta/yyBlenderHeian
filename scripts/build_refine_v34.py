"""残りの殿舎の内部スクリプト（部品v20、モデルv34）

使い方：
    blender --background heian_daidairi_detail_v33.blend \
        --python build_refine_v34.py

モデルv33を開き、壁が実体の箱のまま残っていた殿舎28棟を
空洞化して床を入れ、heian_daidairi_detail_v34.blend として
保存する。確認画像つき。

内容（2026-11-24）：
- 内部の作り込みは内裏・後宮・大極殿・朝堂院・中和院・真言院
  まで進んでいたが、官衙の庁舎・内酒殿・朝堂院の脇殿・推定
  レイヤーの殿舎・寺院の堂など28棟は壁が実体の箱のままだった。
  部品v8・v19と同じ方式で、壁を厚さ0.35mの4枚パネルに置き
  換えて空洞化し、床を入れた（調度は置かない）。外観は変わ
  らない。
- 床は COL_90_Interior に入れ、evidence=schematic_interior
  （推定レイヤーの棟は evidence=conjectural）を付けた。壁
  パネルは元の壁の素材・所属・属性を引き継ぐ。
- 内裏の囲い（DAIRI_SURROUND_Main）は部屋ではないため対象外。
  市街の建物も対象外。

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

icol = bpy.data.collections.get("COL_90_Interior")
if icol is None:
    icol = bpy.data.collections.new("COL_90_Interior")
    bpy.context.scene.collection.children.link(icol)

_cubes = {}
def fbox(name, loc, dims, mat, col, fid="", evidence=None):
    key = (mat.name if mat else "None") + "@" + col.name
    mesh = _cubes.get(key)
    if mesh is None:
        mesh = bpy.data.meshes.new("Refine34Cube_" + key)
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
    col.objects.link(ob)
    return ob

WOOD = bpy.data.materials["MAT_WoodDark"]

TARGETS = [
    "CHD_SEIHO", "CHD_SHORAN", "CHUKAIN_Side", "CHUMUSHO_Main",
    "CONJ_BURAKU_EAST", "CONJ_BURAKU_SOUTH", "CONJ_BURAKU_STORE_N1",
    "CONJ_BURAKU_STORE_N2", "CONJ_BURAKU_STORE_N3", "CONJ_BURAKU_WEST",
    "CONJ_CHD_SHOANDEN", "CONJ_DAIRI_ANPUKU", "CONJ_DAIRI_KORYO",
    "CONJ_DAIRI_KURANDO", "CONJ_DAIRI_SHUNKO", "CONJ_KUNAISHŌ_Main",
    "GOV_E_GUARD_Main", "GOV_SE_ADMIN_Main", "GOV_SW_POLICE_Main",
    "GOV_W_GUARD_Main", "JINGIKAN_Main", "LM_SAIJI_Hall",
    "LM_SHINSENEN_Hall", "LM_TOJI_Hall", "SHINGONIN_Side",
    "SHUISUSHI_Main", "TOGU_GAIN_Main", "UCHISAKEDONO",
]

byname = {}
for o in bpy.data.objects:
    byname.setdefault(base_name(o), []).append(o)

n_halls = 0
largest = None
for prefix in TARGETS:
    walls = byname.get(prefix + "_Wall", [])
    if len(walls) != 1:
        print("SKIP", prefix, len(walls), flush=True)
        continue
    wall = walls[0]
    x0, x1, y0, y1, z0, z1 = wbbox(wall)
    hcol = wall.users_collection[0]
    fid = wall.get("facility_id", "")
    wev = wall.get("evidence")
    mat = wall.data.materials[0] if wall.data.materials else None
    bpy.data.objects.remove(wall, do_unlink=True)
    t = 0.35
    cz = (z0 + z1) / 2.0
    hh = z1 - z0
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    panels = [
        ("_WallN", (cx, y1 - t / 2.0, cz), (x1 - x0, t, hh)),
        ("_WallS", (cx, y0 + t / 2.0, cz), (x1 - x0, t, hh)),
        ("_WallE", (x1 - t / 2.0, cy, cz), (t, (y1 - y0) - 2 * t, hh)),
        ("_WallW", (x0 + t / 2.0, cy, cz), (t, (y1 - y0) - 2 * t, hh)),
    ]
    for suffix, loc, dims in panels:
        fbox(prefix + suffix, loc, dims, mat, hcol, fid, wev)
    ev = "conjectural" if prefix.startswith("CONJ_") else "schematic_interior"
    fbox("INT_" + prefix.split("_")[-1] + "_Floor_" + prefix,
         (cx, cy, z0 + 0.03), ((x1 - x0) - 0.8, (y1 - y0) - 0.8, 0.06),
         WOOD, icol, fid, ev)
    n_halls += 1
    area = (x1 - x0) * (y1 - y0)
    if largest is None or area > largest[0]:
        largest = (area, cx, cy, (y1 - y0) / 2.0, z0, prefix)
print("HOLLOW_DONE halls=%d" % n_halls, flush=True)
print("LARGEST", largest, flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v34.blend")
print("SAVED_V34", flush=True)

# ---------------------------------------------------------------- 確認描画
for c in bpy.data.collections:
    if c.name.startswith("COL_70"):
        c.hide_render = True
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
cam_data = bpy.data.cameras.new("V34Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V34Cam", cam_data)
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

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v34"
if largest:
    _, cx, cy, hv, fz, pname = largest
    setup_cam((cx, cy - hv * 0.45, fz + 1.5), (cx, cy + hv, fz + 1.2), lens=30)
    render(OUT + "_room.png", 1280, 720, 48)
    print("ROOM_DONE", pname, flush=True)
setup_cam((430, 60, 330), (0, 640, 0), lens=35)
render(OUT + "_top.png", 1400, 1400, 24)
print("TOP_DONE", flush=True)
