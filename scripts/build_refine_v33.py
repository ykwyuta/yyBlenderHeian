"""中和院・真言院の内部スクリプト（部品v19、モデルv33）

使い方：
    blender --background heian_daidairi_detail_v32.blend \
        --python build_refine_v33.py

モデルv32を開き、中和院・真言院の主殿と脇殿の内部を作って
heian_daidairi_detail_v33.blend として保存する。確認画像つき。

内容（2026-11-24）：
- 内裏・後宮・大極殿・豊楽殿・朝堂院の内部は部品v8・v11・v19で
  作ったが、中和院（神嘉殿）・真言院の4棟は壁が実体の箱のまま
  だった。壁を厚さ0.35mの4枚パネルに置き換えて空洞化し、床を
  入れた。外観は変わらない。
- 主殿2棟には模式の調度を置いた（evidence=schematic_interior）。
  神嘉殿：北端の壇・卓・燭台2基・畳の敷物。真言院：北端の須弥壇・
  八角の台座・小さい金像・卓・燭台2基・畳の敷物。脇殿2棟は
  床のみの空の間（朝堂院と同じ扱い）。
- 内部は COL_90_Interior に入れる。壁の空洞化は部品v8と同じ
  方式（パネル名は _WallN/_WallS/_WallE/_WallW）。

利用者の提案 docs/proposal/01_non-building-enrichment.md の
E1〜E10 には手をつけていない。
"""
import bpy
import importlib.util
import math
from mathutils import Vector

spec = importlib.util.spec_from_file_location(
    "build_detail",
    "/home/hatch/docs/proposal/history/3d/heiankyo-blender/scripts/build_chodoin_detailed.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

M = {
    "vermilion": bpy.data.materials["MAT_Vermilion"],
    "white": bpy.data.materials["MAT_WhiteWall"],
    "wood": bpy.data.materials["MAT_WoodDark"],
    "light": bpy.data.materials["MAT_WoodLight"],
    "tatami": bpy.data.materials["MAT_Tatami"],
    "curtain": bpy.data.materials["MAT_Curtain"],
    "lacquer": bpy.data.materials["MAT_LacquerBlack"],
    "paper": bpy.data.materials["MAT_PaperPanel"],
    "gold": bpy.data.materials["MAT_Gold"],
    "stone": bpy.data.materials["MAT_Stone"],
}

def base_name(o):
    n = o.name
    return n.rsplit(".", 1)[0] if "." in n and n.rsplit(".", 1)[1].isdigit() else n

def world_bbox(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))

icol = mod.get_or_make_collection("COL_90_Interior")
CUR = {"cx": 0.0, "cy": 0.0, "fz": 0.0, "fid": "", "tag": ""}

def FB(name, loc, dims, mat_key):
    return mod.fast_box(CUR["tag"] + "_" + name, loc, dims, M[mat_key], icol, CUR["fid"])

def P(name, u, v, du, dv, h, mat_key, z0=0.0):
    return FB(name, (CUR["cx"] + u, CUR["cy"] + v, CUR["fz"] + z0 + h / 2.0),
              (du, dv, h), mat_key)

def cyl(name, u, v, r, h, mat_key, z0=0.0):
    ob = mod.add_cylinder(CUR["tag"] + "_" + name,
                          (CUR["cx"] + u, CUR["cy"] + v, CUR["fz"] + z0 + h / 2.0),
                          r, h, M[mat_key], icol)
    ob["facility_id"] = CUR["fid"]
    return ob

def oct_prism(name, u, v, r, h, mat_key, z0=0.0):
    verts = []
    for zz in (0.0, h):
        for k in range(8):
            a = 2 * math.pi * k / 8 + math.pi / 8
            verts.append((r * math.cos(a), r * math.sin(a), zz))
    faces = []
    for k in range(8):
        k2 = (k + 1) % 8
        faces.append((k, k2, 8 + k2, 8 + k))
    faces.append(tuple(range(7, -1, -1)))
    faces.append(tuple(range(8, 16)))
    mesh = bpy.data.meshes.new(CUR["tag"] + "_" + name + "Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.materials.append(M[mat_key])
    ob = bpy.data.objects.new(CUR["tag"] + "_" + name, mesh)
    ob.location = (CUR["cx"] + u, CUR["cy"] + v, CUR["fz"] + z0)
    ob["facility_id"] = CUR["fid"]
    icol.objects.link(ob)
    return ob

def hall_frame(token):
    xs0, xs1, ys0, ys1, zs0 = [], [], [], [], []
    for ob in bpy.data.objects:
        if token in ob.name and "_Wall" in ob.name:
            (ax0, ax1), (ay0, ay1), (az0, az1) = world_bbox(ob)
            xs0.append(ax0); xs1.append(ax1)
            ys0.append(ay0); ys1.append(ay1)
            zs0.append(az0)
    x0, x1, y0, y1, z0 = min(xs0), max(xs1), min(ys0), max(ys1), min(zs0)
    return {"cx": (x0 + x1) / 2.0, "cy": (y0 + y1) / 2.0,
            "hu": (x1 - x0) / 2.0 - 0.45, "hv": (y1 - y0) / 2.0 - 0.45, "fz": z0}

def hollow_walls(token):
    wall = None
    for ob in bpy.data.objects:
        if token in ob.name and ob.name.endswith("_Wall"):
            wall = ob
            break
    (x0, x1), (y0, y1), (z0, z1) = world_bbox(wall)
    hcol = wall.users_collection[0]
    fid = wall.get("facility_id", "")
    prefix = wall.name[: -len("_Wall")]
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
        mod.fast_box(prefix + suffix, loc, dims, M["white"], hcol, fid)

def begin(token, fid, tag):
    fr = hall_frame(token)
    hollow_walls(token)
    CUR.update(fr)
    CUR["fid"] = fid
    CUR["tag"] = tag
    P("Floor", 0, 0, fr["hu"] * 2 - 0.1, fr["hv"] * 2 - 0.1, 0.06, "light")
    return fr

def finish(evidence):
    for ob in icol.objects:
        if ob.name.startswith(CUR["tag"] + "_"):
            ob["evidence"] = evidence

def candle(u, v):
    cyl("Candle", u, v, 0.09, 0.9, "gold", z0=0.35)
    cyl("CandleBowl", u, v, 0.16, 0.06, "gold", z0=1.22)

BEFORE = len(icol.objects)

# 中和院 神嘉殿：壇と卓と燭台
fr = begin("CHUKAIN_Main", "CHUKAIN", "INT_CHUKAIN")
hv = fr["hv"]
P("Dais", 0, hv - 2.2, 5.0, 3.0, 0.35, "lacquer")
P("Table", 0, hv - 2.2, 1.8, 0.9, 0.55, "wood", z0=0.35)
candle(-2.4, hv - 2.2)
candle(2.4, hv - 2.2)
P("Runner", 0, 0, 2.4, hv * 2 - 3.5, 0.05, "tatami", z0=0.06)
finish("schematic_interior")
print("CHUKAIN_DONE", flush=True)

# 真言院：須弥壇と金像
fr = begin("SHINGONIN_Main", "SHINGONIN", "INT_SHINGONIN")
hv = fr["hv"]
P("Altar", 0, hv - 2.0, 4.5, 2.5, 0.5, "lacquer")
oct_prism("Pedestal", 0, hv - 2.0, 0.7, 0.9, "gold", z0=0.5)
P("Image", 0, hv - 2.0, 0.55, 0.3, 0.8, "gold", z0=1.4)
P("Table", 0, hv - 4.6, 1.6, 0.8, 0.5, "wood")
candle(-2.4, hv - 2.0)
candle(2.4, hv - 2.0)
P("Runner", 0, 0, 2.4, hv * 2 - 3.5, 0.05, "tatami", z0=0.06)
finish("schematic_interior")
print("SHINGONIN_DONE", flush=True)

# 脇殿2棟：床のみの空の間
for token, tag in (("CHUKAIN_Side", "INT_CHUKAIN_SIDE"),
                   ("SHINGONIN_Side", "INT_SHINGONIN_SIDE")):
    begin(token, token, tag)
    finish("schematic_interior")
print("SIDES_DONE added=%d" % (len(icol.objects) - BEFORE), flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v33.blend")
print("SAVED_V33", flush=True)

# ---------------------------------------------------------------- 確認描画
for c in bpy.data.collections:
    if c.name.startswith("COL_70"):
        c.hide_render = True
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"

def hide_roof(token):
    for ob in bpy.data.objects:
        if token in ob.name and "_Roof" in ob.name:
            ob.hide_render = True

def show_roof(token):
    for ob in bpy.data.objects:
        if token in ob.name and "_Roof" in ob.name:
            ob.hide_render = False

cam_data = bpy.data.cameras.new("V33Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V33Cam", cam_data)
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

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v33"
fr = hall_frame("CHUKAIN_Main")
hide_roof("CHUKAIN_Main")
setup_cam((fr["cx"], fr["cy"] - 7.0, fr["fz"] + 2.8),
          (fr["cx"], fr["cy"] + 4.0, fr["fz"] + 1.8), lens=29)
render(OUT + "_chukain_room.png", 1280, 720, 48)
print("CHUKAIN_ROOM_DONE", flush=True)
fr = hall_frame("SHINGONIN_Main")
hide_roof("SHINGONIN_Main")
setup_cam((fr["cx"], fr["cy"] - 7.0, fr["fz"] + 2.8),
          (fr["cx"], fr["cy"] + 4.0, fr["fz"] + 1.8), lens=29)
render(OUT + "_shingonin_room.png", 1280, 720, 48)
print("SHINGONIN_ROOM_DONE", flush=True)
show_roof("CHUKAIN_Main")
show_roof("SHINGONIN_Main")
setup_cam((60, 688, 3.2), (60, 722, 4.6), lens=35)
render(OUT + "_chukain.png", 1280, 720, 48)
print("CHUKAIN_DONE", flush=True)
