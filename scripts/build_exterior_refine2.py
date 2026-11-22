"""大内裏・外観精密化その2（部品v5）スクリプト

使い方：
    blender --background heian_daidairi_detail_v16.blend \
        --python build_exterior_refine2.py

モデルv16を開いた状態で実行し、大内裏側にだけ外観の作り込みを足して
heian_daidairi_detail_v17.blend として保存し、確認画像を描く。
部品v4（build_exterior_refine.py）の続きで、対象は宮殿の中核部。
市街レイヤー・推定レイヤー・内裏内部・部品v4の部品には触れない。

内容（2026-11-21）：
- 築地塀の瓦帽子：部品v4で分割した外郭の築地塀16区間の上に、
  瓦色の笠と棟を載せた。塀が白い板から「屋根のある築地」に変わる。
- 大極殿基壇の高欄：基壇（59×24m・高さ2m）の縁に朱の高欄
  （柱＋2段の貫）。南面中央は龍尾壇からの登り口として開けた。
- 龍尾壇の階段と接続部：龍尾壇（大極殿手前の壇）の南面中央に
  石段6段、壇と基壇の間の溝に基壇上面とそろう石の接続部を置いた。
  これまで壇も基壇も、登る手段のない箱だった。
- 大極殿の蔀パネル：南面・北面の柱間に、木の板面＋縦桟＋中帯の
  蔀風パネルを入れた。白壁に柱だけだった正面に表情が出る。
- 朝堂院の殿舎の開口：朝堂12堂・朝集堂・小安殿の、中庭に面する
  長辺側に扉（板面＋横帯2本）と窓（板面）を付けた。開口は板面
  表現で貫通していない（市街の家屋と同じ割り切り）。
- 回廊の隅棟と垂木：部品v4で対象外だった回廊の屋根（20件）にも
  隅棟を付け、軒下には垂木の列（間隔1.5m）を並べた。
- 門扉の鉄鋲：部品v4の門扉50枚の両面に、鉄の鋲を格子状に打った。

新規オブジェクトは専用コレクション COL_06_ExteriorRefine2 に入れ、
facility_id を引き継ぐ。
"""
import bpy
import importlib.util
from mathutils import Vector
from collections import defaultdict

spec = importlib.util.spec_from_file_location(
    "build_detail",
    "/home/hatch/docs/proposal/history/3d/heiankyo-blender/scripts/build_chodoin_detailed.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

col = bpy.data.collections.get("COL_06_ExteriorRefine2")
if col is None:
    col = bpy.data.collections.new("COL_06_ExteriorRefine2")
    bpy.context.scene.collection.children.link(col)
col["layer"] = "exterior_refine_v5"
for _ob in list(col.objects):
    bpy.data.objects.remove(_ob, do_unlink=True)

_cubes = {}
def fbox(name, loc, dims, mat, fid="", quat=None):
    key = mat.name if mat else "None"
    mesh = _cubes.get(key)
    if mesh is None:
        mesh = bpy.data.meshes.new("Refine2Cube_" + key)
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

def base_name(o):
    n = o.name
    return n.rsplit(".", 1)[0] if "." in n and n.rsplit(".", 1)[1].isdigit() else n

def wbbox(o):
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs = [c.x for c in cs]
    ys = [c.y for c in cs]
    zs = [c.z for c in cs]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

def profile(t):
    return t * t * (3.0 - 2.0 * t)

WOOD = bpy.data.materials["MAT_WoodDark"]
VERMILION = bpy.data.materials["MAT_Vermilion"]
STONE = bpy.data.materials["MAT_Stone"]
ROOFTILE = bpy.data.materials["MAT_RoofTile"]
IRON = mod.make_mat("MAT_IronDark", (0.13, 0.13, 0.14), roughness=0.45,
                    metallic=0.7)

prefix_fid = {}
for o in bpy.data.objects:
    fid = o.get("facility_id", "")
    if not fid:
        continue
    parts = base_name(o).split("_")
    for k in range(len(parts) - 1, 0, -1):
        prefix_fid.setdefault("_".join(parts[:k]), fid)

# ---------------------------------------------------------------- 1. 築地塀の瓦帽子
n_cap = 0
for o in list(bpy.data.objects):
    bn = base_name(o)
    if not bn.startswith("WALL_Tsuiji") or not bn.endswith("_Seg"):
        continue
    x0, x1, y0, y1, z0, z1 = wbbox(o)
    fid = o.get("facility_id", "") or "DAIDAIRI_TSUJI"
    if (x1 - x0) >= (y1 - y0):
        length = x1 - x0
        fbox(bn + "_Cap", ((x0 + x1) / 2.0, (y0 + y1) / 2.0, z1 + 0.175),
             (length + 0.4, (y1 - y0) + 0.7, 0.35), ROOFTILE, fid)
        fbox(bn + "_CapRidge", ((x0 + x1) / 2.0, (y0 + y1) / 2.0, z1 + 0.47),
             (length + 0.4, 0.55, 0.24), ROOFTILE, fid)
    else:
        length = y1 - y0
        fbox(bn + "_Cap", ((x0 + x1) / 2.0, (y0 + y1) / 2.0, z1 + 0.175),
             ((x1 - x0) + 0.7, length + 0.4, 0.35), ROOFTILE, fid)
        fbox(bn + "_CapRidge", ((x0 + x1) / 2.0, (y0 + y1) / 2.0, z1 + 0.47),
             (0.55, length + 0.4, 0.24), ROOFTILE, fid)
    n_cap += 1
print("CAP_DONE segments=%d" % n_cap, flush=True)

# ---------------------------------------------------------------- 2. 大極殿基壇の高欄
dgk_kidan = None
ryubidan = None
for o in bpy.data.objects:
    bn = base_name(o)
    if bn == "CHD_Daigokuden_Kidan":
        dgk_kidan = o
    elif bn == "CHD_Ryubidan":
        ryubidan = o
kx0, kx1, ky0, ky1, kz0, kz1 = wbbox(dgk_kidan)
ktop = kz1
IN = 0.35
n_rail = 0
def railing_run(name, ax, fixed, a0, a1):
    """ax='x' なら y=fixed の直線に x 方向の高欄を置く"""
    global n_rail
    length = a1 - a0
    npost = max(2, int(round(length / 2.2)) + 1)
    for i in range(npost):
        t = a0 + length * i / (npost - 1)
        loc = (t, fixed, ktop + 0.475) if ax == "x" else (fixed, t, ktop + 0.475)
        fbox(name + "_RailPost", loc, (0.14, 0.14, 0.95), VERMILION, "CHD_DAIGOKUDEN")
        n_rail += 1
    for rz, rh in ((ktop + 0.90, 0.10), (ktop + 0.50, 0.08)):
        if ax == "x":
            fbox(name + "_Rail", ((a0 + a1) / 2.0, fixed, rz), (length, 0.16, rh),
                 VERMILION, "CHD_DAIGOKUDEN")
        else:
            fbox(name + "_Rail", (fixed, (a0 + a1) / 2.0, rz), (0.16, length, rh),
                 VERMILION, "CHD_DAIGOKUDEN")
        n_rail += 1
railing_run("CHD_Daigokuden_KidanS1", "x", ky0 + IN, kx0 + IN, -6.0)
railing_run("CHD_Daigokuden_KidanS2", "x", ky0 + IN, 6.0, kx1 - IN)
railing_run("CHD_Daigokuden_KidanN", "x", ky1 - IN, kx0 + IN, kx1 - IN)
railing_run("CHD_Daigokuden_KidanE", "y", kx1 - IN, ky0 + IN, ky1 - IN)
railing_run("CHD_Daigokuden_KidanW", "y", kx0 + IN, ky0 + IN, ky1 - IN)
print("RAIL_DONE parts=%d" % n_rail, flush=True)

# ---------------------------------------------------------------- 3. 龍尾壇の階段と接続部
rx0, rx1, ry0, ry1, rz0, rz1 = wbbox(ryubidan)
n_step = 0
NST = 6
for i in range(NST):
    h = rz1 * (i + 1) / NST
    yc = ry0 - (NST - i - 0.5) * 0.55
    fbox("CHD_Ryubidan_Step", ((rx0 + rx1) / 2.0, yc, h / 2.0),
         (12.0, 0.55, h), STONE, "CHD_RYUBIDAN")
    n_step += 1
# 壇の北辺と基壇の南辺の間を、基壇上面と同じ高さでつなぐ
fbox("CHD_Ryubidan_Link", ((rx0 + rx1) / 2.0, (ry1 + ky0) / 2.0, ktop / 2.0),
     (12.0, (ky0 - ry1) + 0.6, ktop), STONE, "CHD_RYUBIDAN")
print("STEPS_DONE steps=%d" % n_step, flush=True)

# ---------------------------------------------------------------- 4. 大極殿の蔀パネル
dgk_wall = None
dgk_cols_s = []
for o in bpy.data.objects:
    bn = base_name(o)
    if bn == "CHD_Daigokuden_Wall":
        dgk_wall = o
    elif bn == "CHD_Daigokuden_Col":
        dgk_cols_s.append(o)
wx0, wx1, wy0, wy1, wz0, wz1 = wbbox(dgk_wall)
col_xs = set()
for o in dgk_cols_s:
    b = wbbox(o)
    if abs((b[2] + b[3]) / 2.0 - wy0) < 1.0:   # 南面の柱だけ
        col_xs.add(round((b[0] + b[1]) / 2.0, 2))
col_xs = sorted(col_xs)
n_panel = 0
for face_y, sgn in ((wy0, -1), (wy1, 1)):
    py = face_y + sgn * 0.05
    for i in range(len(col_xs) - 1):
        bx = (col_xs[i] + col_xs[i + 1]) / 2.0
        pw = (col_xs[i + 1] - col_xs[i]) - 0.6
        fbox("CHD_Daigokuden_Shitomi", (bx, py, (wz0 + wz1) / 2.0),
             (pw, 0.10, (wz1 - wz0) - 1.0), WOOD, "CHD_DAIGOKUDEN")
        fbox("CHD_Daigokuden_ShitomiBand", (bx, py + sgn * 0.015, (wz0 + wz1) / 2.0),
             (pw, 0.13, 0.18), WOOD, "CHD_DAIGOKUDEN")
        for k in range(-2, 3):
            fbox("CHD_Daigokuden_ShitomiSlat", (bx + k * pw / 6.0, py + sgn * 0.015,
                                               (wz0 + wz1) / 2.0),
                 (0.09, 0.13, (wz1 - wz0) - 1.0), WOOD, "CHD_DAIGOKUDEN")
        n_panel += 1
print("PANEL_DGK_DONE bays=%d" % n_panel, flush=True)

# ---------------------------------------------------------------- 5. 朝堂院の殿舎の開口
chodoin = bpy.data.collections.get("COL_02_Chodoin")
groups = defaultdict(list)
for o in chodoin.objects:
    groups[base_name(o).rsplit("_", 1)[0]].append(o)
COURT = Vector((0.0, 383.0))
n_open = 0
for prefix, objs in sorted(groups.items()):
    suffixes = {base_name(o).rsplit("_", 1)[-1] for o in objs}
    if not ("Base" in suffixes and "Wall" in suffixes and "Roof" in suffixes):
        continue
    wall = next(o for o in objs if base_name(o).endswith("_Wall"))
    fid = wall.get("facility_id", "")
    x0, x1, y0, y1, z0, z1 = wbbox(wall)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    bw, bd = x1 - x0, y1 - y0
    wh = z1 - z0
    if bw >= bd:
        # 長辺は南面・北面。中庭に近い方を選ぶ
        cands = [(cx, y0, -1), (cx, y1, 1)]
        fx, fy, sgn = min(cands, key=lambda c: (Vector((c[0], c[1])) - COURT).length)
        # 扉（中央）＋横帯2本
        fbox(prefix + "_OpenDoor", (cx, fy + sgn * 0.055, z0 + 1.3),
             (2.0, 0.09, 2.6), WOOD, fid)
        for bz in (z0 + 0.7, z0 + 1.9):
            fbox(prefix + "_OpenDoorBand", (cx, fy + sgn * 0.065, bz),
                 (2.0, 0.11, 0.16), WOOD, fid)
        for off in (-bw / 4.0, bw / 4.0):
            fbox(prefix + "_OpenWindow", (cx + off, fy + sgn * 0.055, z0 + wh * 0.58),
                 (1.7, 0.09, 1.9), WOOD, fid)
    else:
        cands = [(x0, cy, -1), (x1, cy, 1)]
        fx, fy, sgn = min(cands, key=lambda c: (Vector((c[0], c[1])) - COURT).length)
        fbox(prefix + "_OpenDoor", (fx + sgn * 0.055, cy, z0 + 1.3),
             (0.09, 2.0, 2.6), WOOD, fid)
        for bz in (z0 + 0.7, z0 + 1.9):
            fbox(prefix + "_OpenDoorBand", (fx + sgn * 0.065, cy, bz),
                 (0.11, 2.0, 0.16), WOOD, fid)
        for off in (-bd / 4.0, bd / 4.0):
            fbox(prefix + "_OpenWindow", (fx + sgn * 0.055, cy + off, z0 + wh * 0.58),
                 (0.09, 1.7, 1.9), WOOD, fid)
    n_open += 1
print("HALL_OPEN_DONE halls=%d" % n_open, flush=True)

# ---------------------------------------------------------------- 6. 回廊の隅棟と垂木
def hip_ridges(roof, min_dim=4.0):
    bn = base_name(roof)
    fid = roof.get("facility_id", "") or prefix_fid.get(bn[:-5], "CHD_CORRIDOR")
    x0, x1, y0, y1, z0, z1 = wbbox(roof)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    w, d = x1 - x0, y1 - y0
    eave_z = z0 + 0.35
    rh = z1 - eave_z
    if min(w, d) < min_dim or rh < 0.8:
        return 0
    mat = roof.data.materials[0] if roof.data.materials else None
    long_x = w >= d
    L, S = max(w, d), min(w, d)
    n = 0
    SEG = 4
    for sl in (-1, 1):
        for ss in (-1, 1):
            pts = []
            for i in range(SEG + 1):
                u = i / SEG
                short_c = (S / 2.0) * (1.0 - u)
                long_c = L / 2.0 - (S / 2.0) * u
                corner = (long_c / (L / 2.0)) * (short_c / (S / 2.0)) if S > 0 else 0.0
                z = eave_z + rh * profile(u) + rh * 0.055 * corner * (1.0 - u) + 0.03
                if long_x:
                    pts.append(Vector((cx + sl * long_c, cy + ss * short_c, z)))
                else:
                    pts.append(Vector((cx + ss * short_c, cy + sl * long_c, z)))
            for i in range(SEG):
                a, b = pts[i], pts[i + 1]
                mid = (a + b) / 2.0
                dist = (b - a).length
                q = Vector((0, 1, 0)).rotation_difference(b - a)
                fbox(bn + "_HipRidge", mid, (0.24, dist * 1.3, 0.15), mat, fid, quat=q)
                n += 1
    return n

n_khip = 0
n_kraft = 0
for o in list(bpy.data.objects):
    bn = base_name(o)
    if "KAIRO" not in bn or not bn.endswith("_Roof"):
        continue
    if o.type != "MESH":
        continue
    n_khip += hip_ridges(o)
    fid = prefix_fid.get(bn[:-5], "CHD_CORRIDOR")
    x0, x1, y0, y1, z0, z1 = wbbox(o)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    w, d = x1 - x0, y1 - y0
    eave_z = z0 + 0.35
    if w >= d:
        span = w - d          # 寄棟の斜面になる両端を除いた直線部
        cnt = max(4, int(span / 1.5))
        for sy in (-1, 1):
            for i in range(cnt + 1):
                x = cx - span / 2.0 + span * i / cnt
                ob = fbox(bn + "_Rafter", (x, cy + sy * (d / 2.0 - 0.30), eave_z - 0.28),
                          (0.13, 0.55, 0.10), WOOD, fid)
                ob.rotation_euler.x = -sy * 0.6
                n_kraft += 1
    else:
        span = d - w
        cnt = max(4, int(span / 1.5))
        for sx in (-1, 1):
            for i in range(cnt + 1):
                y = cy - span / 2.0 + span * i / cnt
                ob = fbox(bn + "_Rafter", (cx + sx * (w / 2.0 - 0.30), y, eave_z - 0.28),
                          (0.55, 0.13, 0.10), WOOD, fid)
                ob.rotation_euler.y = sx * 0.6
                n_kraft += 1
print("KAIRO_DONE hip_boxes=%d rafters=%d" % (n_khip, n_kraft), flush=True)

# ---------------------------------------------------------------- 7. 門扉の鉄鋲
n_stud = 0
for o in list(bpy.data.objects):
    bn = base_name(o)
    if "_DoorLeaf" not in bn:
        continue
    fid = o.get("facility_id", "")
    x0, x1, y0, y1, z0, z1 = wbbox(o)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    thin_x = (x1 - x0) <= (y1 - y0)
    length = (y1 - y0) if thin_x else (x1 - x0)
    ncol = max(2, int(round(length / 0.7)))
    for rz in (1.5, 2.35, 3.2):
        for i in range(ncol):
            t = -length / 2.0 + 0.3 + (length - 0.6) * i / (ncol - 1)
            for s in (-1, 1):
                if thin_x:
                    fbox(bn + "_Stud", (cx + s * ((x1 - x0) / 2.0 + 0.025), cy + t, rz),
                         (0.05, 0.11, 0.11), IRON, fid)
                else:
                    fbox(bn + "_Stud", (cx + t, cy + s * ((y1 - y0) / 2.0 + 0.025), rz),
                         (0.11, 0.05, 0.11), IRON, fid)
                n_stud += 1
print("STUD_DONE studs=%d" % n_stud, flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v17.blend")
print("SAVED_V17", flush=True)

# ---------------------------------------------------------------- 確認描画
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
cam_data = bpy.data.cameras.new("V17Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V17Cam", cam_data)
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

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v17"
setup_cam((95, 415, 26), (0, 568, 15), lens=35)
render(OUT + "_daigokuden.png", 1280, 720, 48)
print("DAIGOKUDEN_DONE", flush=True)
setup_cam((24, 492, 3.2), (-2, 562, 13), lens=35)
render(OUT + "_front.png", 1280, 720, 48)
print("FRONT_DONE", flush=True)
setup_cam((28, 348, 2.1), (79, 432, 3.3), lens=32)
render(OUT + "_corridor.png", 1280, 720, 48)
print("CORRIDOR_DONE", flush=True)
setup_cam((1.8, -9, 2.1), (-2.9, 3.5, 2.3), lens=32)
render(OUT + "_door.png", 1280, 720, 48)
print("DOOR_DONE", flush=True)
setup_cam((150, -55, 7), (20, 0, 4.5), lens=35)
render(OUT + "_wall.png", 1280, 720, 48)
print("WALL_DONE", flush=True)
setup_cam((430, 60, 330), (0, 640, 0), lens=35)
render(OUT + "_top.png", 1600, 1600, 32)
print("TOP_DONE", flush=True)
