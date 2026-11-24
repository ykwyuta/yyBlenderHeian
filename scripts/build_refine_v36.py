"""屋外の小物の作り込みスクリプト（部品v22、モデルv36）

使い方：
    blender --background heian_daidairi_detail_v35.blend \
        --python build_refine_v36.py

モデルv35を開き、官衙や服務の殿舎の庭に屋外の小物を置いて
heian_daidairi_detail_v36.blend として保存する。確認画像つき。

内容（2026-11-24）：
- 部品v21（室内の小物）に続く作り込み。建物の庭まわりも
  空っぽで用途が分からなかったため、官衙の庁舎・内酒殿・
  宮内省・寺の堂など15棟の庭に井戸を、官衙8棟の庭に荷車を、
  内酒殿と宮内省に薪の積み重ねと水桶を置いた。すべて模式の
  小物で、新規分は専用コレクション COL_20_ExteriorRefine16、
  evidence=schematic_prop（推定レイヤーの棟は conjectural）
- 井戸は石の井筒・木の屋形（柱2本と横木）・釣瓶で組む。
  荷車は荷台・大八車の車輪2つ・梶棒と積荷の俵。薪は丸太を
  積んだ山、水桶は鉄の箍の桶
- 置き場所は殿舎の南の庭で、他の建物と重ならない位置を
  自動で選ぶ

利用者の提案 docs/proposal/01_non-building-enrichment.md の
E1〜E10 には手をつけていない。
"""
import bpy
import math
from mathutils import Vector

M = {k: bpy.data.materials[n] for k, n in {
    "vermilion": "MAT_Vermilion", "white": "MAT_WhiteWall",
    "wood": "MAT_WoodDark", "light": "MAT_WoodLight",
    "tatami": "MAT_Tatami", "lacquer": "MAT_LacquerBlack",
    "gold": "MAT_Gold", "stone": "MAT_Stone", "iron": "MAT_IronDark",
}.items()}

pcol = bpy.data.collections.new("COL_20_ExteriorRefine16")
bpy.context.scene.collection.children.link(pcol)

def base_name(o):
    n = o.name
    return n.rsplit(".", 1)[0] if "." in n and n.rsplit(".", 1)[1].isdigit() else n

def wbbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

_cube = {}
def cube_mesh(mat):
    if mat.name not in _cube:
        m = bpy.data.meshes.new("Prop36Cube_" + mat.name)
        m.from_pydata(
            [(-.5, -.5, -.5), (.5, -.5, -.5), (.5, .5, -.5), (-.5, .5, -.5),
             (-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5)],
            [],
            [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2),
             (2, 6, 7, 3), (3, 7, 4, 0)])
        m.update()
        m.materials.append(mat)
        _cube[mat.name] = m
    return _cube[mat.name]

_cyl = {}
def cyl_mesh(mat, axis="Z", seg=14):
    key = mat.name + axis + str(seg)
    if key not in _cyl:
        verts, faces = [], []
        for t in (-0.5, 0.5):
            for k in range(seg):
                a = 2 * math.pi * k / seg
                c, s = math.cos(a), math.sin(a)
                if axis == "Z":
                    verts.append((c, s, t))
                elif axis == "X":
                    verts.append((t, c, s))
                else:
                    verts.append((c, t, s))
        for k in range(seg):
            k2 = (k + 1) % seg
            faces.append((k, k2, seg + k2, seg + k))
        faces.append(tuple(range(seg - 1, -1, -1)))
        faces.append(tuple(range(seg, 2 * seg)))
        m = bpy.data.meshes.new("Prop36Cyl_" + key)
        m.from_pydata(verts, [], faces)
        m.update()
        m.materials.append(mat)
        _cyl[key] = m
    return _cyl[key]

CUR = {"tag": "", "fid": "", "ev": ""}
_counter = [0]

def _mk(mesh, loc, scale):
    _counter[0] += 1
    ob = bpy.data.objects.new("PROP36_%s_%04d" % (CUR["tag"], _counter[0]), mesh)
    ob.location = loc
    ob.scale = scale
    if CUR["fid"]:
        ob["facility_id"] = CUR["fid"]
    ob["evidence"] = CUR["ev"]
    pcol.objects.link(ob)
    return ob

def box(mat, x, y, zbase, dx, dy, h):
    return _mk(cube_mesh(M[mat]), (x, y, zbase + h / 2.0), (dx, dy, h))

def cyl(mat, x, y, zbase, r, h, axis="Z"):
    dims = {"Z": (r, r, h), "X": (h, r, r), "Y": (r, h, r)}[axis]
    return _mk(cyl_mesh(M[mat], axis), (x, y, zbase + h / 2.0 if axis == "Z" else zbase), dims)

# ---------------------------------------------------------------- 小物
def well(x, y):
    cyl("stone", x, y, 0.0, 0.78, 0.55)
    cyl("iron", x, y, 0.38, 0.62, 0.06)
    box("wood", x - 0.68, y, 0.0, 0.1, 0.1, 1.5)
    box("wood", x + 0.68, y, 0.0, 0.1, 0.1, 1.5)
    box("wood", x, y, 1.42, 1.55, 0.1, 0.09)
    box("iron", x, y, 0.62, 0.03, 0.03, 0.8)
    cyl("light", x + 0.95, y + 0.3, 0.0, 0.17, 0.26)

def cart(x, y):
    box("light", x, y, 0.72, 2.0, 1.15, 0.1)
    box("wood", x, y - 0.55, 0.82, 2.0, 0.05, 0.3)
    box("wood", x, y + 0.55, 0.82, 2.0, 0.05, 0.3)
    cyl("wood", x, y - 0.68, 0.55, 0.55, 0.09, axis="Y")
    cyl("wood", x, y + 0.68, 0.55, 0.55, 0.09, axis="Y")
    cyl("iron", x, y - 0.68, 0.55, 0.14, 0.12, axis="Y")
    cyl("iron", x, y + 0.68, 0.55, 0.14, 0.12, axis="Y")
    box("wood", x + 1.55, y - 0.35, 0.18, 1.3, 0.07, 0.07)
    box("wood", x + 1.55, y + 0.35, 0.18, 1.3, 0.07, 0.07)
    cyl("tatami", x - 0.45, y, 0.82, 0.33, 0.62)
    cyl("tatami", x + 0.45, y, 0.82, 0.33, 0.62)

def firewood(x, y):
    for row_i, cnt in enumerate((4, 3, 2)):
        for i in range(cnt):
            cyl("wood", x - 0.7 + i * 0.24 + row_i * 0.12, y,
                0.11 + row_i * 0.21, 0.105, 1.1, axis="Y")
    box("light", x, y - 0.62, 0.0, 1.3, 0.08, 0.1)
    box("light", x, y + 0.62, 0.0, 1.3, 0.08, 0.1)

def barrel(x, y):
    cyl("light", x, y, 0.0, 0.34, 0.8)
    cyl("iron", x, y, 0.15, 0.355, 0.06)
    cyl("iron", x, y, 0.59, 0.355, 0.06)

# ---------------------------------------------------------------- 配置
SOLID = []
for o in bpy.data.objects:
    b = base_name(o)
    if ("_Wall" in b or "_Kidan" in b or "_Base" in b) and not b.startswith("PROP"):
        SOLID.append(wbbox(o))

def free(x, y, r=1.6):
    for (x0, x1, y0, y1, z0, z1) in SOLID:
        if x0 - r < x < x1 + r and y0 - r < y < y1 + r:
            return False
    return True

def frame_of(prefix):
    bs = [wbbox(o) for o in bpy.data.objects
          if base_name(o).startswith(prefix + "_Wall")]
    if not bs:
        return None
    fid = ""
    for o in bpy.data.objects:
        if base_name(o).startswith(prefix + "_Wall"):
            fid = o.get("facility_id", "")
            break
    return {"x0": min(b[0] for b in bs), "x1": max(b[1] for b in bs),
            "y0": min(b[2] for b in bs), "y1": max(b[3] for b in bs),
            "fid": fid}

WELLS = ["CHUMUSHO_Main", "GOV_E_GUARD_Main", "GOV_SE_ADMIN_Main",
         "GOV_SW_POLICE_Main", "GOV_W_GUARD_Main", "JINGIKAN_Main",
         "SHUISUSHI_Main", "TOGU_GAIN_Main", "UCHISAKEDONO",
         "CONJ_KUNAISHŌ_Main", "CHUKAIN_Main", "SHINGONIN_Main",
         "BURAKUDEN", "LM_TOJI_Hall", "LM_SAIJI_Hall"]
CARTS = ["CHUMUSHO_Main", "GOV_E_GUARD_Main", "GOV_SE_ADMIN_Main",
         "GOV_SW_POLICE_Main", "GOV_W_GUARD_Main", "JINGIKAN_Main",
         "SHUISUSHI_Main", "TOGU_GAIN_Main"]
WOOD = ["UCHISAKEDONO", "CONJ_KUNAISHŌ_Main"]
BARRELS = ["CONJ_KUNAISHŌ_Main", "SHUISUSHI_Main"]

placed_wells = {}
for prefix in WELLS:
    fr = frame_of(prefix)
    if fr is None:
        print("SKIP", prefix, flush=True)
        continue
    CUR["tag"] = prefix.replace("Ō", "O")
    CUR["fid"] = fr["fid"]
    CUR["ev"] = "conjectural" if prefix.startswith("CONJ_") else "schematic_prop"
    cx = (fr["x0"] + fr["x1"]) / 2
    hx = (fr["x1"] - fr["x0"]) / 2
    for dxf, dy in ((0.42, 5.5), (-0.42, 5.5), (0.0, 6.5), (0.42, 9.0), (-0.42, 9.0)):
        x, y = cx + dxf * hx * 2 * 0.5, fr["y0"] - dy
        if free(x, y):
            well(x, y)
            placed_wells[prefix] = (x, y)
            break
    else:
        print("WELL_NOSPACE", prefix, flush=True)
for prefix in CARTS:
    fr = frame_of(prefix)
    if fr is None:
        continue
    CUR["tag"] = prefix.replace("Ō", "O")
    CUR["fid"] = fr["fid"]
    CUR["ev"] = "schematic_prop"
    cx = (fr["x0"] + fr["x1"]) / 2
    hx = (fr["x1"] - fr["x0"]) / 2
    for dxf, dy in ((-0.4, 7.5), (0.4, 7.5), (0.0, 10.0)):
        x, y = cx + dxf * hx, fr["y0"] - dy
        if free(x, y, 2.2):
            cart(x, y)
            break
    else:
        print("CART_NOSPACE", prefix, flush=True)
for prefix in WOOD:
    fr = frame_of(prefix)
    if fr is None:
        continue
    CUR["tag"] = prefix.replace("Ō", "O")
    CUR["fid"] = fr["fid"]
    CUR["ev"] = "conjectural" if prefix.startswith("CONJ_") else "schematic_prop"
    cx = (fr["x0"] + fr["x1"]) / 2
    hx = (fr["x1"] - fr["x0"]) / 2
    n = 0
    for dxf, dy in ((0.75, 4.0), (-0.75, 4.0), (0.75, 8.0)):
        x, y = cx + dxf * hx, fr["y0"] - dy
        if free(x, y, 1.4):
            firewood(x, y)
            n += 1
        if n >= 2:
            break
for prefix in BARRELS:
    fr = frame_of(prefix)
    if fr is None:
        continue
    CUR["tag"] = prefix.replace("Ō", "O")
    CUR["fid"] = fr["fid"]
    CUR["ev"] = "conjectural" if prefix.startswith("CONJ_") else "schematic_prop"
    cx = (fr["x0"] + fr["x1"]) / 2
    hx = (fr["x1"] - fr["x0"]) / 2
    base = None
    for dxf, dy in ((-0.7, 5.0), (0.7, 5.0), (0.0, 4.0)):
        x, y = cx + dxf * hx, fr["y0"] - dy
        if free(x, y, 1.8):
            base = (x, y)
            break
    if base:
        for i, (ox, oy) in enumerate(((0, 0), (0.85, 0.2), (0.3, 0.85), (1.1, 0.9))):
            barrel(base[0] + ox, base[1] + oy)
print("PROPS36_DONE objects=%d wells=%d" % (_counter[0], len(placed_wells)), flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v36.blend")
print("SAVED_V36", flush=True)

# ---------------------------------------------------------------- 確認描画
for c in bpy.data.collections:
    if c.name.startswith("COL_70"):
        c.hide_render = True
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
cam_data = bpy.data.cameras.new("V36Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V36Cam", cam_data)
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

wp = placed_wells.get("UCHISAKEDONO")
if wp:
    setup_cam((wp[0] + 6.5, wp[1] - 7.5, 3.2), (wp[0] - 1, wp[1] + 3, 0.8), lens=32)
    render("/home/hatch/workspace/heiankyo-blender/output/view_v36_yard.png", 1280, 720, 48)
    print("YARD_DONE", flush=True)
setup_cam((430, 60, 330), (0, 640, 0), lens=35)
render("/home/hatch/workspace/heiankyo-blender/output/view_v36_top.png", 1400, 1400, 24)
print("TOP_DONE", flush=True)
