"""平安京・市街レイヤー生成スクリプト（模式生成）

使い方：
    blender --background heian_daidairi_detail_v7.blend \
        --python build_city_layer.py

大内裏モデル（v7）を開いた状態で実行し、市街レイヤーを追加して
heian_daidairi_detail_v8.blend として保存し、確認画像を描く。

考え方（10_city-layer.md に詳述）：
- 条坊グリッド（町ピッチ133m＝宅地121m＋小路）を骨格に、町単位で
  貴族邸・官人宅・庶民町・寺・畑を確率配分して模式生成する。
  個別の家の史料はないため、町並み全体が確度Dの模式である。
- 位置に根拠のあるランドマーク（羅城門・東寺・西寺・東市・西市・
  神泉苑）だけは固定配置する（data/heiankyo_city_landmarks_v1.csv）。
- 大内裏のデータ・モデルには触れない。市街は専用コレクション
  COL_70_City に入れ、全オブジェクトに evidence=procedural_city を付ける。
- 密度は史料の傾向を反映する：左京は濃く、右京は低湿地として疎らで
  畑が多い。乱数は種818で固定し、再実行で同じ町並みになる。

実装上の注意：約1.5万オブジェクトを bpy.ops 経由で作ると場面の
肥大化に伴って指数的に遅くなる（実測で40分でも終わらなかった）。
そのため市街レイヤーの部品は、共有メッシュ＋オブジェクト配置だけの
高速プリミティブで作る。形状は大内裏の部品と見た目が揃う範囲で簡略化
している（家の屋根は低分割の寄棟、棟木つき）。
"""
import bpy
import importlib.util
import random
import sys
from mathutils import Vector
import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from heian_gpu import use_gpu  # noqa: E402  GPU があれば使う（HEIAN_DEVICE=CPU で無効）
import os
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_SCRIPT_DIR)
# 生成物（.blend・画像）の置き場所。環境変数 HEIAN_WORK で変更できる（既定: <リポジトリ>/output）
WORK = os.environ.get("HEIAN_WORK", os.path.join(_REPO, "output"))
os.makedirs(WORK, exist_ok=True)

spec = importlib.util.spec_from_file_location(
    "build_detail",
    os.path.join(_SCRIPT_DIR, "build_chodoin_detailed.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

MATMAP = {
    "vermilion": "MAT_Vermilion", "white": "MAT_WhiteWall", "roof": "MAT_RoofTile",
    "roof_green": "MAT_RoofGreenGlaze", "stone": "MAT_Stone", "wood": "MAT_WoodDark",
    "gold": "MAT_Gold", "sand": "MAT_SandGround", "earth": "MAT_EarthGround",
    "pine": "MAT_PineGreen", "trunk": "MAT_TrunkBrown", "road": "MAT_RoadGravel",
}
for key, name in MATMAP.items():
    mod.MAT[key] = bpy.data.materials[name]
mod.MAT["water"] = mod.make_mat("MAT_Water", (0.16, 0.28, 0.38), roughness=0.3, color2=(0.11, 0.20, 0.28), tex_scale=0.8, bump=0.05)
mod.MAT["field"] = mod.make_mat("MAT_FieldGreen", (0.34, 0.44, 0.20), roughness=0.95, color2=(0.27, 0.37, 0.16), tex_scale=0.5, bump=0.2)
print("MAT_WIRED", flush=True)

rng = random.Random(818)
col = mod.get_or_make_collection("COL_70_City")
col["layer"] = "city_schematic"

PITCH = 133.0          # 町ピッチ（宅地121m＋小路）
PLOT = 121.0
PALACE = (-590.0, 590.0, -10.0, 1405.0)   # 大内裏（市街を作らない範囲）

# ---------------------------------------------------------------- 高速プリミティブ
def _unit_cube_mesh(mat):
    m = bpy.data.meshes.new("SharedCube")
    m.from_pydata(
        [(-.5, -.5, -.5), (.5, -.5, -.5), (.5, .5, -.5), (-.5, .5, -.5),
         (-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5)],
        [],
        [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)])
    m.update()
    if mat:
        m.materials.append(mat)
    return m

CUBE = {key: _unit_cube_mesh(mat) for key, mat in mod.MAT.items()}

def fbox(name, loc, dims, mat_key, fid=""):
    ob = bpy.data.objects.new(name, CUBE[mat_key])
    ob.location = loc
    ob.scale = dims
    ob["facility_id"] = fid
    col.objects.link(ob)
    return ob

_roof_cache = {}

def froof(name, cx, cy, w, d, eave_z, roof_h, mat_key, fid=""):
    """低分割の寄棟屋根。形状は (w,d,roof_h) でキャッシュして共有する。"""
    key = (round(w), round(d), round(roof_h * 2), mat_key)
    mesh = _roof_cache.get(key)
    if mesh is None:
        nx, ny = 8, 6
        verts = []
        for j in range(ny + 1):
            y = -d / 2.0 + d * j / ny
            for i in range(nx + 1):
                x = -w / 2.0 + w * i / nx
                t = min(w / 2.0 - abs(x), d / 2.0 - abs(y)) / (min(w, d) / 2.0)
                t = max(0.0, min(1.0, t))
                z = roof_h * (t * t * (3.0 - 2.0 * t))
                verts.append((x, y, z))
        faces = []
        for j in range(ny):
            for i in range(nx):
                a = j * (nx + 1) + i
                faces.append((a, a + 1, a + nx + 2, a + nx + 1))
        mesh = bpy.data.meshes.new("SharedRoof")
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        for poly in mesh.polygons:
            poly.use_smooth = True
        mesh.materials.append(mod.MAT[mat_key])
        _roof_cache[key] = mesh
    ob = bpy.data.objects.new(name, mesh)
    ob.location = (cx, cy, eave_z)
    ob["facility_id"] = fid
    col.objects.link(ob)
    # 棟木
    if w >= d:
        fbox(name + "_Ridge", (cx, cy, eave_z + roof_h + 0.15), (max(0.4, w - d) + 0.8, 0.55, 0.3), mat_key, fid)
    else:
        fbox(name + "_Ridge", (cx, cy, eave_z + roof_h + 0.15), (0.55, max(0.4, d - w) + 0.8, 0.3), mat_key, fid)
    return ob

_cyl_cache = {}

def fcyl(name, loc, scale, mat_key, fid=""):
    mesh = _cyl_cache.get(mat_key)
    if mesh is None:
        import math
        verts = []
        for k in range(12):
            a = 2 * math.pi * k / 12
            verts.append((math.cos(a), math.sin(a), -0.5))
        for k in range(12):
            a = 2 * math.pi * k / 12
            verts.append((math.cos(a), math.sin(a), 0.5))
        faces = []
        for k in range(12):
            k2 = (k + 1) % 12
            faces.append((k, k2, 12 + k2, 12 + k))
        faces.append(tuple(range(11, -1, -1)))
        faces.append(tuple(range(12, 24)))
        mesh = bpy.data.meshes.new("SharedCyl")
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        mesh.materials.append(mod.MAT[mat_key])
        _cyl_cache[mat_key] = mesh
    ob = bpy.data.objects.new(name, mesh)
    ob.location = loc
    ob.scale = scale
    ob["facility_id"] = fid
    col.objects.link(ob)
    return ob

def fwall(prefix, cx, cy, sx, sy):
    """築地塀（高速版）。南辺中央に開口。"""
    inset, h, t = 1.2, 2.4, 0.7
    ix, iy = sx / 2 - inset, sy / 2 - inset
    runs = [("N", cx, cy + iy, 2 * ix, t), ("E", cx + ix, cy, t, 2 * iy), ("W", cx - ix, cy, t, 2 * iy)]
    gap = 8.0
    seg = (2 * ix - gap) / 2
    runs.append(("S1", cx - gap / 2 - seg / 2, cy - iy, seg, t))
    runs.append(("S2", cx + gap / 2 + seg / 2, cy - iy, seg, t))
    for tag, x, y, w, d in runs:
        fbox(prefix + "_Wall" + tag, (x, y, h / 2), (w, d, h), "white", prefix)
        fbox(prefix + "_Cap" + tag, (x, y, h + 0.15), (w, d + 0.35, 0.3), "roof", prefix)

def fpine(prefix, x, y, s=1.0):
    fbox(prefix + "_Trunk", (x, y, 1.5 * s), (0.35 * s, 0.35 * s, 3.0 * s), "trunk", prefix)
    fcyl(prefix + "_Canopy1", (x, y, 3.6 * s), (3.4 * s, 3.4 * s, 1.1 * s), "pine", prefix)
    fcyl(prefix + "_Canopy2", (x, y, 4.7 * s), (2.3 * s, 2.3 * s, 1.0 * s), "pine", prefix)

def house(prefix, x, y, w, d, roof_key, wall_key="wood"):
    fbox(prefix + "_Wall", (x, y, 1.25), (w, d, 2.5), wall_key, prefix)
    froof(prefix + "_Roof", x, y, w + 1.8, d + 1.8, 2.5, 1.8, roof_key, prefix)

def hall_fast(prefix, cx, cy, w, d, wall_h=4.0, roof_h=4.2):
    """殿舎の高速版：基壇＋白壁＋寄棟屋根（柱列は省略）。"""
    fbox(prefix + "_Kidan", (cx, cy, 0.4), (w + 3, d + 3, 0.8), "stone", prefix)
    fbox(prefix + "_Wall", (cx, cy, 0.8 + wall_h / 2), (w, d, wall_h), "white", prefix)
    froof(prefix + "_Roof", cx, cy, w + 5, d + 5, 0.8 + wall_h, roof_h, "roof", prefix)

def pagoda(prefix, x, y, tiers, base, height):
    fbox(prefix + "_Core", (x, y, height / 2), (base * 0.55, base * 0.55, height), "white", prefix)
    for i in range(tiers):
        t = i / max(tiers - 1, 1)
        s = base * (1 - 0.32 * t)
        z = height * (0.18 + 0.78 * t)
        fbox(prefix + "_Tier%d" % i, (x, y, z), (s, s, 0.55), "roof", prefix)
    fbox(prefix + "_Finial", (x, y, height + 2.2), (0.5, 0.5, 4.4), "gold", prefix)

# ---------------------------------------------------------------- 道路と地面
fbox("CITY_Ground", (0, -1100, -0.06), (4700, 6000, 0.08), "earth", "CITY")
fbox("CITY_SuzakuRoad", (0, -1925, 0.03), (84, 3850, 0.04), "road", "CITY")
for b in range(1, 8):
    fbox("CITY_AveEW%d" % b, (0, -550 * b, 0.025), (4340, 24, 0.04), "road", "CITY")
for sx in (574, 1106, 1638, 2170):
    for side in (-1, 1):
        if sx == 574:
            fbox("CITY_AveNS", (side * sx, -1925, 0.02), (20, 3850, 0.04), "road", "CITY")
        else:
            fbox("CITY_AveNS", (side * sx, -1228, 0.02), (20, 5244, 0.04), "road", "CITY")
for side in (-1, 1):
    fbox("CITY_Rajo", (side * (42 + 2128 / 2), -3872, 0.6), (2128, 3, 1.2), "earth", "CITY")
for i in range(15):
    y = -150 - i * 260
    for side in (-1, 1):
        fpine("CITY_Tree", side * 50, y, 0.85)

# ---------------------------------------------------------------- ランドマーク
mod.make_gate("LM_RAJOMON", 0, -3850, 36, 17, col, "LM_RAJOMON", upper=True, passage=True)
for side, tag in ((1, "TOJI"), (-1, "SAIJI")):
    x = side * 480
    fwall("LM_" + tag, x, -3760, 150, 150)
    pagoda("LM_" + tag + "_Pagoda", x, -3735, 5, 13, 30)
    hall_fast("LM_" + tag + "_Hall", x, -3805, 27, 15)
for side, tag in ((1, "EAST_MKT"), (-1, "WEST_MKT")):
    x = side * 840
    fbox("LM_" + tag + "_Plaza", (x, -1934, 0.03), (250, 250, 0.05), "sand", "LM_" + tag)
    for r in range(4):
        for c in range(5):
            sx_ = x - 88 + c * 44
            sy_ = -1934 - 66 + r * 44
            p = "LM_%s_Stall%d_%d" % (tag, r, c)
            fbox(p + "_Counter", (sx_, sy_, 0.5), (5, 3, 1.0), "wood", p)
            fbox(p + "_Roof", (sx_, sy_, 2.7), (6.5, 4.5, 0.25), "sand", p)
fbox("LM_SHINSENEN_Pond", (800, -270, 0.02), (300, 400, 0.05), "water", "LM_SHINSENEN")
hall_fast("LM_SHINSENEN_Hall", 800, -95, 23, 11)
for i, (px, py) in enumerate(((665, -120), (935, -120), (665, -430), (935, -430))):
    fpine("LM_SHINSENEN_Pine%d" % i, px, py, 1.1)

SKIP_RECTS = [
    PALACE,
    (840 - 135, 840 + 135, -1934 - 135, -1934 + 135),
    (-840 - 135, -840 + 135, -1934 - 135, -1934 + 135),
    (480 - 82, 480 + 82, -3760 - 82, -3760 + 82),
    (-480 - 82, -480 + 82, -3760 - 82, -3760 + 82),
    (800 - 165, 800 + 165, -270 - 215, -270 + 215),
]

def intersects(x0, x1, y0, y1):
    for a, b, c, d in SKIP_RECTS:
        if x0 < b and a < x1 and y0 < d and c < y1:
            return True
    return False

# ---------------------------------------------------------------- 町の生成
def weights(side, band):
    """(貴族邸, 官人宅, 庶民町, 寺, 畑) の確率。band: 0=二条 … 6=八条、-1=宮の両側"""
    if side > 0:  # 左京
        table = {-1: (.40, .35, .12, .03, .10), 0: (.40, .35, .12, .03, .10),
                 1: (.22, .33, .32, .03, .10), 2: (.22, .33, .32, .03, .10),
                 3: (.05, .25, .50, .05, .15), 4: (.02, .15, .45, .03, .35),
                 5: (.02, .15, .45, .03, .35), 6: (.00, .08, .30, .02, .60)}
    else:         # 右京（低湿：畑と空地が多い）
        table = {-1: (.15, .30, .25, .02, .28), 0: (.15, .30, .25, .02, .28),
                 1: (.05, .20, .30, .03, .42), 2: (.05, .20, .30, .03, .42),
                 3: (.02, .15, .35, .03, .45), 4: (.00, .05, .18, .02, .75),
                 5: (.00, .05, .18, .02, .75), 6: (.00, .05, .15, .02, .78)}
    return table[band]

def pick(w):
    r = rng.random()
    acc = 0.0
    for i, p in enumerate(w):
        acc += p
        if r < acc:
            return i
    return len(w) - 1

def build_plot(cx, cy, kind, tag):
    p = "CTY_" + tag
    if kind == 0:      # 貴族邸
        fwall(p, cx, cy, PLOT, PLOT)
        hall_fast(p + "_Main", cx, cy + 24, 29, 14)
        house(p + "_Side", cx - 34, cy - 16, 18, 11, "roof", "white")
        fcyl(p + "_Pond", (cx + 30, cy - 24, 0.05), (11, 11, 0.12), "water", p)
        fpine(p + "_Pine", cx - 28, cy + 30, 1.0)
    elif kind == 1:    # 官人宅（4分割）
        for i, (ox, oy) in enumerate(((-30, 30), (30, 30), (-30, -30), (30, -30))):
            house("%s_H%d" % (p, i), cx + ox, cy + oy, 21, 12.5, "roof")
    elif kind == 2:    # 庶民町（街路沿いに小家）
        n = 0
        for ox in (-45, -27, -9, 9, 27, 45):
            if rng.random() < 0.9:
                house("%s_S%d" % (p, n), cx + ox, cy - 48, 13.5, 8.5, "sand"); n += 1
            if rng.random() < 0.8:
                house("%s_S%d" % (p, n), cx + ox, cy + 48, 13.5, 8.5, "sand"); n += 1
        for oy in (-24, 0, 24):
            if rng.random() < 0.55:
                house("%s_S%d" % (p, n), cx - 48, cy + oy, 8.5, 13.5, "sand"); n += 1
            if rng.random() < 0.55:
                house("%s_S%d" % (p, n), cx + 48, cy + oy, 8.5, 13.5, "sand"); n += 1
    elif kind == 3:    # 寺
        fwall(p, cx, cy, PLOT, PLOT)
        hall_fast(p + "_Main", cx - 12, cy + 18, 21, 12)
        pagoda(p + "_Pagoda", cx + 30, cy - 18, 3, 9, 17)
    else:              # 畑・空地
        fbox(p + "_Field", (cx, cy, 0.02), (PLOT, PLOT, 0.05), "field", p)
        if rng.random() < 0.35:
            house(p + "_Farm", cx + rng.uniform(-25, 25), cy + rng.uniform(-25, 25), 12, 8, "sand")
        if rng.random() < 0.2:
            fpine(p + "_Pine", cx - 40, cy + 40, 0.9)

count = {}
plots = 0
for side in (-1, 1):
    for k in range(16):
        cx = side * (42 + k * PITCH + PITCH / 2)
        x0, x1 = cx - PLOT / 2, cx + PLOT / 2
        for band in range(7):
            for r in range(4):
                cy = -(band * 550 + 18 + r * PITCH + PITCH / 2)
                if intersects(x0, x1, cy - PLOT / 2, cy + PLOT / 2):
                    continue
                kind = pick(weights(side, band))
                build_plot(cx, cy, kind, "%s%d_B%d_%d" % ("E" if side > 0 else "W", k, band, r))
                count[kind] = count.get(kind, 0) + 1
                plots += 1
        for r in range(10):
            cy = r * PITCH + PITCH / 2
            if intersects(x0, x1, cy - PLOT / 2, cy + PLOT / 2):
                continue
            kind = pick(weights(side, -1))
            build_plot(cx, cy, kind, "%s%d_N%d" % ("E" if side > 0 else "W", k, r))
            count[kind] = count.get(kind, 0) + 1
            plots += 1

for obj in col.objects:
    obj["evidence"] = "procedural_city"
print("CITY_DONE plots=%d kinds=%s objects=%d" % (plots, count, len(col.objects)), flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath=os.path.join(WORK, "heian_daidairi_detail_v8.blend"))
print("SAVED_V8", flush=True)

scene = bpy.context.scene
use_gpu(scene)

def setup_cam(loc, target, ortho=None, lens=35):
    cam_data = bpy.data.cameras.new("V8Cam")
    cam_data.clip_start = 0.5
    cam_data.clip_end = 9000.0
    if ortho:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho
    else:
        cam_data.lens = lens
    cam = bpy.data.objects.new("V8Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

def render(path, rx, ry, samples):
    scene.cycles.samples = samples
    scene.render.resolution_x, scene.render.resolution_y = rx, ry
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)

OUT = os.path.join(WORK, "view_v8")
setup_cam((0, -1225, 3200), (0, -1225, 0), ortho=5600)
render(OUT + "_top.png", 1250, 1500, 16)
print("TOP_DONE", flush=True)
setup_cam((2700, -4300, 1500), (0, -900, 0), lens=35)
render(OUT + "_hero.png", 1280, 720, 32)
print("HERO_DONE", flush=True)
setup_cam((0, -3650, 4), (0, 200, 30), lens=30)
render(OUT + "_suzaku.png", 1280, 720, 32)
print("SUZAKU_DONE", flush=True)
