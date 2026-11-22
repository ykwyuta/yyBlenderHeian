"""大内裏・外観精密化その3（部品v6）スクリプト

使い方：
    blender --background heian_daidairi_detail_v17.blend \
        --python build_exterior_refine3.py

モデルv17を開いた状態で実行し、大内裏側にだけ外観の作り込みを足して
heian_daidairi_detail_v18.blend として保存し、確認画像を描く。
部品v4・v5の続き。今回は宮殿の殿舎の「顔」をそろえる回で、内裏の
後宮、豊楽殿、中和院・真言院、官衙の庁舎に開口を付けた。
市街レイヤー・推定レイヤー・内裏内部には触れない。

内容（2026-11-21）：
- 内裏・後宮の殿舎11棟（御花舎・弘徽殿・麗景殿・淑景舎・昭陽舎・
  承香殿・常寧殿・上東殿・登華殿・宣耀殿・襲芳舎）に、中庭に面する
  側へ扉と窓の板面を付けた。
- 内裏の正殿級4棟（紫宸殿・清涼殿・仁寿殿・飛香舎。内部を作った
  ため壁が4枚パネルになっている）は南面パネルを基準に開口を付け、
  紫宸殿は大極殿と同じ蔀パネル（柱間）とした。
- 豊楽殿：南面の柱間に蔀パネル、南面中央に石段4段。
- 中和院・真言院の主殿と脇殿（6棟）に、区画の中庭に面する側へ開口。
- 官衙の庁舎群：COL_05_Offices の庁舎・倉庫・厩舎（模式配置の
  infill）と主庁、内酒殿に、南面（基本の正面）へ扉と窓の板面を
  付けた。棟数が多いので壁オブジェクト単位で処理する。
- 門扉の環：部品v4の門扉50枚に、吊り金具の板と鉄の環を付けた。
  環はトーラスの共有メッシュで作る。
- 内裏の正殿3棟（紫宸殿・清涼殿・仁寿殿）の南面に、基壇上の
  木の縁側と石の階段2段を付けた。

開口はいずれも板面表現で貫通していない（市街の家屋・朝堂院の
殿舎と同じ割り切り）。新規オブジェクトは専用コレクション
COL_07_ExteriorRefine3 に入れ、facility_id を引き継ぐ。
"""
import bpy
import os
import sys as _sys
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_SCRIPT_DIR)
_sys.path.insert(0, _SCRIPT_DIR)
from heian_gpu import use_gpu  # noqa: E402  GPU があれば使う（HEIAN_DEVICE=CPU で無効）
# 生成物（.blend・画像）の置き場所。環境変数 HEIAN_WORK で変更できる（既定: <リポジトリ>/output）
WORK = os.environ.get("HEIAN_WORK", os.path.join(_REPO, "output"))
os.makedirs(WORK, exist_ok=True)
import importlib.util
import math
from mathutils import Vector
from collections import defaultdict

spec = importlib.util.spec_from_file_location(
    "build_detail",
    os.path.join(_SCRIPT_DIR, "build_chodoin_detailed.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

col = bpy.data.collections.get("COL_07_ExteriorRefine3")
if col is None:
    col = bpy.data.collections.new("COL_07_ExteriorRefine3")
    bpy.context.scene.collection.children.link(col)
col["layer"] = "exterior_refine_v6"
for _ob in list(col.objects):
    bpy.data.objects.remove(_ob, do_unlink=True)

_cubes = {}
def fbox(name, loc, dims, mat, fid="", quat=None):
    key = mat.name if mat else "None"
    mesh = _cubes.get(key)
    if mesh is None:
        mesh = bpy.data.meshes.new("Refine3Cube_" + key)
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
    if quat is not None:
        ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = quat
    if fid:
        ob["facility_id"] = fid
    col.objects.link(ob)
    return ob

# 門扉の環用トーラス（共有メッシュ）
def make_ring_mesh(mat):
    R, r, SEG, TUB = 0.15, 0.028, 14, 6
    verts = []
    for i in range(SEG):
        a = 2.0 * math.pi * i / SEG
        for j in range(TUB):
            b = 2.0 * math.pi * j / TUB
            x = (R + r * math.cos(b)) * math.cos(a)
            y = (R + r * math.cos(b)) * math.sin(a)
            z = r * math.sin(b)
            verts.append((x, y, z))
    faces = []
    for i in range(SEG):
        for j in range(TUB):
            i2 = (i + 1) % SEG
            j2 = (j + 1) % TUB
            faces.append((i * TUB + j, i2 * TUB + j, i2 * TUB + j2, i * TUB + j2))
    mesh = bpy.data.meshes.new("Refine3Ring")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.materials.append(mat)
    return mesh

def base_name(o):
    n = o.name
    return n.rsplit(".", 1)[0] if "." in n and n.rsplit(".", 1)[1].isdigit() else n

def wbbox(o):
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs = [c.x for c in cs]
    ys = [c.y for c in cs]
    zs = [c.z for c in cs]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

WOOD = bpy.data.materials["MAT_WoodDark"]
STONE = bpy.data.materials["MAT_Stone"]
IRON = bpy.data.materials["MAT_IronDark"]
RING_MESH = make_ring_mesh(IRON)

def hall_openings(prefix, wall, ref=None, fid=""):
    """壁1枚の、中庭に面する（または南の）長辺側に扉と窓の板面を付ける"""
    x0, x1, y0, y1, z0, z1 = wbbox(wall)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    bw, bd = x1 - x0, y1 - y0
    wh = z1 - z0
    n = 0
    if bw >= bd:
        if ref is not None:
            cands = [(cx, y0, -1), (cx, y1, 1)]
            fx, fy, sgn = min(cands, key=lambda c: (Vector((c[0], c[1])) - Vector(ref)).length)
        else:
            fx, fy, sgn = cx, y0, -1
        fbox(prefix + "_OpenDoor", (cx, fy + sgn * 0.055, z0 + 1.3),
             (2.0, 0.09, 2.6), WOOD, fid)
        for bz in (z0 + 0.7, z0 + 1.9):
            fbox(prefix + "_OpenDoorBand", (cx, fy + sgn * 0.065, bz),
                 (2.0, 0.11, 0.16), WOOD, fid)
        for off in (-bw / 4.0, bw / 4.0):
            fbox(prefix + "_OpenWindow", (cx + off, fy + sgn * 0.055, z0 + wh * 0.58),
                 (1.7, 0.09, 1.9), WOOD, fid)
        n = 5
    else:
        if ref is not None:
            cands = [(x0, cy, -1), (x1, cy, 1)]
            fx, fy, sgn = min(cands, key=lambda c: (Vector((c[0], c[1])) - Vector(ref)).length)
        else:
            fx, fy, sgn = x0, cy, -1
        fbox(prefix + "_OpenDoor", (fx + sgn * 0.055, cy, z0 + 1.3),
             (0.09, 2.0, 2.6), WOOD, fid)
        for bz in (z0 + 0.7, z0 + 1.9):
            fbox(prefix + "_OpenDoorBand", (fx + sgn * 0.065, cy, bz),
                 (0.11, 2.0, 0.16), WOOD, fid)
        for off in (-bd / 4.0, bd / 4.0):
            fbox(prefix + "_OpenWindow", (fx + sgn * 0.055, cy + off, z0 + wh * 0.58),
                 (0.09, 1.7, 1.9), WOOD, fid)
        n = 5
    return n

def shitomi_bays(prefix, wall, cols, hall_cy, fid):
    """南面の柱間に蔀パネルを入れる（大極殿と同じ様式）"""
    wx0, wx1, wy0, wy1, wz0, wz1 = wbbox(wall)
    xs = set()
    for o in cols:
        b = wbbox(o)
        if (b[2] + b[3]) / 2.0 < hall_cy:   # 南半分の柱
            xs.add(round((b[0] + b[1]) / 2.0, 2))
    xs = sorted(xs)
    n = 0
    py = wy0 - 0.05
    for i in range(len(xs) - 1):
        bx = (xs[i] + xs[i + 1]) / 2.0
        pw = (xs[i + 1] - xs[i]) - 0.6
        if pw < 1.0:
            continue
        ph = (wz1 - wz0) - 1.0
        fbox(prefix + "_Shitomi", (bx, py, (wz0 + wz1) / 2.0),
             (pw, 0.10, ph), WOOD, fid)
        fbox(prefix + "_ShitomiBand", (bx, py - 0.015, (wz0 + wz1) / 2.0),
             (pw, 0.13, 0.18), WOOD, fid)
        for k in range(-2, 3):
            fbox(prefix + "_ShitomiSlat", (bx + k * pw / 6.0, py - 0.015,
                                           (wz0 + wz1) / 2.0),
                 (0.09, 0.13, ph), WOOD, fid)
        n += 1
    return n

# ---------------------------------------------------------------- 1. 内裏・後宮の開口
dairi = bpy.data.collections["COL_03_Dairi"]
groups = defaultdict(list)
for o in dairi.objects:
    groups[base_name(o).rsplit("_", 1)[0]].append(o)
n_dairi = 0
for prefix, objs in sorted(groups.items()):
    suffixes = {base_name(o).rsplit("_", 1)[-1] for o in objs}
    if not ("Base" in suffixes and "Wall" in suffixes and "Roof" in suffixes):
        continue
    wall = next(o for o in objs if base_name(o).endswith("_Wall"))
    n_dairi += hall_openings(prefix, wall, ref=(280.0, 810.0),
                             fid=wall.get("facility_id", ""))
print("DAIRI_OPEN_DONE parts=%d" % n_dairi, flush=True)

# ---------------------------------------------------------------- 2. 内裏の正殿級4棟
n_inner = 0
for prefix, mode in (("DAIRI_SHISHINDEN", "shitomi"),
                     ("DAIRI_SEIRYODEN", "open"),
                     ("DAIRI_JIJU_JOKYO", "open"),
                     ("DAIRI_HIGYOSHA", "open")):
    objs = groups.get(prefix, [])
    wall_s = next((o for o in objs if base_name(o).endswith("_WallS")), None)
    kidan = next((o for o in objs if base_name(o).endswith("_Kidan")), None)
    if wall_s is None:
        continue
    fid = wall_s.get("facility_id", "") or prefix
    if mode == "shitomi" and kidan is not None:
        kb = wbbox(kidan)
        cols = [o for o in objs if base_name(o).endswith("_Col")]
        n_inner += shitomi_bays(prefix, wall_s, cols, (kb[2] + kb[3]) / 2.0, fid)
    else:
        # WallS の南面を開口の基準にする（壁として扱う）
        n_inner += hall_openings(prefix, wall_s, ref=None, fid=fid)
print("INNER4_DONE parts=%d" % n_inner, flush=True)

# ---------------------------------------------------------------- 3. 豊楽殿
bura = bpy.data.collections["COL_04_Burakuin"]
bgroups = defaultdict(list)
for o in bura.objects:
    bgroups[base_name(o).rsplit("_", 1)[0]].append(o)
bobjs = bgroups.get("BURAKUDEN", [])
bwall = next((o for o in bobjs if base_name(o).endswith("_Wall")), None)
bkidan = next((o for o in bobjs if base_name(o).endswith("_Kidan")), None)
n_bura = 0
if bwall is not None and bkidan is not None:
    kb = wbbox(bkidan)
    cols = [o for o in bobjs if base_name(o).endswith("_Col")]
    n_bura += shitomi_bays("BURAKUDEN", bwall, cols, (kb[2] + kb[3]) / 2.0,
                           bwall.get("facility_id", "BURAKUDEN"))
    # 南面中央の石段（地面0.3から基壇上面1.5まで4段）
    cx = (kb[0] + kb[1]) / 2.0
    for i in range(4):
        h = 0.3 + (kb[5] - 0.3) * (i + 1) / 4.0
        yc = kb[2] - (4 - i - 0.5) * 0.5
        fbox("BURAKUDEN_Step", (cx, yc, (0.3 + h) / 2.0), (10.0, 0.5, h - 0.3),
             STONE, "BURAKUDEN")
        n_bura += 1
print("BURA_DONE parts=%d" % n_bura, flush=True)

# ---------------------------------------------------------------- 4. 官衙コレクションの開口
offices = bpy.data.collections["COL_05_Offices"]
REFS = (("CHUKAIN", (60.0, 700.0)), ("SHINGONIN", (-140.0, 640.0)))
n_off = 0
n_off_walls = 0
for o in list(offices.objects):
    bn = base_name(o)
    if not bn.endswith("_Wall"):
        continue
    prefix = bn[:-5]
    ref = None
    for key, pt in REFS:
        if prefix.startswith(key):
            ref = pt
            break
    n_off += hall_openings(prefix, o, ref=ref, fid=o.get("facility_id", ""))
    n_off_walls += 1
print("OFFICE_OPEN_DONE walls=%d parts=%d" % (n_off_walls, n_off), flush=True)

# ---------------------------------------------------------------- 5. 門扉の環
walls_by_prefix = defaultdict(list)
for o in list(bpy.data.objects):
    if o.type != "MESH":
        continue
    bn = base_name(o)
    if bn.endswith("_Wall"):
        walls_by_prefix[bn[:-5]].append(o)
gate_info = {}
for prefix, walls in walls_by_prefix.items():
    if len(walls) != 2:
        continue
    a, b = wbbox(walls[0]), wbbox(walls[1])
    acx, acy = (a[0] + a[1]) / 2.0, (a[2] + a[3]) / 2.0
    bcx, bcy = (b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0
    if abs(acx - bcx) >= abs(acy - bcy):
        gx = ((a[1] + b[0]) / 2.0) if acx < bcx else ((b[1] + a[0]) / 2.0)
        gy = (max(a[2], b[2]) + min(a[3], b[3])) / 2.0
        gate_info[prefix] = ("NS", gx, gy)
    else:
        gx = (max(a[0], b[0]) + min(a[1], b[1])) / 2.0
        gy = ((a[3] + b[2]) / 2.0) if acy < bcy else ((b[3] + a[2]) / 2.0)
        gate_info[prefix] = ("EW", gx, gy)

n_ring = 0
for o in list(bpy.data.objects):
    bn = base_name(o)
    if not bn.endswith("_DoorLeaf"):
        continue
    prefix = bn.split("_DoorLeaf")[0]
    info = gate_info.get(prefix)
    if info is None:
        continue
    axis, gx, gy = info
    fid = o.get("facility_id", "")
    x0, x1, y0, y1, z0, z1 = wbbox(o)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    thin_x = (x1 - x0) <= (y1 - y0)
    if axis == "NS":
        # 通り抜けはY方向。蝶番は宮殿中心(y=697)に近い端
        jamb = y0 if abs(y0 - 697.0) < abs(y1 - 697.0) else y1
        free_side = 1 if jamb == y0 else -1
        along = cy + free_side * ((y1 - y0) / 2.0 - 0.38)
        s = 1 if gx > cx else -1
        rx = cx + s * ((x1 - x0) / 2.0 + 0.03)
        ob = bpy.data.objects.new(bn + "_Ring", RING_MESH)
        ob.location = (rx, along, 2.12)
        ob.rotation_euler = (0, math.pi / 2.0, 0)
        if fid:
            ob["facility_id"] = fid
        col.objects.link(ob)
        fbox(bn + "_RingMount", (cx + s * ((x1 - x0) / 2.0 + 0.012), along, 2.32),
             (0.03, 0.2, 0.26), IRON, fid)
    else:
        jamb = x0 if abs(x0 - 0.0) < abs(x1 - 0.0) else x1
        free_side = 1 if jamb == x0 else -1
        along = cx + free_side * ((x1 - x0) / 2.0 - 0.38)
        s = 1 if gy > cy else -1
        ry = cy + s * ((y1 - y0) / 2.0 + 0.03)
        ob = bpy.data.objects.new(bn + "_Ring", RING_MESH)
        ob.location = (along, ry, 2.12)
        ob.rotation_euler = (math.pi / 2.0, 0, 0)
        if fid:
            ob["facility_id"] = fid
        col.objects.link(ob)
        fbox(bn + "_RingMount", (along, cy + s * ((y1 - y0) / 2.0 + 0.012), 2.32),
             (0.2, 0.03, 0.26), IRON, fid)
    n_ring += 1
print("RING_DONE leaves=%d" % n_ring, flush=True)

# ---------------------------------------------------------------- 6. 正殿3棟の縁側と石段
n_ver = 0
GZ = 0.42   # 内裏内郭の地面スラブ上面
for prefix in ("DAIRI_SHISHINDEN", "DAIRI_SEIRYODEN", "DAIRI_JIJU_JOKYO"):
    objs = groups.get(prefix, [])
    kidan = next((o for o in objs if base_name(o).endswith("_Kidan")), None)
    wall_s = next((o for o in objs if base_name(o).endswith("_WallS")), None)
    if kidan is None or wall_s is None:
        continue
    fid = kidan.get("facility_id", "") or prefix
    kx0, kx1, ky0, ky1, kz0, kz1 = wbbox(kidan)
    wb = wbbox(wall_s)
    depth = wb[2] - ky0 - 0.12
    print("VERANDA_DBG", prefix, "depth=%.2f" % depth, flush=True)
    if depth >= 0.45:
        fbox(prefix + "_Veranda", ((kx0 + kx1) / 2.0, ky0 + 0.10 + depth / 2.0, kz1 + 0.06),
             (kx1 - kx0 - 0.8, depth, 0.12), WOOD, fid)
        n_ver += 1
    cx = (kx0 + kx1) / 2.0
    top2 = kz1 - 0.02
    fbox(prefix + "_StepStone2", (cx, ky0 - 0.275, (GZ + top2) / 2.0),
         (2.4, 0.55, top2 - GZ), STONE, fid)
    top1 = GZ + (kz1 - GZ) * 0.5
    fbox(prefix + "_StepStone1", (cx, ky0 - 0.825, (GZ + top1) / 2.0),
         (2.6, 0.55, top1 - GZ), STONE, fid)
    n_ver += 2
print("VERANDA_DONE parts=%d" % n_ver, flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath=os.path.join(WORK, "heian_daidairi_detail_v18.blend"))
print("SAVED_V18", flush=True)

# ---------------------------------------------------------------- 確認描画
scene = bpy.context.scene
scene.render.engine = "CYCLES"
use_gpu(scene)
cam_data = bpy.data.cameras.new("V18Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V18Cam", cam_data)
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

OUT = os.path.join(WORK, "view_v18")
setup_cam((215, 664, 5.5), (283, 738, 8.5), lens=35)
render(OUT + "_dairi.png", 1280, 720, 48)
print("DAIRI_DONE", flush=True)
setup_cam((280, 792, 3.2), (246, 884, 3.2), lens=35)
render(OUT + "_kokyo.png", 1280, 720, 48)
print("KOKYO_DONE", flush=True)
setup_cam((-280, 322, 4.5), (-280, 434, 6), lens=35)
render(OUT + "_burakuden.png", 1280, 720, 48)
print("BURA_DONE", flush=True)
setup_cam((60, 662, 3.5), (60, 722, 5), lens=35)
render(OUT + "_chukain.png", 1280, 720, 48)
print("CHUKAIN_DONE", flush=True)
setup_cam((300, 208, 4.5), (302, 330, 3.5), lens=35)
render(OUT + "_offices.png", 1280, 720, 48)
print("OFFICES_DONE", flush=True)
setup_cam((1.2, -3.5, 2.1), (-2.95, 3.2, 2.1), lens=32)
render(OUT + "_door.png", 1280, 720, 48)
print("DOOR_DONE", flush=True)
setup_cam((430, 60, 330), (0, 640, 0), lens=35)
render(OUT + "_top.png", 1600, 1600, 32)
print("TOP_DONE", flush=True)
