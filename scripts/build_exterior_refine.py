"""大内裏・外観精密化（部品v4）スクリプト

使い方：
    blender --background heian_daidairi_detail_v15.blend \
        --python build_exterior_refine.py

モデルv15を開いた状態で実行し、大内裏側にだけ外観の作り込みを足して
heian_daidairi_detail_v16.blend として保存し、確認画像を描く。
市街レイヤー・推定レイヤー・内裏内部には触れない（内裏の屋根素材の
付け替えのみ、対象オブジェクト自体への変更として行う）。

内容（2026-11-21）：
- 内裏（DAIRI_*）の殿舎の屋根を檜皮葺の色に付け替えた。平安の内裏は
  檜皮葺が標準的な姿で、瓦葺の大極殿・朝堂院との葺き分けになる。
  対象は _Roof / _RoofGable / _Roof_Ridge のみ（門の屋根は瓦のまま）。
- 寄棟屋根の四隅の稜線に隅棟（細い箱を稜線の曲線に沿って分割配置）。
  対象は大内裏側の殿舎と門の屋根（回廊と市街は除く）。
- 主要殿舎（入母屋の5棟＋大極殿）の長辺の軒下に垂木の列。
- 通り抜けのある門すべてに、開口の内側へ開いた姿の門扉（板扉＋横桟）。
  門の2枚の壁体の隙間から開口幅と奥行を求めるので、回転配置の
  東西門にもそのまま効く。
- 外郭の築地塀が門の通り抜けを塞いでいた問題の修正：塀は1枚の長い
  板で作られていて、門の位置でも貫通していた。門の開口に当たる
  区間を抜いて分割し直した（元の塀は削除し、分割分はこの
  コレクションに入る）。
新規オブジェクトは専用コレクション COL_05_ExteriorRefine に入れ、
facility_id を引き継ぐ。
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

col = bpy.data.collections.get("COL_05_ExteriorRefine")
if col is None:
    col = bpy.data.collections.new("COL_05_ExteriorRefine")
    bpy.context.scene.collection.children.link(col)
col["layer"] = "exterior_refine_v4"
for _ob in list(col.objects):
    bpy.data.objects.remove(_ob, do_unlink=True)

# 共有立方体（素材ごと）
_cubes = {}
def fbox(name, loc, dims, mat, fid="", quat=None):
    key = mat.name if mat else "None"
    mesh = _cubes.get(key)
    if mesh is None:
        mesh = bpy.data.meshes.new("RefineCube_" + key)
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

def in_city(o):
    return any(c.name == "COL_70_City" for c in o.users_collection)

def profile(t):
    return t * t * (3.0 - 2.0 * t)

WOOD = bpy.data.materials["MAT_WoodDark"]

# 接頭辞→facility_id の対応表（屋根オブジェクトには facility_id が
# 付いていないため、壁など属性のあるオブジェクトの名前から引く）
prefix_fid = {}
for o in bpy.data.objects:
    fid = o.get("facility_id", "")
    if not fid:
        continue
    parts = base_name(o).split("_")
    for k in range(len(parts) - 1, 0, -1):
        prefix_fid.setdefault("_".join(parts[:k]), fid)

# ---------------------------------------------------------------- 1. 内裏の檜皮葺
# 屋根には facility_id が付いていないので、名前の接頭辞で判定する
hiwada = mod.make_mat("MAT_HiwadaBark", (0.40, 0.28, 0.16), roughness=0.95,
                      color2=(0.32, 0.21, 0.11), tex_scale=2.0, bump=0.25)
n_hiwada = 0
for o in list(bpy.data.objects):
    bn = base_name(o)
    if not bn.startswith("DAIRI_"):
        continue
    if not (bn.endswith("_Roof") or bn.endswith("_RoofGable") or bn.endswith("_Roof_Ridge")):
        continue
    if o.type != "MESH":
        continue
    if o.data.users > 1:
        o.data = o.data.copy()
    if o.data.materials:
        o.data.materials[0] = hiwada
    else:
        o.data.materials.append(hiwada)
    n_hiwada += 1
print("HIWADA_DONE", n_hiwada, flush=True)

# ---------------------------------------------------------------- 2. 隅棟
def hip_ridges(roof):
    bn = base_name(roof)
    fid = roof.get("facility_id", "")
    if not fid:
        for suf in ("_Roof1", "_Roof2", "_Roof"):
            if bn.endswith(suf):
                fid = prefix_fid.get(bn[:-len(suf)], "")
                break
    x0, x1, y0, y1, z0, z1 = wbbox(roof)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    w, d = x1 - x0, y1 - y0
    eave_z = z0 + 0.35           # 軒の垂れ（スカート）分
    rh = z1 - eave_z
    if min(w, d) < 7.0 or rh < 0.8:
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

n_hip_roofs = 0
n_hip_boxes = 0
for o in list(bpy.data.objects):
    if o.type != "MESH" or in_city(o):
        continue
    bn = base_name(o)
    if not (bn.endswith("_Roof") or bn.endswith("_Roof1") or bn.endswith("_Roof2")):
        continue
    if o.get("facility_id", "") == "CHD_CORRIDOR" or "KAIRO" in bn:
        continue
    got = hip_ridges(o)
    if got:
        n_hip_roofs += 1
        n_hip_boxes += got
print("HIP_DONE roofs=%d boxes=%d" % (n_hip_roofs, n_hip_boxes), flush=True)

# ---------------------------------------------------------------- 3. 垂木
# 屋根には facility_id が付いていないので、名前の接頭辞で判定する
RAFTER_PREFIX = {"CHD_Daigokuden": "CHD_DAIGOKUDEN",
                 "DAIRI_SHISHINDEN": "DAIRI_SHISHINDEN",
                 "DAIRI_SEIRYODEN": "DAIRI_SEIRYODEN",
                 "DAIRI_JIJU_JOKYO": "DAIRI_JIJU_JOKYO",
                 "BURAKUDEN": "BURAKUDEN"}
n_raft = 0
for o in list(bpy.data.objects):
    if o.type != "MESH":
        continue
    bn = base_name(o)
    if not bn.endswith("_Roof"):
        continue
    fid = RAFTER_PREFIX.get(bn[:-5])
    if fid is None:
        continue
    x0, x1, y0, y1, z0, z1 = wbbox(o)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    w, d = x1 - x0, y1 - y0
    eave_z = z0 + 0.35
    mat = WOOD
    if w >= d:
        span = w * 0.80
        cnt = max(4, int(span / 0.92))
        for sy in (-1, 1):
            for i in range(cnt + 1):
                x = cx - span / 2.0 + span * i / cnt
                ob = fbox(bn + "_Rafter", (x, cy + sy * (d / 2.0 - 0.30), eave_z - 0.28),
                          (0.13, 0.55, 0.10), mat, fid)
                ob.rotation_euler.x = -sy * 0.6
                n_raft += 1
    else:
        span = d * 0.80
        cnt = max(4, int(span / 0.92))
        for sx in (-1, 1):
            for i in range(cnt + 1):
                y = cy - span / 2.0 + span * i / cnt
                ob = fbox(bn + "_Rafter", (cx + sx * (w / 2.0 - 0.30), y, eave_z - 0.28),
                          (0.55, 0.13, 0.10), mat, fid)
                ob.rotation_euler.y = sx * 0.6
                n_raft += 1
print("RAFTER_DONE", n_raft, flush=True)

# ---------------------------------------------------------------- 4. 門扉
from collections import defaultdict
walls_by_prefix = defaultdict(list)
for o in list(bpy.data.objects):
    if o.type != "MESH" or in_city(o):
        continue
    bn = base_name(o)
    if bn.endswith("_Wall"):
        walls_by_prefix[bn[:-5]].append(o)

n_doors = 0
gate_rects = []   # 通り抜けの矩形（後の築地塀の分割に使う）
for prefix, walls in sorted(walls_by_prefix.items()):
    if len(walls) != 2:
        continue
    fid = walls[0].get("facility_id", "")
    a = wbbox(walls[0])
    b = wbbox(walls[1])
    acx, acy = (a[0] + a[1]) / 2.0, (a[2] + a[3]) / 2.0
    bcx, bcy = (b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0
    if abs(acx - bcx) >= abs(acy - bcy):
        # 壁がX方向に分かれる＝開口はX方向の隙間、通り抜けはY方向
        if acx < bcx:
            gap_lo, gap_hi = a[1], b[0]
            face_a, face_b = a[1], b[0]
        else:
            gap_lo, gap_hi = b[1], a[0]
            face_a, face_b = b[1], a[0]
        pw = gap_hi - gap_lo
        if pw < 1.5 or pw > 8.0:
            continue
        depth_y0 = max(a[2], b[2])
        depth_y1 = min(a[3], b[3])
        depth = depth_y1 - depth_y0
        if depth < pw / 2.0:
            continue
        gate_rects.append((gap_lo, gap_hi, depth_y0, depth_y1))
        # 宮殿中心に近い側の口を蝶番側にする
        hinge_y = depth_y0 if abs(depth_y0 - 697.0) < abs(depth_y1 - 697.0) else depth_y1
        leaf_len = pw / 2.0 - 0.05
        for face, sgn in ((face_a, 1), (face_b, -1)):
            lx = face + sgn * 0.08
            if hinge_y == depth_y0:
                ly = hinge_y + leaf_len / 2.0
            else:
                ly = hinge_y - leaf_len / 2.0
            fbox(prefix + "_DoorLeaf", (lx, ly, 1.0 + 1.425), (0.13, leaf_len, 2.85), WOOD, fid)
            for bz in (1.7, 3.1):
                fbox(prefix + "_DoorBand", (lx, ly, bz), (0.17, leaf_len, 0.2), WOOD, fid)
            n_doors += 1
    else:
        # 壁がY方向に分かれる＝通り抜けはX方向
        if acy < bcy:
            gap_lo, gap_hi = a[3], b[2]
            face_a, face_b = a[3], b[2]
        else:
            gap_lo, gap_hi = b[3], a[2]
            face_a, face_b = b[3], a[2]
        pw = gap_hi - gap_lo
        if pw < 1.5 or pw > 8.0:
            continue
        depth_x0 = max(a[0], b[0])
        depth_x1 = min(a[1], b[1])
        depth = depth_x1 - depth_x0
        if depth < pw / 2.0:
            continue
        gate_rects.append((depth_x0, depth_x1, gap_lo, gap_hi))
        hinge_x = depth_x0 if abs(depth_x0 - 0.0) < abs(depth_x1 - 0.0) else depth_x1
        leaf_len = pw / 2.0 - 0.05
        for face, sgn in ((face_a, 1), (face_b, -1)):
            ly = face + sgn * 0.08
            if hinge_x == depth_x0:
                lx = hinge_x + leaf_len / 2.0
            else:
                lx = hinge_x - leaf_len / 2.0
            fbox(prefix + "_DoorLeaf", (lx, ly, 1.0 + 1.425), (leaf_len, 0.13, 2.85), WOOD, fid)
            for bz in (1.7, 3.1):
                fbox(prefix + "_DoorBand", (lx, ly, bz), (leaf_len, 0.17, 0.2), WOOD, fid)
            n_doors += 1
print("DOORS_DONE leaves=%d" % n_doors, flush=True)

# ---------------------------------------------------------------- 5. 築地塀の門開口
# 大内裏の外郭の築地塀は1枚の長い板で作られており、門の通り抜けを
# 塞いでいた（v16の確認で判明）。門の開口に当たる区間を抜いて
# 分割し直す。元の塀は消し、分割した塀はこのコレクションに入れる。
n_wall_seg = 0
for o in list(bpy.data.objects):
    if not base_name(o).startswith("WALL_Tsuiji"):
        continue
    x0, x1, y0, y1, z0, z1 = wbbox(o)
    mat = o.data.materials[0] if o.data.materials else None
    fid = o.get("facility_id", "") or "DAIDAIRI_TSUJI"
    long_x = (x1 - x0) >= (y1 - y0)
    openings = []
    for (gx0, gx1, gy0, gy1) in gate_rects:
        if long_x:
            if gy0 < y1 and gy1 > y0:
                openings.append((gx0, gx1))
        else:
            if gx0 < x1 and gx1 > x0:
                openings.append((gy0, gy1))
    if not openings:
        continue
    openings.sort()
    merged = []
    for a, b in openings:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    lo, hi = (x0, x1) if long_x else (y0, y1)
    cur = lo
    spans = []
    for a, b in merged:
        if a > cur:
            spans.append((cur, a))
        cur = max(cur, b)
    if cur < hi:
        spans.append((cur, hi))
    for a, b in spans:
        if b - a < 0.3:
            continue
        if long_x:
            fbox(base_name(o) + "_Seg", ((a + b) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0),
                 (b - a, y1 - y0, z1 - z0), mat, fid)
        else:
            fbox(base_name(o) + "_Seg", ((x0 + x1) / 2.0, (a + b) / 2.0, (z0 + z1) / 2.0),
                 (x1 - x0, b - a, z1 - z0), mat, fid)
        n_wall_seg += 1
    bpy.data.objects.remove(o, do_unlink=True)
print("WALL_DONE segments=%d" % n_wall_seg, flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v16.blend")
print("SAVED_V16", flush=True)

# ---------------------------------------------------------------- 確認描画
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
cam_data = bpy.data.cameras.new("V16Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V16Cam", cam_data)
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

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v16"
setup_cam((95, 415, 26), (0, 568, 15), lens=35)
render(OUT + "_daigokuden.png", 1280, 720, 48)
print("DAIGOKUDEN_DONE", flush=True)
setup_cam((280, 638, 8.5), (280, 738, 10), lens=35)
render(OUT + "_dairi.png", 1280, 720, 48)
print("DAIRI_DONE", flush=True)
setup_cam((7.5, -34, 2.4), (-1, 25, 2.2), lens=32)
render(OUT + "_gate.png", 1280, 720, 48)
print("GATE_DONE", flush=True)
setup_cam((430, 60, 330), (0, 640, 0), lens=35)
render(OUT + "_top.png", 1600, 1600, 32)
print("TOP_DONE", flush=True)
setup_cam((0, -14, 2.2), (0, 40, 2.4), lens=32)
render(OUT + "_passage.png", 1280, 720, 48)
print("PASSAGE_DONE", flush=True)
