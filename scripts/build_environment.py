# -*- coding: utf-8 -*-
"""環境レイヤー（第1弾：E1 遠景の地形・E2 大気と光・E3 河川と水路）

使い方：
    blender --background heian_daidairi_detail_v20.blend \
        --python build_environment.py -- <保存する.blend> [--no-render] [--time day|morning|evening]

開いたモデルに環境レイヤーを足して保存し、確認画像を描く。既存の
コレクション（大内裏・推定・内部・市街・外観精密化）には触れない。
再実行すると環境レイヤーの中身だけを入れ替える。
提案は docs/proposal/01_non-building-enrichment.md、記録は 12_environment-layer.md。

入力：
- 標高タイル：<HEIAN_WORK>/dem（scripts/fetch_dem.py で取得。HEIAN_DEM で変更可）
- 河川・池・運河・湿地：data/heiankyo_environment_v1.csv（確度と根拠つき）

内容：
- E1 遠景の地形：国土地理院の標高タイルから、京都盆地を囲む山（東山・
  北山・西山、船岡山・双ヶ岡などの丘）の形だけを取り出した地形メッシュ。
  盆地の床は北から南へ傾いているので、京の範囲で求めた傾き（平面）を
  差し引き、その上に5m以上出る部分だけを残す。京の範囲とその周り
  （約1km）、河川と池の周りは0に均す。現代の造成地形を持ち込まないため。
  地形の外側は遠景用の平らな地面でつなぐ。
- E2 大気と光：霞（地表から高さ700mの箱に入れた低密度の散乱ボリューム）、空のグラデーションに
  雲の層を足し、太陽と空を時刻のプリセット（day / morning / evening）で
  切り替えられるようにした。保存は day。
- E3 河川と水路：鴨川・桂川（下流と宇治川を含む）、巨椋池、堀川・西堀川
  （護岸・橋つき）、右京南西部の湿地（水たまりと葦）。

属性：全オブジェクトに evidence（terrain_dem / environment_csv /
procedural_env）、certainty（A〜D）、feature_id を付ける。コレクションは
COL_91_Environment（COL_90_Interior とは別）。消せば v20 に戻る（ただし
ワールドと太陽の設定、レンダー設定の変更は残る。12_environment-layer.md 参照）。
座標系は他のレイヤーと共通（朱雀門中心が原点、X=東、Y=北、実寸m）。
"""
import bpy
import os
import sys as _sys
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_SCRIPT_DIR)
_sys.path.insert(0, _SCRIPT_DIR)
from heian_gpu import use_gpu  # noqa: E402  GPU があれば使う（HEIAN_DEVICE=CPU で無効）
from heian_time import apply_time  # noqa: E402  時刻のプリセット（昼・朝・夕・夜）
# 生成物（.blend・画像）の置き場所。環境変数 HEIAN_WORK で変更できる（既定: <リポジトリ>/output）
WORK = os.environ.get("HEIAN_WORK", os.path.join(_REPO, "output"))
os.makedirs(WORK, exist_ok=True)
import csv
import glob
import importlib.util
import math
import random
import re
import time

import numpy as np
from mathutils import Vector

spec = importlib.util.spec_from_file_location(
    "build_detail", os.path.join(_SCRIPT_DIR, "build_chodoin_detailed.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

T0 = time.time()


def log(*a):
    print(*a, "t=%.0fs" % (time.time() - T0), flush=True)


# ---------------------------------------------------------------- 引数
argv = _sys.argv[_sys.argv.index("--") + 1:] if "--" in _sys.argv else []
OUT_BLEND = os.path.abspath(argv[0]) if argv and not argv[0].startswith("--") else \
    os.path.join(WORK, "heian_daidairi_detail_v21.blend")
DO_RENDER = "--no-render" not in argv
SAVE_TIME = argv[argv.index("--time") + 1] if "--time" in argv else "day"
OUT = os.path.join(WORK, "view_v21")
DEM_DIR = os.environ.get("HEIAN_DEM", os.path.join(WORK, "dem"))
CSV_PATH = os.path.join(_REPO, "data", "heiankyo_environment_v1.csv")

# ---------------------------------------------------------------- 地理座標とモデル座標
# 原点（朱雀門中心）の緯度経度。承香殿の石標（KA133、北緯35°01′15.1″・東経135°44′39.8″、
# 08_layout-v31-correction.md）がモデル座標 (280, 830) にあることから逆算した。
LAT0, LON0 = 35.013380, 135.741318
M_PER_DEG_LAT = 110950.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(LAT0))


def latlon_to_xy(lat, lon):
    return (lon - LON0) * M_PER_DEG_LON, (lat - LAT0) * M_PER_DEG_LAT


# 京（市街レイヤー）の外形。市街の町は x=±2170、南端 y=-3850（羅城）、宮の北辺 y=1405
CITY_X = 2170.0
CITY_S, CITY_N = -3850.0, 1405.0
CITY_GROUND = (-2350.0, 2350.0, -4100.0, 1900.0)   # 市街レイヤーの地面板（CITY_Ground）の範囲

# ---------------------------------------------------------------- コレクションと共通
col = bpy.data.collections.get("COL_91_Environment")
if col is None:
    col = bpy.data.collections.new("COL_91_Environment")
    bpy.context.scene.collection.children.link(col)
for _ob in list(col.objects):
    bpy.data.objects.remove(_ob, do_unlink=True)
col["layer"] = "environment"


def tag(ob, evidence, certainty, fid):
    ob["evidence"] = evidence
    ob["certainty"] = certainty
    ob["facility_id"] = fid
    return ob


def link_mesh(name, verts, faces, mat, evidence, certainty, fid, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    if smooth:
        me.shade_smooth()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return tag(ob, evidence, certainty, fid)


_cube = {}


def box(name, loc, dims, mat, evidence, certainty, fid, rot_z=0.0):
    """共有の単位立方体メッシュを使う高速な箱（市街レイヤーと同じ方式）。"""
    me = _cube.get(mat.name)
    if me is None:
        me = bpy.data.meshes.new("EnvCube_" + mat.name)
        me.from_pydata(
            [(-.5, -.5, -.5), (.5, -.5, -.5), (.5, .5, -.5), (-.5, .5, -.5),
             (-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5)], [],
            [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)])
        me.update()
        me.materials.append(mat)
        _cube[mat.name] = me
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    ob.scale = dims
    ob.rotation_euler.z = rot_z
    col.objects.link(ob)
    return tag(ob, evidence, certainty, fid)


def get_mat(name, *a, **kw):
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    return mod.make_mat(name, *a, **kw)


MAT_WATER = get_mat("MAT_EnvWater", (0.085, 0.14, 0.16), roughness=0.07,
                    color2=(0.06, 0.11, 0.13), tex_scale=0.02, bump=0.02)
def make_riverbed_mat():
    """河原：帯の幅方向の UV（u=0〜1）を使い、流れに近い中央は砂礫、岸寄りは草地。
    境目はノイズで崩し、砂州と草の島がまだらに出るようにする。"""
    m = bpy.data.materials.get("MAT_EnvRiverbed")
    if m is not None:
        return m
    m = bpy.data.materials.new("MAT_EnvRiverbed")
    m.diffuse_color = (0.45, 0.44, 0.38, 1)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 1.0
    N = nt.nodes.new
    tc = N("ShaderNodeTexCoord")
    sep = N("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["UV"], sep.inputs["Vector"])
    center = N("ShaderNodeMath")          # 中央からの距離 |u-0.5|（0=中央、0.5=岸）
    center.operation = "SUBTRACT"
    center.inputs[1].default_value = 0.5
    nt.links.new(sep.outputs["X"], center.inputs[0])
    ab = N("ShaderNodeMath")
    ab.operation = "ABSOLUTE"
    nt.links.new(center.outputs[0], ab.inputs[0])
    noise = N("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.012
    noise.inputs["Detail"].default_value = 5.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    nz = N("ShaderNodeMath")
    nz.operation = "MULTIPLY_ADD"          # ノイズ×0.7＋|u-0.5|。0.52〜0.60 を境に草地へ
    nz.inputs[1].default_value = 0.7
    nt.links.new(noise.outputs["Fac"], nz.inputs[0])
    nt.links.new(ab.outputs[0], nz.inputs[2])
    edge = N("ShaderNodeMapRange")
    edge.inputs["From Min"].default_value = 0.52
    edge.inputs["From Max"].default_value = 0.60
    nt.links.new(nz.outputs[0], edge.inputs["Value"])
    fine = N("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 0.08
    fine.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], fine.inputs["Vector"])
    _, f1, a1, b1, gravel = mix_rgb(nt)
    nt.links.new(fine.outputs["Fac"], f1)
    a1.default_value = (0.45, 0.43, 0.38, 1)
    b1.default_value = (0.34, 0.33, 0.29, 1)
    _, f2, a2, b2, grass = mix_rgb(nt)
    nt.links.new(fine.outputs["Fac"], f2)
    a2.default_value = (0.20, 0.28, 0.11, 1)
    b2.default_value = (0.30, 0.34, 0.15, 1)
    _, f3, a3, b3, res = mix_rgb(nt)
    nt.links.new(edge.outputs["Result"], f3)
    nt.links.new(gravel, a3)
    nt.links.new(grass, b3)
    nt.links.new(res, bsdf.inputs["Base Color"])
    bump = N("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.4
    nt.links.new(fine.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


MAT_WET = get_mat("MAT_EnvWetGround", (0.20, 0.22, 0.12), roughness=0.85,
                  color2=(0.15, 0.17, 0.09), tex_scale=0.05, bump=0.2)
MAT_SHORE = get_mat("MAT_EnvShoreReed", (0.42, 0.43, 0.25), roughness=1.0,
                    color2=(0.33, 0.36, 0.19), tex_scale=0.01, bump=0.2)
MAT_REED = get_mat("MAT_EnvReed", (0.22, 0.27, 0.10), roughness=0.95,
                   color2=(0.36, 0.34, 0.15), tex_scale=0.4, bump=0.1)
MAT_WOOD = bpy.data.materials.get("MAT_WoodDark") or get_mat("MAT_WoodDark", (0.32, 0.21, 0.12))
MAT_WOOD_L = bpy.data.materials.get("MAT_WoodLight") or get_mat("MAT_WoodLight", (0.52, 0.42, 0.30))
MAT_STONE = bpy.data.materials.get("MAT_Stone") or get_mat("MAT_Stone", (0.56, 0.54, 0.50))


def mix_rgb(nt):
    """RGBA の ShaderNodeMix を作り、(Factor, A, B, Result) のソケットを返す。
    Mix ノードは型ごとに同名のソケット（A・B）を持つので、名前ではなく型で選ぶ。"""
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    ins = [s for s in mx.inputs if s.type == "RGBA"]
    outs = [s for s in mx.outputs if s.type == "RGBA"]
    return mx, mx.inputs[0], ins[0], ins[1], outs[0]


def make_terrain_mat():
    """高さで盆地の床（草地・田畑の色）と山（森の色）を塗り分ける地形マテリアル。"""
    m = bpy.data.materials.get("MAT_EnvTerrain")
    if m is not None:
        return m
    m = bpy.data.materials.new("MAT_EnvTerrain")
    m.diffuse_color = (0.2, 0.3, 0.15, 1)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 1.0
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs["Vector"])
    hfac = nt.nodes.new("ShaderNodeMapRange")
    hfac.inputs["From Min"].default_value = 3.0
    hfac.inputs["From Max"].default_value = 40.0
    nt.links.new(sep.outputs["Z"], hfac.inputs["Value"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.0025
    noise.inputs["Detail"].default_value = 6.0
    nt.links.new(geo.outputs["Position"], noise.inputs["Vector"])
    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 0.03
    fine.inputs["Detail"].default_value = 4.0
    nt.links.new(geo.outputs["Position"], fine.inputs["Vector"])

    def mix(a, b, fac_socket):
        _, fac, sa, sb, res = mix_rgb(nt)
        nt.links.new(fac_socket, fac)
        for val, sock in ((a, sa), (b, sb)):
            if isinstance(val, tuple):
                sock.default_value = (*val, 1)
            else:
                nt.links.new(val, sock)
        return res

    # 盆地の床：ボロノイの区画（約120m）ごとに、青い稲・熟れた稲・休耕の草地・畑の土の色を
    # 割り当て、京の外の平地を田畑の継ぎはぎに見せる（第2弾 E5、確度D）
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 0.0085
    vor.inputs["Randomness"].default_value = 0.85
    nt.links.new(geo.outputs["Position"], vor.inputs["Vector"])
    cell = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(vor.outputs["Color"], cell.inputs["Color"])
    f_a = mix((0.33, 0.40, 0.17), (0.45, 0.43, 0.22), cell.outputs[0])
    f_b = mix((0.37, 0.36, 0.25), (0.40, 0.33, 0.22), cell.outputs[1])
    patch = mix(f_a, f_b, cell.outputs[2])
    floor = patch
    forest = mix((0.085, 0.15, 0.075), (0.15, 0.21, 0.10), noise.outputs["Fac"])
    forest = mix(forest, (0.06, 0.11, 0.06), fine.outputs["Fac"])
    col_out = mix(floor, forest, hfac.outputs["Result"])
    nt.links.new(col_out, bsdf.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    nt.links.new(fine.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


MAT_TERRAIN = make_terrain_mat()
MAT_RIVERBED = make_riverbed_mat()


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------- CSV（河川・池・運河・湿地）
FEATURES = []
with open(CSV_PATH, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        nums = [[float(v) for v in p.split()] for p in row["points"].split(";")]
        if row["coord"] == "latlon":
            if row["type"] == "lake":
                la, lo, a, b = nums[0]
                pts = [(*latlon_to_xy(la, lo), a, b)]
            else:
                pts = [latlon_to_xy(la, lo) for la, lo in nums]
        else:
            pts = [tuple(p) for p in nums]
        row["pts"] = pts
        FEATURES.append(row)
log("CSV_LOADED", len(FEATURES))


def densify(pts, step=60.0):
    """Catmull-Rom で折れ線をなめらかにし、約 step m ごとの点列にする。"""
    P = [Vector((p[0], p[1], 0)) for p in pts]
    if len(P) < 3:
        out = []
        for a, b in zip(P[:-1], P[1:]):
            n = max(1, int((b - a).length / step))
            out += [a.lerp(b, i / n) for i in range(n)]
        return out + [P[-1]]
    ext = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        n = max(2, int((p2 - p1).length / step))
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-1])
    return out


def keep_clear_of_city(pts, clearance=300.0, slope=0.3):
    """京の東西端から clearance m 以内に入る区間を外へ押し出す（河川用）。
    押し出し量は前後へ傾き slope でなだらかに減らし、折れ曲がりを作らない。"""
    need = []
    for p in pts:
        s_ = 0.0
        if CITY_S - clearance < p.y < CITY_N + clearance and abs(p.x) < CITY_X + clearance:
            s_ = CITY_X + clearance - abs(p.x)
        need.append(s_)
    out = []
    for i, p in enumerate(pts):
        sh = max([n - abs(p.y - q.y) * slope for n, q in zip(need, pts)] + [0.0])
        out.append(Vector((p.x + math.copysign(sh, p.x), p.y, 0)))
    return out


RIVERS = []   # (feature, 点列)
for ft in FEATURES:
    if ft["type"] == "river":
        line = densify(ft["pts"])
        if ft["feature_id"] == "RIV_KAMO":
            line = densify(keep_clear_of_city(line), 60.0)
        RIVERS.append((ft, line))
LAKES = [ft for ft in FEATURES if ft["type"] == "lake"]


def dist_to_polyline(X, Y, line):
    best = np.full(X.shape, 1e12)
    for a, b in zip(line[:-1], line[1:]):
        ax, ay, bx, by = a.x, a.y, b.x, b.y
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 < 1e-6:
            continue
        t = np.clip(((X - ax) * dx + (Y - ay) * dy) / L2, 0.0, 1.0)
        d2 = (X - ax - t * dx) ** 2 + (Y - ay - t * dy) ** 2
        np.minimum(best, d2, out=best)
    return np.sqrt(best)


def lake_radius(theta, a, b):
    """池の岸の半径（楕円にゆるい凹凸を足す。凹凸は固定）。"""
    wob = 1.0 + 0.07 * np.sin(3 * theta + 0.6) + 0.04 * np.sin(7 * theta + 1.9)
    return a * b / np.sqrt((b * np.cos(theta)) ** 2 + (a * np.sin(theta)) ** 2) * wob


def dist_to_lake(X, Y, lake):
    cx, cy, a, b = lake["pts"][0]
    dx, dy = X - cx, Y - cy
    r = np.hypot(dx, dy)
    th = np.arctan2(dy, dx)
    return np.maximum(r - lake_radius(th, a, b), 0.0)


# ---------------------------------------------------------------- E1 遠景の地形
def load_dem():
    files = glob.glob(os.path.join(DEM_DIR, "dem_*_*_*.txt"))
    if not files:
        raise RuntimeError("標高タイルがない: %s（scripts/fetch_dem.py で取得する）" % DEM_DIR)
    keys = []
    for p in files:
        z, tx, ty = map(int, re.findall(r"dem_(\d+)_(\d+)_(\d+)\.txt", os.path.basename(p))[0])
        keys.append((z, tx, ty, p))
    z = keys[0][0]
    tx0, tx1 = min(k[1] for k in keys), max(k[1] for k in keys)
    ty0, ty1 = min(k[2] for k in keys), max(k[2] for k in keys)
    arr = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256), dtype=np.float32)
    for _, tx, ty, p in keys:
        rows = open(p, encoding="ascii").read().strip().splitlines()
        a = np.array([[float(v) if v != "e" else 0.0 for v in r.split(",")] for r in rows],
                     dtype=np.float32)
        arr[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = a
    return arr, z, tx0, ty0


def dem_sampler(arr, z, tx0, ty0):
    n = 2 ** z * 256

    def to_px(X, Y):
        lat = LAT0 + Y / M_PER_DEG_LAT
        lon = LON0 + X / M_PER_DEG_LON
        fx = (lon + 180.0) / 360.0 * n - tx0 * 256 - 0.5
        lr = np.radians(lat)
        fy = (1.0 - np.log(np.tan(lr) + 1.0 / np.cos(lr)) / math.pi) / 2.0 * n - ty0 * 256 - 0.5
        return fx, fy

    def sample(X, Y):
        fx, fy = to_px(X, Y)
        fx = np.clip(fx, 0, arr.shape[1] - 1.001)
        fy = np.clip(fy, 0, arr.shape[0] - 1.001)
        ix, iy = fx.astype(int), fy.astype(int)
        ax, ay = fx - ix, fy - iy
        v00 = arr[iy, ix]
        v10 = arr[iy, ix + 1]
        v01 = arr[iy + 1, ix]
        v11 = arr[iy + 1, ix + 1]
        return (v00 * (1 - ax) + v10 * ax) * (1 - ay) + (v01 * (1 - ax) + v11 * ax) * ay

    # タイル群が覆う範囲（モデル座標）
    def px_to_xy(px, py):
        lon = (px + tx0 * 256) / n * 360.0 - 180.0
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (py + ty0 * 256) / n))))
        return latlon_to_xy(lat, lon)
    xa, yb = px_to_xy(0, arr.shape[0])
    xb, ya = px_to_xy(arr.shape[1], 0)
    return sample, (xa, xb, yb, ya)


arr, dem_z, tx0, ty0 = load_dem()
sample, (bx0, bx1, by0, by1) = dem_sampler(arr, dem_z, tx0, ty0)
log("DEM_LOADED", arr.shape, "cover_x=%.0f..%.0f cover_y=%.0f..%.0f" % (bx0, bx1, by0, by1))

# 京の範囲の標高から盆地の床の傾き（平面）を求める
gx, gy = np.meshgrid(np.linspace(-CITY_X, CITY_X, 30), np.linspace(CITY_S, CITY_N, 40))
gh = sample(gx, gy)
A = np.c_[np.ones(gx.size), gx.ravel(), gy.ravel()]
coef, *_ = np.linalg.lstsq(A, gh.ravel(), rcond=None)
log("FLOOR_FIT h = %.2f + %.5f*x + %.5f*y (m)" % tuple(coef),
    "north=%.1f south=%.1f" % (coef[0] + coef[2] * CITY_N, coef[0] + coef[2] * CITY_S))

STEP = 75.0
MARGIN = 300.0
xs = np.arange(math.ceil((bx0 + MARGIN) / STEP) * STEP, bx1 - MARGIN, STEP)
ys = np.arange(math.ceil((by0 + MARGIN) / STEP) * STEP, by1 - MARGIN, STEP)
X, Y = np.meshgrid(xs, ys)
H = sample(X, Y)
# 傾きは京の範囲の外では延ばさない（南の平野まで延ばすと平地が持ち上がるため）
base = coef[0] + coef[1] * np.clip(X, -CITY_X, CITY_X) + coef[2] * np.clip(Y, CITY_S, CITY_N)
Hr = np.maximum(H - base - 5.0, 0.0)
# 京の範囲とその周りは均す
ddx = np.maximum(np.maximum(X - (CITY_X + 60), -(CITY_X + 60) - X), 0.0)
ddy = np.maximum(np.maximum(Y - (CITY_N + 60), (CITY_S - 100) - Y), 0.0)
mask = smoothstep(250.0, 1000.0, np.hypot(ddx, ddy))
# 河川と池の周りは均す
for ft, line in RIVERS:
    r = float(ft["bank_w_m"]) / 2.0
    mask *= smoothstep(r + 20.0, r + 450.0, dist_to_polyline(X, Y, line))
for lk in LAKES:
    mask *= smoothstep(60.0, 700.0, dist_to_lake(X, Y, lk))
# メッシュの縁は 3km かけて平地に落とす（外側の遠景地面とつなぐ）
edge = np.minimum.reduce([X - xs[0], xs[-1] - X, Y - ys[0], ys[-1] - Y])
mask *= smoothstep(0.0, 3000.0, edge)
Zt = Hr * mask
Zt = np.where(Zt < 0.05, -0.15, Zt)
in_ground = (X > CITY_GROUND[0]) & (X < CITY_GROUND[1]) & (Y > CITY_GROUND[2]) & (Y < CITY_GROUND[3])
Zt = np.where(in_ground, -0.6, Zt)
for name, (px, py) in (("funaokayama", latlon_to_xy(35.0365, 135.7428)),
                       ("narabigaoka", latlon_to_xy(35.0247, 135.7095)),
                       ("higashiyama_daimonji", latlon_to_xy(35.0247, 135.8003)),
                       ("hieizan", latlon_to_xy(35.0670, 135.8340)),
                       ("atagoyama", latlon_to_xy(35.0600, 135.6330))):
    j = int(np.argmin(np.abs(ys - py)))
    i = int(np.argmin(np.abs(xs - px)))
    log("PEAK", name, "xy=(%.0f,%.0f)" % (px, py), "dem=%.0f" % sample(np.array(px), np.array(py)),
        "model_z=%.0f" % Zt[j, i])

ny, nx = Zt.shape
verts = np.c_[X.ravel(), Y.ravel(), Zt.ravel()].tolist()
ii = np.arange(nx - 1)
jj = np.arange(ny - 1)
I, J = np.meshgrid(ii, jj)
a = (J * nx + I).ravel()
faces = np.c_[a, a + 1, a + nx + 1, a + nx].tolist()
terrain = link_mesh("ENV_Terrain_DEM", verts, faces, MAT_TERRAIN, "terrain_dem", "B", "ENV_TERRAIN",
                    smooth=True)
terrain["source_note"] = ("国土地理院 標高タイル（dem, z=%d）から山の形だけを取得。盆地の床は"
                          "京の範囲の傾きを差し引き5m未満を0に均した。京・河川・池の周りも均した" % dem_z)
log("TERRAIN_DONE verts=%d faces=%d" % (len(verts), len(faces)))
del verts, faces

# 地形の外側の遠景地面。霞の箱（±40km）の内側に収め、縁が霞に溶けるようにする
far = link_mesh("ENV_FarGround",
                [(-38000, -38000, -0.4), (38000, -38000, -0.4), (38000, 38000, -0.4), (-38000, 38000, -0.4)],
                [(0, 1, 2, 3)], MAT_TERRAIN, "procedural_env", "D", "ENV_TERRAIN")
far.location.z = -1.0   # 地形メッシュ（床 -0.15）より下

# ---------------------------------------------------------------- E3 河川と池
def ribbon(name, line, width, z, mat, evidence, certainty, fid):
    verts, faces = [], []
    n = len(line)
    for k, p in enumerate(line):
        a = line[max(k - 1, 0)]
        b = line[min(k + 1, n - 1)]
        t = (b - a)
        t.z = 0
        t.normalize()
        nrm = Vector((-t.y, t.x, 0))
        verts.append(tuple(p + nrm * (width / 2) + Vector((0, 0, z))))
        verts.append(tuple(p - nrm * (width / 2) + Vector((0, 0, z))))
        if k:
            faces.append((2 * k - 2, 2 * k - 1, 2 * k + 1, 2 * k))
    ob = link_mesh(name, verts, faces, mat, evidence, certainty, fid)
    # 幅方向の UV（左岸 u=0、右岸 u=1）。河原のマテリアルが砂礫と草の塗り分けに使う
    me = ob.data
    uv = me.uv_layers.new(name="UVMap")
    vi = [0] * len(me.loops)
    me.loops.foreach_get("vertex_index", vi)
    uv.data.foreach_set("uv", [c for v in vi for c in (float(v % 2), 0.0)])
    return ob


for ft, line in RIVERS:
    fid, cert = ft["feature_id"], ft["certainty"]
    bank = ribbon(fid + "_Riverbed", line, float(ft["bank_w_m"]), -0.10, MAT_RIVERBED,
                  "environment_csv", cert, fid)
    water = ribbon(fid + "_Water", line, float(ft["water_w_m"]), -0.06, MAT_WATER,
                   "environment_csv", cert, fid)
    for ob in (bank, water):
        ob["source_note"] = ft["basis_note"]
log("RIVERS_DONE", len(RIVERS))

for lk in LAKES:
    cx, cy, a_, b_ = lk["pts"][0]
    th = np.linspace(0, 2 * math.pi, 160, endpoint=False)
    for suffix, grow, z, mat in (("_Shore", 90.0, -0.10, MAT_SHORE), ("_Water", 0.0, -0.06, MAT_WATER)):
        rr = lake_radius(th, a_, b_) + grow
        verts = [(cx, cy, z)] + [(cx + r * math.cos(t), cy + r * math.sin(t), z) for r, t in zip(rr, th)]
        faces = [(0, k + 1, (k + 1) % len(th) + 1) for k in range(len(th))]
        ob = link_mesh(lk["feature_id"] + suffix, verts, faces, mat, "environment_csv",
                       lk["certainty"], lk["feature_id"])
        ob["source_note"] = lk["basis_note"]
log("LAKES_DONE", len(LAKES))

# ---------------------------------------------------------------- E3 堀川・西堀川
# 市街レイヤー（build_city_layer.py）の配置と合わせる：町ピッチ133m、宅地121m、
# 東西の大路は y=-550*b（幅24m）。運河は町境の小路（幅12m）の中央を通る。
PITCH, PLOT = 133.0, 121.0
EXCLUDE = {   # 市街レイヤー側の区画が模式で水路と重なる区間（y_min, y_max）
    840: [(-1934 - 135, -1934 + 135), (-270 - 215, -270 + 215)],   # 東市・神泉苑
    -840: [(-1934 - 135, -1934 + 135)],                          # 西市
}


def excluded(x, y0, y1):
    return any(y0 < b and a < y1 for a, b in EXCLUDE.get(int(round(x)), []))


def row_gaps():
    """町と町の間（東西の小路）の y。宮の両側の10列と、二条〜八条の各帯の帯内3本。"""
    g = [r * PITCH for r in range(1, 10)]
    for band in range(7):
        for r in range(1, 4):
            g.append(-(band * 550 + 18 + r * PITCH))
    return g


n_canal = 0
for ft in FEATURES:
    if ft["type"] != "canal":
        continue
    fid, cert = ft["feature_id"], ft["certainty"]
    (x, ytop), (_, ybot) = ft["pts"]
    ww = float(ft["water_w_m"])
    # 区間に分ける（除外区間で切る）
    cuts = sorted([ybot, ytop] + [v for ab in EXCLUDE.get(int(round(x)), []) for v in ab])
    segs = [(a, b) for a, b in zip(cuts[:-1], cuts[1:]) if not excluded(x, a + 1, b - 1) and b - a > 5]
    for k, (y0, y1) in enumerate(segs):
        L, cy = y1 - y0, (y0 + y1) / 2
        box("%s_Water_%d" % (fid, k), (x, cy, 0.0), (ww, L, 0.04), MAT_WATER, "environment_csv", cert, fid)
        for sgn in (-1, 1):   # 護岸（板の土留め）と岸の土手
            box("%s_Bank_%d" % (fid, k), (x + sgn * (ww / 2 + 0.15), cy, 0.12), (0.3, L, 0.4),
                MAT_WOOD, "environment_csv", "D", fid)
            box("%s_Levee_%d" % (fid, k), (x + sgn * (ww / 2 + 1.3), cy, 0.03), (2.0, L, 0.08),
                MAT_RIVERBED, "environment_csv", "D", fid)
        n_canal += 1
    # 東西の大路との交差に橋（欄干つき）
    for b in range(1, 8):
        y = -550.0 * b
        if excluded(x, y - 14, y + 14) or not (ybot < y < ytop):
            continue
        box("%s_Bridge%d_Deck" % (fid, b), (x, y, 0.22), (ww + 5, 26, 0.25), MAT_WOOD_L,
            "procedural_env", "D", fid)
        for sgn in (-1, 1):
            box("%s_Bridge%d_Rail" % (fid, b), (x + sgn * (ww / 2 + 2.2), y, 0.75), (0.18, 26, 0.12),
                MAT_WOOD, "procedural_env", "D", fid)
            for py in (-12, -4, 4, 12):
                box("%s_Bridge%d_Post" % (fid, b), (x + sgn * (ww / 2 + 2.2), y + py, 0.5),
                    (0.2, 0.2, 0.6), MAT_WOOD, "procedural_env", "D", fid)
    # 町境の小路には板橋
    for y in row_gaps():
        if excluded(x, y - 6, y + 6) or not (ybot < y < ytop):
            continue
        box("%s_Plank" % fid, (x, y, 0.2), (ww + 3, 4.0, 0.15), MAT_WOOD_L, "procedural_env", "D", fid)
    # 宮の南（二条大路）の前の橋
    box("%s_BridgeNijo_Deck" % fid, (x, -9.0, 0.22), (ww + 5, 30, 0.25), MAT_WOOD_L,
        "procedural_env", "D", fid)
log("CANALS_DONE segments=%d" % n_canal)

# ---------------------------------------------------------------- E3 右京南西部の湿地
rng = random.Random(1919)
n_marsh = 0
reed_pts = 0
for ft in FEATURES:
    if ft["type"] != "marsh":
        continue
    x0, x1, y0, y1 = ft["pts"][0]
    fields = [o for o in bpy.data.objects
              if o.name.endswith("_Field") and x0 < o.location.x < x1 and y0 < o.location.y < y1]
    fields.sort(key=lambda o: (round(o.location.x), round(o.location.y)))
    for fo in fields:
        if rng.random() > 0.42:
            continue
        cx, cy = fo.location.x, fo.location.y
        # 湿った地面（畑の畝を覆う暗い面）を不定形に2〜3枚重ねる
        for k in range(rng.randint(2, 3)):
            box("%s_Marsh_Wet%d" % (fo.name, k),
                (cx + rng.uniform(-18, 18), cy + rng.uniform(-18, 18), 0.155),
                (rng.uniform(60, 100), rng.uniform(50, 90), 0.04), MAT_WET, "procedural_env", "D",
                ft["feature_id"], rot_z=rng.uniform(-0.4, 0.4))
        for k in range(rng.randint(2, 4)):
            px, py = cx + rng.uniform(-35, 35), cy + rng.uniform(-35, 35)
            box("%s_Marsh_Pool%d" % (fo.name, k), (px, py, 0.17), (rng.uniform(18, 40), rng.uniform(12, 30), 0.04),
                MAT_WATER, "procedural_env", "D", ft["feature_id"], rot_z=rng.uniform(0, math.pi))
            for _ in range(rng.randint(28, 44)):
                ang = rng.uniform(0, 2 * math.pi)
                rr = rng.uniform(7, 20)
                h = rng.uniform(1.4, 2.6)
                box("%s_Marsh_Reed" % fo.name, (px + rr * math.cos(ang), py + rr * math.sin(ang), h / 2),
                    (rng.uniform(0.4, 1.1), rng.uniform(0.4, 1.1), h), MAT_REED, "procedural_env", "D",
                    ft["feature_id"], rot_z=rng.uniform(0, math.pi))
                reed_pts += 1
        n_marsh += 1
log("MARSH_DONE fields=%d reeds=%d" % (n_marsh, reed_pts))

# ---------------------------------------------------------------- E2 大気と光
# 時刻のプリセット（PRESETS）と apply_time は heian_time.py に置く（第2弾と共用）


def setup_world():
    """空のグラデーション＋雲の層＋霞（散乱ボリューム）。値は apply_time で入れる。"""
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    N = nt.nodes.new
    out = N("ShaderNodeOutputWorld")
    bg = N("ShaderNodeBackground")
    bg.name = "HEIAN_Bg"
    coord = N("ShaderNodeTexCoord")
    sep = N("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Generated"], sep.inputs["Vector"])
    grad = N("ShaderNodeMapRange")
    grad.inputs["From Min"].default_value = 0.0
    grad.inputs["From Max"].default_value = 0.38
    grad.interpolation_type = "SMOOTHSTEP"
    nt.links.new(sep.outputs["Z"], grad.inputs["Value"])
    sky, sky_f, sky_a, sky_b, sky_r = mix_rgb(nt)
    sky.name = "HEIAN_SkyMix"
    nt.links.new(grad.outputs["Result"], sky_f)
    # 雲：視線を高さ1の平面へ投影した座標でノイズを引く
    zz = N("ShaderNodeMath")
    zz.operation = "MAXIMUM"
    zz.inputs[1].default_value = 0.04
    nt.links.new(sep.outputs["Z"], zz.inputs[0])
    u = N("ShaderNodeMath")
    u.operation = "DIVIDE"
    nt.links.new(sep.outputs["X"], u.inputs[0])
    nt.links.new(zz.outputs[0], u.inputs[1])
    v = N("ShaderNodeMath")
    v.operation = "DIVIDE"
    nt.links.new(sep.outputs["Y"], v.inputs[0])
    nt.links.new(zz.outputs[0], v.inputs[1])
    comb = N("ShaderNodeCombineXYZ")
    nt.links.new(u.outputs[0], comb.inputs["X"])
    nt.links.new(v.outputs[0], comb.inputs["Y"])
    comb.inputs["Z"].default_value = 3.7
    noise = N("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.9
    noise.inputs["Detail"].default_value = 7.0
    noise.inputs["Roughness"].default_value = 0.55
    nt.links.new(comb.outputs[0], noise.inputs["Vector"])
    ramp = N("ShaderNodeMapRange")
    ramp.name = "HEIAN_CloudRamp"
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Value"])
    fade = N("ShaderNodeMapRange")
    fade.inputs["From Min"].default_value = 0.03
    fade.inputs["From Max"].default_value = 0.25
    nt.links.new(sep.outputs["Z"], fade.inputs["Value"])
    cmask = N("ShaderNodeMath")
    cmask.operation = "MULTIPLY"
    nt.links.new(ramp.outputs["Result"], cmask.inputs[0])
    nt.links.new(fade.outputs["Result"], cmask.inputs[1])
    # 雲の陰影：細かいノイズで、雲の色と影の色を混ぜる
    shn = N("ShaderNodeTexNoise")
    shn.inputs["Scale"].default_value = 2.6
    shn.inputs["Detail"].default_value = 4.0
    nt.links.new(comb.outputs[0], shn.inputs["Vector"])
    shr = N("ShaderNodeMapRange")
    shr.inputs["From Min"].default_value = 0.35
    shr.inputs["From Max"].default_value = 0.65
    nt.links.new(shn.outputs["Fac"], shr.inputs["Value"])
    ctone, ct_f, ct_a, ct_b, ct_r = mix_rgb(nt)
    ctone.name = "HEIAN_CloudTone"
    nt.links.new(shr.outputs["Result"], ct_f)
    cloud, cl_f, cl_a, cl_b, cl_r = mix_rgb(nt)
    cloud.name = "HEIAN_CloudMix"
    nt.links.new(cmask.outputs[0], cl_f)
    nt.links.new(sky_r, cl_a)
    nt.links.new(ct_r, cl_b)
    nt.links.new(cl_r, bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    return world


HAZE_TOP = 700.0   # 霞の層の厚さ（m）


def setup_haze():
    """霞：地表から HAZE_TOP m までの箱に低密度の散乱ボリュームを入れる。
    ワールド全体のボリュームにすると、無限遠の太陽と空の光がすべて吸収されて
    画面が真っ黒になるため、有限の箱にしている（山頂は層の上に出る）。"""
    m = bpy.data.materials.get("MAT_EnvHaze")
    if m is None:
        m = bpy.data.materials.new("MAT_EnvHaze")
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        vol = nt.nodes.new("ShaderNodeVolumeScatter")
        vol.name = "HEIAN_Haze"
        vol.inputs["Anisotropy"].default_value = 0.55
        nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    ob = box("ENV_HazeVolume", (0, 0, HAZE_TOP / 2 - 2.0), (80000, 80000, HAZE_TOP), m,
             "procedural_env", "-", "ENV_ATMOSPHERE")
    ob.visible_shadow = False
    return m


setup_world()
setup_haze()
apply_time(SAVE_TIME)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.use_denoising = True       # 霞（ボリューム）のノイズを抑える
scene.cycles.volume_bounces = 0     # 霞は一次散乱だけで足りる（速度優先）
for cam in bpy.data.cameras:            # 既存カメラの描画距離を遠景の山まで延ばす
    cam.clip_end = max(cam.clip_end, 60000.0)
log("ATMOSPHERE_DONE time=%s" % SAVE_TIME)

n_env = len(col.objects)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
log("SAVED", OUT_BLEND, "env_objects=%d" % n_env)

# ---------------------------------------------------------------- 確認描画
if DO_RENDER:
    use_gpu(scene)
    cam_data = bpy.data.cameras.new("V21Cam")
    cam_data.clip_start = 0.3
    cam_data.clip_end = 80000
    cam = bpy.data.objects.new("V21Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    # 試し描き用：HEIAN_SAMPLES でサンプル数、HEIAN_SHOTS（カンマ区切り）で描くカットを絞れる
    ONLY = [s for s in os.environ.get("HEIAN_SHOTS", "").split(",") if s]

    def shot(name, loc, target, lens=35, w=1280, h=720, samples=48, tod="day"):
        if ONLY and name not in ONLY:
            return
        samples = int(os.environ.get("HEIAN_SAMPLES", samples))
        apply_time(tod)
        cam.location = loc
        cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        cam_data.lens = lens
        scene.render.resolution_x, scene.render.resolution_y = w, h
        scene.cycles.samples = samples
        scene.render.filepath = OUT + "_" + name + ".png"
        t = time.time()
        bpy.ops.render.render(write_still=True)
        log("RENDERED", name, "sec=%.0f" % (time.time() - t))

    shot("basin", (0, -9500, 2200), (0, 1500, 0), lens=30)
    shot("north", (0, 250, 22), (0, 3500, 80), lens=32)
    shot("east", (-1600, -1500, 380), (4500, -700, 120), lens=35)
    shot("kamo", (2560, -2700, 30), (2660, 200, 0), lens=35)
    shot("horikawa", (848, -1240, 4.5), (840, -1080, 0.5), lens=28)
    shot("marsh", (-1350, -3050, 70), (-1750, -3500, 0), lens=35)
    shot("south_evening", (0, 60, 32), (0, -3500, 0), lens=32, tod="evening")
    shot("east_morning", (-1600, -1500, 380), (4500, -700, 120), lens=35, tod="morning")
    apply_time(SAVE_TIME)
log("ENV_DONE")
