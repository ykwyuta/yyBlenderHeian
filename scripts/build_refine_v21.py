"""残りの殿舎の仕上げスクリプト（部品v8、モデルv21）

使い方：
    blender --background heian_daidairi_detail_v20.blend \
        --python build_refine_v21.py

モデルv20を開き、次を追加して heian_daidairi_detail_v21.blend
として保存する。確認画像つき。

内容（2026-11-22）：
- **大極殿の内部**：最も重要な殿舎だけ内部がなかったため、壁を
  空洞化し、床と高御座（紫宸殿の例に倣う模式、evidence=
  schematic_interior）と茵の敷物を入れた。提案 E7 の儀式の装置
  （宝幢・四神旗など屋外の仮設）とは別の、建物の常設の調度として
  扱う。
- **豊楽殿・朝堂院の内部**：豊楽殿と朝堂12堂・朝集堂・小安殿も
  壁を空洞化し、床を入れた（調度は置かない空の間）。
- **組物・礎石の展開**：部品v7で主要殿舎21棟に付けた組物と礎石を、
  後宮11棟・中和院・真言院の6棟・内酒殿にも広げた。小さい殿舎
  向けに組物は0.8倍に縮小した。新規分は専用コレクション
  COL_09_ExteriorRefine5。

利用者の提案 docs/proposal/01_non-building-enrichment.md（建築物
以外の要素）の E1〜E10 には手をつけていない。内部は
COL_90_Interior に入れ、壁の空洞化は外形を変えない。
"""
import bpy
import importlib.util
import math
from mathutils import Vector
from collections import defaultdict

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

def wbbox(o):
    (x0, x1), (y0, y1), (z0, z1) = world_bbox(o)
    return (x0, x1, y0, y1, z0, z1)

# ================================================================ 内部
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

def takamikura(name, u, v, s):
    """高御座（v11の紫宸殿と同じ部品）。s は縮尺。"""
    oct_prism(name + "_Base", u, v, 2.25 * s, 0.55, "lacquer")
    for k in range(8):
        a = 2 * math.pi * k / 8 + math.pi / 8
        cyl(name + "_Post%d" % k, u + 1.85 * s * math.cos(a), v + 1.85 * s * math.sin(a),
            0.08, 3.9 * s, "lacquer", z0=0.55)
    for k in range(8):
        a = 2 * math.pi * k / 8 + math.pi / 8
        if -0.6 < math.sin(a) < 0.0 or math.sin(a) < -0.85:
            continue
        uu = u + 1.92 * s * math.cos(a)
        vv = v + 1.92 * s * math.sin(a)
        ob = P(name + "_Curtain%d" % k, uu, vv, 0.1, 0.1, 0.1, "curtain")
        ob.location = (CUR["cx"] + uu, CUR["cy"] + vv, CUR["fz"] + 0.75 + 1.55 * s)
        ob.scale = (1.42 * s, 0.05, 3.1 * s)
        ob.rotation_euler.z = -a + math.pi / 2
    P(name + "_Chair", u, v + 0.3 * s, 0.95 * s, 0.8 * s, 0.5, "lacquer", z0=0.55)
    P(name + "_ChairBack", u, v + 0.62 * s, 0.95 * s, 0.1, 1.1, "lacquer", z0=1.05)
    oct_prism(name + "_Canopy", u, v, 2.55 * s, 0.4, "lacquer", z0=4.45 * s)
    oct_prism(name + "_Cap", u, v, 1.1 * s, 0.5, "lacquer", z0=4.85 * s)
    FB(name + "_Phoenix", (CUR["cx"] + u, CUR["cy"] + v, CUR["fz"] + 5.55 * s),
       (0.34, 0.2, 0.5), "gold")
    P(name + "_Step1", u, v - 2.5 * s, 1.6 * s, 0.5, 0.2, "wood")
    P(name + "_Step2", u, v - 2.15 * s, 1.6 * s, 0.4, 0.38, "wood")

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

BEFORE = len(icol.objects)

# 大極殿：高御座のある内部
fr = begin("CHD_Daigokuden", "CHD_DAIGOKUDEN", "INT_DAIGOKU")
takamikura("Takamikura", 0.0, 3.2, 1.25)
P("Runner", 0, -4.4, 2.6, 9.5, 0.05, "tatami", z0=0.06)
finish("schematic_interior")
print("DAIGOKU_DONE", flush=True)

# 豊楽殿と朝堂院：空の間
EMPTY = [("BURAKUDEN", "INT_BURAKU"),
         ("CHD_CHOSHUDO_E", "INT_CHOSHU_E"), ("CHD_CHOSHUDO_W", "INT_CHOSHU_W"),
         ("CHD_KOANDEN", "INT_KOAN")]
EMPTY += [("CHD_E%d" % i, "INT_CHD_E%d" % i) for i in range(1, 7)]
EMPTY += [("CHD_W%d" % i, "INT_CHD_W%d" % i) for i in range(1, 7)]
for token, tag in EMPTY:
    begin(token, token, tag)
    finish("schematic_interior")
print("EMPTY_DONE added=%d" % (len(icol.objects) - BEFORE), flush=True)

# ================================================================ 組物・礎石の展開
ecol = bpy.data.collections.get("COL_09_ExteriorRefine5")
if ecol is None:
    ecol = bpy.data.collections.new("COL_09_ExteriorRefine5")
    bpy.context.scene.collection.children.link(ecol)
ecol["layer"] = "exterior_refine_v8"
for _ob in list(ecol.objects):
    bpy.data.objects.remove(_ob, do_unlink=True)

_cubes = {}
def fbox(name, loc, dims, mat, fid=""):
    key = mat.name if mat else "None"
    mesh = _cubes.get(key)
    if mesh is None:
        mesh = bpy.data.meshes.new("Refine5Cube_" + key)
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

WOOD = bpy.data.materials["MAT_WoodDark"]
STONE = bpy.data.materials["MAT_Stone"]

HALLS = ["DAIRI_GYOKASHA", "DAIRI_KOKIDEN", "DAIRI_REIKEIDEN",
         "DAIRI_SHUKUKEISHA", "DAIRI_SHOYOSHA", "DAIRI_SHUHOSHA",
         "DAIRI_JONEIDEN", "DAIRI_JOGANDEN", "DAIRI_TOKADEN",
         "DAIRI_SENYODEN", "DAIRI_SHOKADEN",
         "CHUKAIN_Main", "CHUKAIN_Side", "SHINGONIN_Main", "SHINGONIN_Side",
         "UCHISAKEDONO"]
S = 0.8   # 小さい殿舎向けの縮尺

cols_by = defaultdict(list)
for o in bpy.data.objects:
    bn = base_name(o)
    if bn.endswith("_Col"):
        cols_by[bn[:-4]].append(o)

def clusters(boxes):
    """接頭辞を共有する複数棟（中和院の脇殿など）を柱の近さで分ける"""
    pts = [((b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0, b) for b in boxes]
    groups = []
    for px, py, b in pts:
        for g in groups:
            gx = sum(p[0] for p in g) / len(g)
            gy = sum(p[1] for p in g) / len(g)
            if abs(px - gx) < 16 and abs(py - gy) < 16:
                g.append((px, py, b))
                break
        else:
            groups.append([(px, py, b)])
    return [[p[2] for p in g] for g in groups]

n_bracket = 0
n_soseki = 0
for prefix in HALLS:
    cols = cols_by.get(prefix, [])
    if not cols:
        print("NOCOLS", prefix, flush=True)
        continue
    fid = cols[0].get("facility_id", "")
    for boxes in clusters([wbbox(o) for o in cols]):
     cx = sum((b[0] + b[1]) / 2.0 for b in boxes) / len(boxes)
     cy = sum((b[2] + b[3]) / 2.0 for b in boxes) / len(boxes)
     hx = max(abs((b[0] + b[1]) / 2.0 - cx) for b in boxes)
     hy = max(abs((b[2] + b[3]) / 2.0 - cy) for b in boxes)
     seen = set()
     for b in boxes:
        px, py = (b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0
        key = (round(px, 1), round(py, 1))
        if key in seen:
            continue
        seen.add(key)
        z0, z1 = b[4], b[5]
        dx, dy = px - cx, py - cy
        on_x_face = abs(dy) > hy - 1.0
        on_y_face = abs(dx) > hx - 1.0
        fbox(prefix + "_Soseki", (px, py, z0 + 0.03), (0.5, 0.5, 0.16), STONE, fid)
        n_soseki += 1
        fbox(prefix + "_BracketLow", (px, py, z1 - 0.57 * S), (0.36 * S, 0.36 * S, 0.18 * S), WOOD, fid)
        fbox(prefix + "_BracketMid", (px, py, z1 - 0.37 * S), (0.46 * S, 0.46 * S, 0.22 * S), WOOD, fid)
        if on_x_face:
            fbox(prefix + "_BracketArmX", (px, py, z1 - 0.13 * S), (1.15 * S, 0.26 * S, 0.26 * S), WOOD, fid)
            n_bracket += 1
        if on_y_face:
            fbox(prefix + "_BracketArmY", (px, py, z1 - 0.13 * S), (0.26 * S, 1.15 * S, 0.26 * S), WOOD, fid)
            n_bracket += 1
        n_bracket += 2
print("BRACKET2_DONE brackets=%d soseki=%d" % (n_bracket, n_soseki), flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v21.blend")
print("SAVED_V21", flush=True)

# ---------------------------------------------------------------- 確認描画
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"

def hide_roof(token):
    for ob in bpy.data.objects:
        if token in ob.name and "_Roof" in ob.name:
            ob.hide_render = True

cam_data = bpy.data.cameras.new("V21Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V21Cam", cam_data)
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

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v21"
fr = hall_frame("CHD_Daigokuden")
hide_roof("CHD_Daigokuden")
setup_cam((fr["cx"], fr["cy"] - 7.0, fr["fz"] + 2.6),
          (fr["cx"], fr["cy"] + 5.0, fr["fz"] + 3.6), lens=29)
render(OUT + "_daigoku_room.png", 1280, 720, 48)
print("DGK_ROOM_DONE", flush=True)
setup_cam((243, 817, 2.6), (245, 831, 3.4), lens=35)
render(OUT + "_kokiden.png", 1280, 720, 48)
print("KOKI_DONE", flush=True)
setup_cam((60, 688, 3.2), (60, 722, 4.6), lens=35)
render(OUT + "_chukain.png", 1280, 720, 48)
print("CHUKAIN_DONE", flush=True)
setup_cam((430, 60, 330), (0, 640, 0), lens=35)
render(OUT + "_top.png", 1600, 1600, 32)
print("TOP_DONE", flush=True)
