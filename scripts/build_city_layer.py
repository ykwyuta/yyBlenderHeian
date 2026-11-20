"""平安京・市街レイヤー生成スクリプト（模式生成）v6

使い方：
    blender --background heian_daidairi_detail_v14.blend \
        --python build_city_layer.py

モデルを開いた状態で実行し、既存の市街レイヤーを消してから作り直し、
heian_daidairi_detail_v15.blend として保存し、確認画像を描く。
（市街コレクションの中身だけを入れ替えるので、大内裏・推定・
内部のレイヤーには触れない。）

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

v2での作り込み（2026-11-19）：
- 配分に「塊化」を入れた。初期抽選のあと近傍の多数派へ寄せる平滑化を
  2回かけ、貴族街区・庶民街区・農地帯がかたまりになるようにした
  （v1の市松模様の解消）。
- 家屋のバリエーション：屋根は寄棟と切妻を使い分け（貴族邸の主殿は
  入母屋風に小さな切妻を載せる）、寸法にばらつきを持たせた。庶民町には
  長屋・井戸・小屋が混ざる。官人宅は表通りに低い塀と門を持つ。
- 畑には畝（細い帯）を入れ、作物の色を2色で割った。
- 街路樹は円盤をやめ、塊状の樹冠を持つ樹木にした。

v3での作り込み（2026-11-20、近景対策）：
- 全家屋に南面の扉と窓（蔀を思わせる暗い板面）を付け、大きな家には
  縁側の板と踏み石も付ける。開口は板面による表現で、貫通はしていない。
- 長屋は扉を板面に直し、戸口の間に小窓と前面の踏み板を付けた。
- 官人宅の門に扉と小屋根、殿舎（hall_fast）に入口の扉・窓・石段を付けた。
- 樹木は幹を円柱にし、樹冠を3つの塊の重なりにした。
- 朱雀大路の両側に側溝（水面の帯）、市場の屋台に暖簾、庶民町の一部に
  通り沿いの生垣を付けた。

v4での作り込み（2026-11-20）：
- 地面と大路が淡く白っぽく見えたため、市街専用の地面・大路マテリアル
  （色を深くし、凹凸と色むらを強めたもの）に切り替えた。大内裏側の
  共有マテリアルには触れていない。
- 大きな家の窓に格子の桟と扉の鴨居、切妻屋根（長さ14m以上）に棟と
  鬼瓦風の端飾り、井戸に釣瓶と縄を追加。
- 二条・五条の大路の南側に街路樹の並木を追加。
- 朱雀大路と東市の入口に牛車（御所車風、模式）を置いた。

v5での作り込み（2026-11-20）：
- 大きな家の扉に方立、窓に窓台を付けて開口まわりの納まりを付けた。
- 庶民の家の一部に薪の束と樽の小物（専用の乱数で抽選し、既存の
  配置の乱数列には影響させない）。
- 貴族邸の池のほとりと神泉苑に石灯籠、寺と東寺・西寺に鐘楼。
- 朱雀大路の側溝が大路を横切る箇所に木橋（14箇所）。
- 市場の屋台の一部に樽と箱、五条大路と朱雀大路に荷車。

v6での作り込み（2026-11-20）：
- 板葺屋根に濃い色のバリエーション（専用乱数で約4割）、樹冠に
  明るい緑のバリエーションを持たせ、町並みの単調さを減らした。
- 庶民町に表の板塀（生垣のない町の一部）、官人宅に馬屋、
  貴族邸の池の南に釣殿風の小亭。
- 朱雀大路の側溝に、町への出入りの小橋（板橋）を等間隔に架けた。

実装上の注意：約2.5万オブジェクトを bpy.ops 経由で作ると場面の
肥大化に伴って指数的に遅くなる（実測で40分でも終わらなかった）。
そのため市街レイヤーの部品は、共有メッシュ＋オブジェクト配置だけの
高速プリミティブで作る。
"""
import bpy
import importlib.util
import math
import random
import sys
from mathutils import Vector

spec = importlib.util.spec_from_file_location(
    "build_detail",
    "/home/hatch/docs/proposal/history/3d/heiankyo-blender/scripts/build_chodoin_detailed.py")
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
mod.MAT["field2"] = mod.make_mat("MAT_FieldGreen2", (0.48, 0.55, 0.26), roughness=0.95, color2=(0.40, 0.47, 0.21), tex_scale=0.5, bump=0.2)
mod.MAT["wood2"] = mod.make_mat("MAT_WoodLight", (0.52, 0.42, 0.30), roughness=0.9, color2=(0.45, 0.36, 0.25), tex_scale=3.0, bump=0.15)
mod.MAT["ground2"] = mod.make_mat("MAT_CityGround", (0.40, 0.33, 0.23), roughness=1.0, color2=(0.31, 0.25, 0.17), tex_scale=0.25, bump=0.3)
mod.MAT["road2"] = mod.make_mat("MAT_CityRoad", (0.46, 0.43, 0.38), roughness=1.0, color2=(0.36, 0.33, 0.28), tex_scale=0.7, bump=0.35)
mod.MAT["sand2"] = mod.make_mat("MAT_CityThatch2", (0.44, 0.35, 0.22), roughness=1.0, color2=(0.36, 0.28, 0.17), tex_scale=2.0, bump=0.2)
mod.MAT["leaf2"] = mod.make_mat("MAT_CityLeaf2", (0.30, 0.45, 0.22), roughness=0.95, color2=(0.24, 0.38, 0.18), tex_scale=1.5, bump=0.15)
print("MAT_WIRED", flush=True)

rng = random.Random(818)
rng2 = random.Random(1234)   # v5の小物抽選専用（配置の乱数列を変えないため）
col = mod.get_or_make_collection("COL_70_City")
col["layer"] = "city_schematic"
# 既存の市街レイヤーがあれば入れ替える（他のレイヤーには触れない）
for _ob in list(col.objects):
    bpy.data.objects.remove(_ob, do_unlink=True)

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

def _smooth(t):
    return t * t * (3.0 - 2.0 * t)

def froof(name, cx, cy, w, d, eave_z, roof_h, mat_key, fid=""):
    """低分割の寄棟屋根。形状は (w,d,roof_h,mat) でキャッシュして共有する。"""
    key = ("hip", round(w), round(d), round(roof_h * 2), mat_key)
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
                verts.append((x, y, roof_h * _smooth(t)))
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
    if w >= d:
        fbox(name + "_Ridge", (cx, cy, eave_z + roof_h + 0.15), (max(0.4, w - d) + 0.8, 0.55, 0.3), mat_key, fid)
    else:
        fbox(name + "_Ridge", (cx, cy, eave_z + roof_h + 0.15), (0.55, max(0.4, d - w) + 0.8, 0.3), mat_key, fid)
    return ob

def froof_gable(name, cx, cy, w, d, eave_z, roof_h, mat_key, fid=""):
    """切妻屋根。断面（5点の折れ線）を長手方向に押し出した形状。
    棟方向は w が長い方。妻面は断面ポリゴンで閉じる。"""
    key = ("gable", round(w), round(d), round(roof_h * 2), mat_key)
    mesh = _roof_cache.get(key)
    if mesh is None:
        prof = []
        for t in (-1.0, -0.55, 0.0, 0.55, 1.0):
            z = roof_h * _smooth(1.0 - abs(t))
            prof.append((t * d / 2.0, z))
        verts = []
        for x in (-w / 2.0, w / 2.0):
            for (y, z) in prof:
                verts.append((x, y, z))
        faces = []
        for i in range(4):
            faces.append((i, 5 + i, 6 + i, i + 1))
        faces.append((0, 1, 2, 3, 4))          # 妻面（-x側）
        faces.append((9, 8, 7, 6, 5))          # 妻面（+x側）
        mesh = bpy.data.meshes.new("SharedGable")
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        for poly in mesh.polygons:
            poly.use_smooth = False
        mesh.materials.append(mod.MAT[mat_key])
        _roof_cache[key] = mesh
    ob = bpy.data.objects.new(name, mesh)
    ob.location = (cx, cy, eave_z)
    ob["facility_id"] = fid
    col.objects.link(ob)
    if w >= 14:
        fbox(name + "_Ridge", (cx, cy, eave_z + roof_h + 0.08), (w * 0.92, 0.42, 0.26), mat_key, fid)
        for sgn in (-1, 1):
            fbox(name + "_Oni", (cx + sgn * (w / 2 - 0.35), cy, eave_z + roof_h + 0.25),
                 (0.5, 0.6, 0.6), "wood", fid)
    return ob

_cyl_cache = {}

def fcyl(name, loc, scale, mat_key, fid=""):
    mesh = _cyl_cache.get(mat_key)
    if mesh is None:
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

_blob_meshes = {}

def fblob(name, loc, scale, fid="", mat_key="pine"):
    """塊状の樹冠（8角柱の3段重ね、低ポリゴン）。"""
    global _blob_meshes
    if mat_key not in _blob_meshes:
        rings = [(-0.5, 0.62), (-0.1, 1.0), (0.3, 0.82), (0.5, 0.30)]
        verts = []
        for (z, r) in rings:
            for k in range(8):
                a = 2 * math.pi * k / 8 + 0.39
                verts.append((r * math.cos(a), r * math.sin(a), z))
        faces = []
        for ri in range(3):
            for k in range(8):
                k2 = (k + 1) % 8
                a = ri * 8 + k
                faces.append((a, ri * 8 + k2, (ri + 1) * 8 + k2, (ri + 1) * 8 + k))
        faces.append(tuple(range(7, -1, -1)))
        faces.append(tuple(range(24, 32)))
        mesh = bpy.data.meshes.new("SharedCanopy_" + mat_key)
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        mesh.materials.append(mod.MAT[mat_key])
        _blob_meshes[mat_key] = mesh
    ob = bpy.data.objects.new(name, _blob_meshes[mat_key])
    ob.location = loc
    ob.scale = scale
    ob["facility_id"] = fid
    col.objects.link(ob)
    return ob

def ftree(prefix, x, y, s=1.0, fid=""):
    leaf = "leaf2" if rng2.random() < 0.35 else "pine"
    fcyl(prefix + "_Trunk", (x, y, 1.3 * s), (0.30 * s, 0.30 * s, 2.6 * s), "trunk", fid)
    fblob(prefix + "_Canopy", (x, y, 3.8 * s), (4.8 * s, 4.8 * s, 3.6 * s), fid, leaf)
    fblob(prefix + "_Canopy2", (x + 1.3 * s, y - 0.9 * s, 4.8 * s), (3.1 * s, 3.1 * s, 2.5 * s), fid, leaf)
    fblob(prefix + "_Canopy3", (x - 1.2 * s, y + 0.8 * s, 4.4 * s), (2.7 * s, 2.7 * s, 2.2 * s), fid, leaf)

def fwall(prefix, cx, cy, sx, sy, fid=""):
    """築地塀（高速版）。南辺中央に開口。"""
    inset, h, t = 1.2, 2.4, 0.7
    ix, iy = sx / 2 - inset, sy / 2 - inset
    runs = [("N", cx, cy + iy, 2 * ix, t), ("E", cx + ix, cy, t, 2 * iy), ("W", cx - ix, cy, t, 2 * iy)]
    gap = 8.0
    seg = (2 * ix - gap) / 2
    runs.append(("S1", cx - gap / 2 - seg / 2, cy - iy, seg, t))
    runs.append(("S2", cx + gap / 2 + seg / 2, cy - iy, seg, t))
    for tag, x, y, w, d in runs:
        fbox(prefix + "_Wall" + tag, (x, y, h / 2), (w, d, h), "white", fid)
        fbox(prefix + "_Cap" + tag, (x, y, h + 0.15), (w, d + 0.35, 0.3), "roof", fid)

def ffence(prefix, cx, cy, sx, fid=""):
    """官人宅の表塀（低い木塀、南辺のみ、中央に門の開口）。"""
    gap = 5.0
    seg = (sx - gap) / 2
    for tag, x in (("1", cx - gap / 2 - seg / 2), ("2", cx + gap / 2 + seg / 2)):
        fbox(prefix + "_Fence" + tag, (x, cy - PLOT / 2 + 1.0, 0.55), (seg, 0.25, 1.1), "wood", fid)
    for tag, ox in (("L", -2.5), ("R", 2.5)):
        fbox(prefix + "_GatePost" + tag, (cx + ox, cy - PLOT / 2 + 1.0, 1.1), (0.35, 0.35, 2.2), "wood", fid)
    fbox(prefix + "_GateTop", (cx, cy - PLOT / 2 + 1.0, 2.35), (6.2, 0.5, 0.3), "wood", fid)
    fbox(prefix + "_GateDoorL", (cx - 1.2, cy - PLOT / 2 + 1.0, 1.0), (2.2, 0.12, 2.0), "wood2", fid)
    fbox(prefix + "_GateDoorR", (cx + 1.2, cy - PLOT / 2 + 1.0, 1.0), (2.2, 0.12, 2.0), "wood2", fid)
    froof_gable(prefix + "_GateRoof", cx, cy - PLOT / 2 + 1.0, 7.2, 2.8, 2.5, 1.0, "roof", fid)

def house(prefix, x, y, w, d, roof_key, wall_key="wood", gable=False, fid=""):
    is_sand = (roof_key == "sand")
    if is_sand and rng2.random() < 0.4:
        roof_key = "sand2"   # 板葺の色バリエーション（v6、専用乱数）
    fbox(prefix + "_Wall", (x, y, 1.25), (w, d, 2.5), wall_key, fid)
    if gable:
        froof_gable(prefix + "_Roof", x, y, w + 1.8, d + 1.8, 2.5, 1.9, roof_key, fid)
    else:
        froof(prefix + "_Roof", x, y, w + 1.8, d + 1.8, 2.5, 1.8, roof_key, fid)
    # 近景の作り込み：南面に扉と窓（板面表現）、大きな家には縁側と踏み石
    door_mat = "wood2" if wall_key == "wood" else "wood"
    dx = (rng.random() - 0.5) * w * 0.3
    fbox(prefix + "_Door", (x + dx, y - d / 2 - 0.03, 0.95), (1.1, 0.1, 1.9), door_mat, fid)
    wx = dx + (w * 0.28 if dx <= 0 else -w * 0.28)
    wx = max(-w / 2 + 0.95, min(w / 2 - 0.95, wx))
    fbox(prefix + "_Window", (x + wx, y - d / 2 - 0.03, 1.55), (1.5, 0.1, 0.95), "roof", fid)
    if w >= 16:
        eng_mat = "wood" if wall_key == "wood2" else "wood2"
        fbox(prefix + "_Engawa", (x, y - d / 2 - 0.55, 0.09), (w * 0.85, 1.1, 0.18), eng_mat, fid)
        fbox(prefix + "_Step", (x + dx, y - d / 2 - 1.35, 0.11), (1.5, 0.7, 0.22), "stone", fid)
        for bx in (-0.38, 0.38):
            fbox(prefix + "_Lattice", (x + wx + bx, y - d / 2 - 0.09, 1.55), (0.07, 0.06, 0.95), door_mat, fid)
        fbox(prefix + "_Lintel", (x + dx, y - d / 2 - 0.05, 1.98), (1.5, 0.09, 0.14), door_mat, fid)
        for px in (-0.62, 0.62):
            fbox(prefix + "_DoorPost", (x + dx + px, y - d / 2 - 0.05, 0.95), (0.09, 0.09, 1.9), door_mat, fid)
        fbox(prefix + "_Sill", (x + wx, y - d / 2 - 0.06, 1.02), (1.7, 0.12, 0.1), door_mat, fid)
    # 庶民の家の一部に薪と樽（v5、専用乱数で抽選。判定は屋根色の
    # 差し替え前に取ること。v6で差し替え後の値で判定して薪が
    # 減る不具合があり、v15ではパッチで補った）
    if is_sand and rng2.random() < 0.35:
        px, py = x + w / 2 + 1.3, y - d / 4
        for i, (dy, lz) in enumerate(((-0.17, 0.17), (0.17, 0.17), (0.0, 0.47))):
            log = fcyl(prefix + "_Firewood%d" % i, (px, py + dy, lz), (0.16, 0.16, 1.4), "trunk", fid)
            log.rotation_euler.x = math.pi / 2
        fcyl(prefix + "_Barrel", (px + 1.3, py + 0.9, 0.4), (0.38, 0.38, 0.8), "trunk", fid)

def hall_fast(prefix, cx, cy, w, d, wall_h=4.0, roof_h=4.2, irimoya=False, fid=""):
    """殿舎の高速版：基壇＋白壁＋寄棟屋根（柱列は省略）。
    irimoya=True で屋根の上に小さな切妻を載せ、入母屋風にする。"""
    fbox(prefix + "_Kidan", (cx, cy, 0.4), (w + 3, d + 3, 0.8), "stone", fid)
    fbox(prefix + "_Wall", (cx, cy, 0.8 + wall_h / 2), (w, d, wall_h), "white", fid)
    froof(prefix + "_Roof", cx, cy, w + 5, d + 5, 0.8 + wall_h, roof_h, "roof", fid)
    # 近景の作り込み：南面中央に入口の扉と窓、前面に石段
    fbox(prefix + "_Door", (cx, cy - d / 2 - 0.03, 0.8 + 1.3), (3.2, 0.12, 2.6), "wood", fid)
    for sgn in (-1, 1):
        fbox(prefix + "_Window%d" % (1 if sgn > 0 else 0), (cx + sgn * w / 4, cy - d / 2 - 0.03, 0.8 + 2.1),
             (2.2, 0.1, 1.7), "wood", fid)
    fbox(prefix + "_StepLo", (cx, cy - (d + 3) / 2 - 0.4, 0.14), (4.4, 0.8, 0.27), "stone", fid)
    fbox(prefix + "_StepHi", (cx, cy - (d + 3) / 2 + 0.45, 0.27), (4.4, 0.8, 0.53), "stone", fid)
    if irimoya:
        froof_gable(prefix + "_RoofTop", cx, cy, (w + 5) * 0.42, (d + 5) * 0.52,
                    0.8 + wall_h + roof_h * 0.82, roof_h * 0.38, "roof", fid)

def pagoda(prefix, x, y, tiers, base, height, fid=""):
    fbox(prefix + "_Core", (x, y, height / 2), (base * 0.55, base * 0.55, height), "white", fid)
    for i in range(tiers):
        t = i / max(tiers - 1, 1)
        s = base * (1 - 0.32 * t)
        z = height * (0.18 + 0.78 * t)
        fbox(prefix + "_Tier%d" % i, (x, y, z), (s, s, 0.55), "roof", fid)
    fbox(prefix + "_Finial", (x, y, height + 2.2), (0.5, 0.5, 4.4), "gold", fid)

def well(prefix, x, y, fid=""):
    fcyl(prefix + "_Well", (x, y, 0.4), (0.8, 0.8, 0.8), "stone", fid)
    for tag, ox in (("L", -0.9), ("R", 0.9)):
        fbox(prefix + "_WellPost" + tag, (x + ox, y, 1.1), (0.18, 0.18, 2.2), "wood", fid)
    froof_gable(prefix + "_WellRoof", x, y, 2.6, 2.2, 2.2, 0.7, "sand", fid)
    fbox(prefix + "_Bucket", (x, y, 1.5), (0.48, 0.48, 0.36), "wood2", fid)
    fbox(prefix + "_Rope", (x, y, 1.95), (0.05, 0.05, 0.55), "wood", fid)

# ---------------------------------------------------------------- 道路と地面
fbox("CITY_Ground", (0, -1100, -0.06), (4700, 6000, 0.08), "ground2", "CITY")
fbox("CITY_SuzakuRoad", (0, -1925, 0.03), (84, 3850, 0.04), "road2", "CITY")
for sgn in (-1, 1):
    fbox("CITY_SuzakuDitch", (sgn * 46, -1925, 0.02), (1.6, 3850, 0.03), "water", "CITY")
for b in range(1, 8):
    for sgn in (-1, 1):
        fbox("CITY_DitchBridge", (sgn * 46, -550 * b, 0.12), (3.2, 5.0, 0.18), "wood2", "CITY")
for sgn in (-1, 1):
    for k in range(26):
        fbox("CITY_DitchPlank", (sgn * 46, -420 - 133 * k, 0.09), (3.4, 2.2, 0.12), "wood2", "CITY")
for b in range(1, 8):
    fbox("CITY_AveEW%d" % b, (0, -550 * b, 0.025), (4340, 24, 0.04), "road2", "CITY")
for sx in (574, 1106, 1638, 2170):
    for side in (-1, 1):
        if sx == 574:
            fbox("CITY_AveNS", (side * sx, -1925, 0.02), (20, 3850, 0.04), "road2", "CITY")
        else:
            fbox("CITY_AveNS", (side * sx, -1228, 0.02), (20, 5244, 0.04), "road2", "CITY")
for side in (-1, 1):
    fbox("CITY_Rajo", (side * (42 + 2128 / 2), -3872, 0.6), (2128, 3, 1.2), "ground2", "CITY")
for i in range(15):
    y = -150 - i * 260
    for side in (-1, 1):
        ftree("CITY_Tree", side * 50, y, 0.95, "CITY")
# 二条・五条の大路の南側に並木（北側は町と接するため南側の空き帯に置く）
for b in (1, 4):
    y0 = -550 * b
    for xi in range(-2080, 2081, 133):
        if abs(xi) < 75:
            continue
        ftree("CITY_AveTree", xi, y0 - 17, 0.9, "CITY")

def oxcart(prefix, x, y, dirn=1, fid="CITY"):
    """牛車（御所車風の模式）。dirn=1で北向き（牛が+y側）。"""
    fbox(prefix + "_Bed", (x, y, 0.98), (2.0, 3.0, 0.22), "wood", fid)
    fbox(prefix + "_Cabin", (x, y - dirn * 0.2, 1.85), (1.8, 2.5, 1.55), "wood2", fid)
    fbox(prefix + "_Curtain", (x, y + dirn * 1.06, 1.8), (1.6, 0.08, 1.2), "vermilion", fid)
    froof_gable(prefix + "_Roof", x, y - dirn * 0.2, 2.6, 3.2, 2.62, 0.55, "roof", fid)
    for sgn in (-1, 1):
        wob = fcyl(prefix + "_Wheel", (x + sgn * 1.08, y, 1.05), (1.05, 1.05, 0.16), "wood", fid)
        wob.rotation_euler.y = math.pi / 2
        fbox(prefix + "_Shaft", (x + sgn * 0.6, y + dirn * 2.2, 0.95), (0.09, 1.6, 0.09), "wood", fid)
    oy = y + dirn * 3.6
    fbox(prefix + "_OxBody", (x, oy, 1.05), (0.9, 2.0, 1.0), "trunk", fid)
    for lx in (-0.3, 0.3):
        for ly in (-0.75, 0.75):
            fbox(prefix + "_OxLeg", (x + lx, oy + ly, 0.3), (0.16, 0.16, 0.6), "trunk", fid)
    fbox(prefix + "_OxHead", (x, oy + dirn * 1.25, 0.8), (0.55, 0.7, 0.6), "trunk", fid)
    for sgn in (-1, 1):
        fbox(prefix + "_OxHorn", (x + sgn * 0.4, oy + dirn * 1.15, 1.2), (0.3, 0.08, 0.08), "sand", fid)

oxcart("CITY_Cart1", 16, -1500, 1)
oxcart("CITY_Cart2", -18, -2650, -1)
oxcart("CITY_Cart3", 14, -3400, 1)
oxcart("CITY_Cart4", 760, -2085, 1)

def loadcart(prefix, x, y, dirn=1, fid="CITY"):
    """荷車（模式）：台に荷を積み、梶棒を前に出す。"""
    fbox(prefix + "_Bed", (x, y, 1.0), (1.9, 2.8, 0.18), "wood", fid)
    for sgn in (-1, 1):
        wob = fcyl(prefix + "_Wheel", (x + sgn * 1.02, y, 0.95), (0.95, 0.95, 0.14), "wood", fid)
        wob.rotation_euler.y = math.pi / 2
        fbox(prefix + "_Shaft", (x + sgn * 0.55, y + dirn * 2.0, 0.75), (0.08, 1.8, 0.08), "wood", fid)
    fbox(prefix + "_Goods1", (x - 0.3, y - 0.5, 1.45), (1.2, 1.1, 0.7), "wood2", fid)
    fbox(prefix + "_Goods2", (x + 0.25, y + 0.6, 1.4), (1.0, 0.9, 0.6), "white", fid)
    fbox(prefix + "_Goods3", (x - 0.3, y - 0.5, 2.05), (0.9, 0.8, 0.5), "vermilion", fid)

loadcart("CITY_Load1", 700, -2193, 1)
loadcart("CITY_Load2", -700, -2193, 1)
loadcart("CITY_Load3", -13, -2080, -1)

def lantern(prefix, x, y, fid=""):
    """石灯籠（模式）。"""
    fbox(prefix + "_Base", (x, y, 0.15), (0.9, 0.9, 0.3), "stone", fid)
    fcyl(prefix + "_Shaft", (x, y, 0.65), (0.16, 0.16, 0.7), "stone", fid)
    fbox(prefix + "_Firebox", (x, y, 1.2), (0.62, 0.62, 0.45), "stone", fid)
    fbox(prefix + "_Roof", (x, y, 1.58), (0.95, 0.95, 0.3), "stone", fid)
    fcyl(prefix + "_Jewel", (x, y, 1.85), (0.14, 0.14, 0.28), "stone", fid)

def belfry(prefix, x, y, fid=""):
    """鐘楼（模式）：4本柱に屋根、釣鐘を吊る。"""
    for sx in (-1.3, 1.3):
        for sy in (-1.3, 1.3):
            fbox(prefix + "_Post", (x + sx, y + sy, 1.5), (0.22, 0.22, 3.0), "wood", fid)
    froof(prefix + "_Roof", x, y, 3.6, 3.4, 3.0, 1.1, "roof", fid)
    fcyl(prefix + "_Bell", (x, y, 2.2), (0.55, 0.55, 1.1), "wood", fid)

# ---------------------------------------------------------------- ランドマーク
mod.make_gate("LM_RAJOMON", 0, -3850, 36, 17, col, "LM_RAJOMON", upper=True, passage=True)
for side, tag in ((1, "TOJI"), (-1, "SAIJI")):
    x = side * 480
    fwall("LM_" + tag, x, -3760, 150, 150, "LM_" + tag)
    pagoda("LM_" + tag + "_Pagoda", x, -3735, 5, 13, 30, "LM_" + tag)
    hall_fast("LM_" + tag + "_Hall", x, -3805, 27, 15, fid="LM_" + tag)
    belfry("LM_" + tag + "_Belfry", x - 40, -3745, "LM_" + tag)
for side, tag in ((1, "EAST_MKT"), (-1, "WEST_MKT")):
    x = side * 840
    fbox("LM_" + tag + "_Plaza", (x, -1934, 0.03), (250, 250, 0.05), "ground2", "LM_" + tag)
    for r in range(4):
        for c in range(5):
            sx_ = x - 88 + c * 44
            sy_ = -1934 - 66 + r * 44
            p = "LM_%s_Stall%d_%d" % (tag, r, c)
            fbox(p + "_Counter", (sx_, sy_, 0.5), (5, 3, 1.0), "wood", p)
            fbox(p + "_Roof", (sx_, sy_, 2.7), (6.5, 4.5, 0.25), "sand" if (r + c) % 3 else "roof", p)
            for pi, (ox, oy) in enumerate(((-2.6, -1.7), (2.6, -1.7), (-2.6, 1.7), (2.6, 1.7))):
                fbox("%s_Post%d" % (p, pi), (sx_ + ox, sy_ + oy, 1.35), (0.14, 0.14, 2.7), "wood", p)
            # 屋台の柱（2026-11-20追加）：v12の確認画像で屋根だけが浮いて
            # 見えたため、屋根を支える柱4本を足した。柱なしでは再生成時に
            # 同じ欠陥が戻る。
            for _i, (_ox, _oy) in enumerate(((-2.6, -1.7), (2.6, -1.7), (-2.6, 1.7), (2.6, 1.7))):
                fbox(p + "_Post%d" % _i, (sx_ + _ox, sy_ + _oy, 1.35), (0.14, 0.14, 2.7), "wood", p)
            fbox(p + "_Noren", (sx_, sy_ - 2.3, 1.9), (4.6, 0.08, 0.9), "vermilion" if (r + c) % 2 else "white", p)
            if (r * 5 + c) % 4 == 0:
                fbox(p + "_Goods", (sx_, sy_, 1.25), (2.2, 1.4, 0.5), "vermilion", p)
            if (r * 5 + c) % 3 == 0:
                fcyl(p + "_Barrel", (sx_ + 3.9, sy_ + 1.5, 0.4), (0.38, 0.38, 0.8), "trunk", p)
                fbox(p + "_Crate", (sx_ - 3.9, sy_ - 1.2, 0.35), (0.85, 0.85, 0.7), "wood2", p)
fbox("LM_SHINSENEN_Pond", (800, -270, 0.02), (300, 400, 0.05), "water", "LM_SHINSENEN")
hall_fast("LM_SHINSENEN_Hall", 800, -95, 23, 11, irimoya=True, fid="LM_SHINSENEN")
lantern("LM_SHINSENEN_Lantern1", 655, -90, "LM_SHINSENEN")
lantern("LM_SHINSENEN_Lantern2", 945, -450, "LM_SHINSENEN")
for i, (px, py) in enumerate(((665, -120), (935, -120), (665, -430), (935, -430))):
    ftree("LM_SHINSENEN_Tree%d" % i, px, py, 1.15, "LM_SHINSENEN")

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

# ---------------------------------------------------------------- 町の配分（塊化つき）
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

# 町の座標表を作る。key=(side, k, row) rowは ('S', band, r) か ('N', r)
plots = {}
for side in (-1, 1):
    for k in range(16):
        cx = side * (42 + k * PITCH + PITCH / 2)
        x0, x1 = cx - PLOT / 2, cx + PLOT / 2
        for band in range(7):
            for r in range(4):
                cy = -(band * 550 + 18 + r * PITCH + PITCH / 2)
                if intersects(x0, x1, cy - PLOT / 2, cy + PLOT / 2):
                    continue
                plots[(side, k, ("S", band, r))] = (cx, cy, band)
        for r in range(10):
            cy = r * PITCH + PITCH / 2
            if intersects(x0, x1, cy - PLOT / 2, cy + PLOT / 2):
                continue
            plots[(side, k, ("N", r))] = (cx, cy, -1)

def neighbors(key):
    side, k, row = key
    out = []
    for dk in (-1, 1):
        if (side, k + dk, row) in plots:
            out.append((side, k + dk, row))
    if row[0] == "S":
        _, band, r = row
        cands = []
        if r > 0:
            cands.append(("S", band, r - 1))
        if r < 3:
            cands.append(("S", band, r + 1))
        if r == 0 and band > 0:
            cands.append(("S", band - 1, 3))
        if r == 3 and band < 6:
            cands.append(("S", band + 1, 0))
        if r == 0 and band == 0:
            cands.append(("N", 0))
        for c in cands:
            if (side, k, c) in plots:
                out.append((side, k, c))
    else:
        r = row[1]
        if r > 0 and (side, k, ("N", r - 1)) in plots:
            out.append((side, k, ("N", r - 1)))
        if r < 9 and (side, k, ("N", r + 1)) in plots:
            out.append((side, k, ("N", r + 1)))
        if r == 0 and (side, k, ("S", 0, 0)) in plots:
            out.append((side, k, ("S", 0, 0)))
    return out

types = {}
for key, (cx, cy, band) in plots.items():
    types[key] = pick(weights(key[0], band))

# 平滑化（近傍の多数派へ寄せて街区を塊にする）を2回
for sweep in range(2):
    keys = list(types.keys())
    rng.shuffle(keys)
    for key in keys:
        ns = [types[n] for n in neighbors(key)]
        if not ns:
            continue
        cur = types[key]
        built = sum(1 for t in ns if t != 4)
        if cur == 4 and built < 2:
            continue  # 農地帯の内側は農地のまま
        majority = max(set(ns), key=ns.count)
        if majority != cur and ns.count(majority) >= 2:
            p_adopt = 0.55 if key[0] > 0 else 0.40
            if rng.random() < p_adopt:
                types[key] = majority

# ---------------------------------------------------------------- 町の生成
def build_plot(cx, cy, kind, tag):
    p = "CTY_" + tag
    if kind == 0:      # 貴族邸
        fwall(p, cx, cy, PLOT, PLOT, p)
        hall_fast(p + "_Main", cx, cy + 24, 29, 14, irimoya=True, fid=p)
        house(p + "_Side", cx - 34, cy - 16, 18, 11, "roof", "white", fid=p)
        if rng.random() < 0.6:
            fbox(p + "_Store", (cx + 38, cy + 34, 1.5), (9, 7, 3.0), "white", p)
            froof(p + "_StoreRoof", cx + 38, cy + 34, 10.5, 8.5, 3.0, 1.6, "roof", p)
        fcyl(p + "_Pond", (cx + 30, cy - 24, 0.05), (11, 11, 0.12), "water", p)
        lantern(p + "_Lantern", cx + 18, cy - 24, p)
        fbox(p + "_PavilionDeck", (cx + 30, cy - 41, 0.18), (6.5, 5.5, 0.36), "wood", p)
        for px in (-2.6, 2.6):
            for py in (-2.1, 2.1):
                fbox(p + "_PavilionPost", (cx + 30 + px, cy - 41 + py, 1.3), (0.18, 0.18, 1.9), "wood", p)
        froof(p + "_PavilionRoof", cx + 30, cy - 41, 7.6, 6.6, 2.25, 1.0, "roof", p)
        ftree(p + "_Tree", cx - 28, cy + 32, 1.05, p)
        ftree(p + "_Tree2", cx + 44, cy - 40, 0.8, p)
    elif kind == 1:    # 官人宅（表に塀と門、家は通り沿い）
        ffence(p, cx, cy, PLOT, p)
        house(p + "_H1", cx - 28, cy - 26, 22, 13, "roof", fid=p, gable=rng.random() < 0.4)
        house(p + "_H2", cx + 28, cy - 26, 22, 13, "roof", fid=p, gable=rng.random() < 0.4)
        house(p + "_H3", cx - 28, cy + 28, 19, 12, "roof", "wood2", fid=p)
        fbox(p + "_StableWall", (cx + 40, cy + 40, 1.1), (10, 5, 2.2), "wood", p)
        froof_gable(p + "_StableRoof", cx + 40, cy + 40, 11.8, 6.8, 2.2, 1.6, "sand", p)
        fbox(p + "_StableDoor", (cx + 40, cy + 37.4, 0.95), (1.6, 0.1, 1.9), "wood2", p)
        if rng.random() < 0.5:
            ftree(p + "_Tree", cx + 32, cy + 30, 0.85, p)
    elif kind == 2:    # 庶民町
        if rng.random() < 0.5:
            fbox(p + "_Hedge", (cx, cy - 59.3, 0.5), (PLOT - 10, 1.2, 1.0), "pine", p)
        elif rng2.random() < 0.6:
            for tag, fx in (("1", cx - 30.5), ("2", cx + 30.5)):
                fbox(p + "_FrontFence" + tag, (fx, cy - 59.5, 0.5), (58, 0.18, 1.0), "wood", p)
        pattern = rng.random()
        n = 0
        if pattern < 0.35:
            # 長屋：南辺に長い一棟＋北辺に小家
            fbox(p + "_NagayaWall", (cx, cy - 46, 1.3), (86, 7.5, 2.6), "wood2", p)
            froof_gable(p + "_NagayaRoof", cx, cy - 46, 89, 9.3, 2.6, 2.2, "sand", p)
            fbox(p + "_NagayaStep", (cx, cy - 50.6, 0.09), (86, 1.0, 0.18), "wood", p)
            for i in range(7):
                fbox("%s_Door%d" % (p, i), (cx - 36 + i * 12, cy - 49.85, 0.95), (1.05, 0.1, 1.9), "wood", p)
                if i < 6:
                    fbox("%s_Win%d" % (p, i), (cx - 30 + i * 12, cy - 49.85, 1.6), (1.4, 0.1, 0.85), "roof", p)
            for ox in (-30, 0, 30):
                if rng.random() < 0.8:
                    house("%s_S%d" % (p, n), cx + ox, cy + 46, 14, 9, "sand", fid=p, gable=True); n += 1
        else:
            for ox in (-45, -27, -9, 9, 27, 45):
                if rng.random() < 0.9:
                    house("%s_S%d" % (p, n), cx + ox, cy - 48, 13.5, 8.5, "sand", fid=p, gable=rng.random() < 0.7); n += 1
                if rng.random() < 0.8:
                    house("%s_S%d" % (p, n), cx + ox, cy + 48, 13.5, 8.5, "sand", fid=p, gable=rng.random() < 0.7); n += 1
            for oy in (-24, 0, 24):
                if rng.random() < 0.5:
                    house("%s_S%d" % (p, n), cx - 48, cy + oy, 8.5, 13.5, "sand", fid=p, gable=True); n += 1
                if rng.random() < 0.5:
                    house("%s_S%d" % (p, n), cx + 48, cy + oy, 8.5, 13.5, "sand", fid=p, gable=True); n += 1
        if rng.random() < 0.45:
            well(p + "_Well", cx + rng.uniform(-15, 15), cy + rng.uniform(-12, 12), p)
        if rng.random() < 0.3:
            sx_ = cx + rng.uniform(-35, 35)
            sy_ = cy + rng.uniform(-35, 35)
            fbox(p + "_Shed", (sx_, sy_, 1.0), (6, 4.5, 2.0), "wood", p)
            fbox(p + "_ShedRoof", (sx_, sy_, 2.2), (7.2, 5.6, 0.25), "sand", p)
    elif kind == 3:    # 寺
        fwall(p, cx, cy, PLOT, PLOT, p)
        hall_fast(p + "_Main", cx - 12, cy + 18, 21, 12, irimoya=True, fid=p)
        pagoda(p + "_Pagoda", cx + 30, cy - 18, 3, 9, 17, p)
        belfry(p + "_Belfry", cx + 32, cy + 30, p)
        for tag2, ox in (("L", -3), ("R", 3)):
            fbox(p + "_GatePost" + tag2, (cx + ox, cy - PLOT / 2 + 1.2, 1.5), (0.4, 0.4, 3.0), "vermilion", p)
        froof(p + "_GateRoof", cx, cy - PLOT / 2 + 1.2, 9, 3.4, 3.0, 1.2, "roof", p)
        ftree(p + "_Tree", cx - 38, cy - 30, 1.0, p)
    else:              # 畑・空地
        mat = "field" if (int(cx + cy) // 7) % 2 == 0 else "field2"
        fbox(p + "_Field", (cx, cy, 0.02), (PLOT, PLOT, 0.05), mat, p)
        for i in range(6):
            fbox("%s_Ridge%d" % (p, i), (cx - 50 + i * 20, cy, 0.09), (7, PLOT - 14, 0.1), "earth", p)
        if rng.random() < 0.4:
            house(p + "_Farm", cx + rng.uniform(-20, 20), cy - 42, 12, 8, "sand", fid=p, gable=True)
        if rng.random() < 0.2:
            ftree(p + "_Tree", cx - 40, cy + 40, 0.9, p)

count = {}
for key, (cx, cy, band) in plots.items():
    side, k, row = key
    tag = "%s%d_%s" % ("E" if side > 0 else "W", k,
                       ("B%d_%d" % (row[1], row[2])) if row[0] == "S" else ("N%d" % row[1]))
    kind = types[key]
    build_plot(cx, cy, kind, tag)
    count[kind] = count.get(kind, 0) + 1

for obj in col.objects:
    obj["evidence"] = "procedural_city"
print("CITY_DONE plots=%d kinds=%s objects=%d" % (len(plots), count, len(col.objects)), flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v15.blend")
print("SAVED_V15", flush=True)

scene = bpy.context.scene

def setup_cam(loc, target, ortho=None, lens=35):
    cam_data = bpy.data.cameras.new("V15Cam")
    cam_data.clip_start = 0.5
    cam_data.clip_end = 9000.0
    if ortho:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho
    else:
        cam_data.lens = lens
    cam = bpy.data.objects.new("V15Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

def render(path, rx, ry, samples):
    scene.cycles.samples = samples
    scene.render.resolution_x, scene.render.resolution_y = rx, ry
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v15"
setup_cam((0, -1225, 3200), (0, -1225, 0), ortho=5600)
render(OUT + "_top.png", 1250, 1500, 16)
print("TOP_DONE", flush=True)
setup_cam((2700, -4300, 1500), (0, -900, 0), lens=35)
render(OUT + "_hero.png", 1280, 720, 32)
print("HERO_DONE", flush=True)
setup_cam((0, -3650, 4), (0, 200, 30), lens=30)
render(OUT + "_suzaku.png", 1280, 720, 32)
print("SUZAKU_DONE", flush=True)
setup_cam((250, -545, 2.4), (650, -556, 1.8), lens=32)
render(OUT + "_avenue.png", 1280, 720, 48)
print("AVENUE_DONE", flush=True)
setup_cam((82.6, -679.5, 1.75), (79.1, -666.5, 1.15), lens=34)
render(OUT + "_close.png", 1280, 720, 48)
print("CLOSE_DONE", flush=True)
setup_cam((113.5, -830.0, 1.75), (105.5, -816.8, 1.05), lens=30)
render(OUT + "_nagaya.png", 1280, 720, 48)
print("NAGAYA_DONE", flush=True)
setup_cam((803, -1967, 1.8), (796, -1957, 1.5), lens=32)
render(OUT + "_market.png", 1280, 720, 48)
print("MARKET_DONE", flush=True)
setup_cam((25.5, -1513, 2.1), (15.5, -1496.5, 1.3), lens=32)
render(OUT + "_cart.png", 1280, 720, 48)
print("CART_DONE", flush=True)
