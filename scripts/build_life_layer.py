# -*- coding: utf-8 -*-
"""第2弾：植生の作り分け（E5）・生活の気配（E6）・地面の質感（E4、傾きを除く）

使い方：
    blender --background heian_daidairi_detail_v21.blend \
        --python build_life_layer.py -- [保存する.blend] [--no-render]

環境レイヤー（v21、build_environment.py）を含むモデルを開いて実行し、
heian_daidairi_detail_v22.blend として保存して確認画像を描く。
既存のコレクション（大内裏・推定・内部・市街・外観精密化・環境）には触れない。
再実行すると、このスクリプトのコレクションの中身だけを入れ替える。
提案は docs/proposal/01_non-building-enrichment.md、記録は 13_life-layer.md。

コレクションと属性：
- COL_92_Vegetation：樹種を明示した植栽。evidence=vegetation_sourced（史料に樹種の
  記述があるもの、確度B）。朱雀大路の柳、紫宸殿南庭の左近の梅・右近の橘。
  あわせて市街レイヤーの汎用樹・生垣と宴の松原の松を、手続き生成の樹（scripts/heian_trees.py の
  松・落葉広葉樹・生垣）に置き換える（evidence=procedural_vegetation、確度D）。元のオブジェクトは
  消さずに非表示にし、heian_replaced_by の属性を付ける。
- COL_93_Life：生活の気配と地面の痕跡。evidence=procedural_life（一般的な生活像からの
  模式、確度D）。炊煙、干し物、夜の灯り（石灯籠・門の篝火・家の窓）、筏と小舟、
  大路の轍と水たまり。
夜の灯り（光源と発光面）は属性 heian_night=1 を持ち、heian_time.apply_time("night") の
ときだけ描かれる。保存時は昼（灯りは非表示）。
"""
import bpy
import os
import sys as _sys
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_SCRIPT_DIR)
_sys.path.insert(0, _SCRIPT_DIR)
from heian_gpu import use_gpu  # noqa: E402  GPU があれば使う（HEIAN_DEVICE=CPU で無効）
from heian_time import apply_time  # noqa: E402  時刻のプリセット（環境レイヤーが前提）
# 生成物（.blend・画像）の置き場所。環境変数 HEIAN_WORK で変更できる（既定: <リポジトリ>/output）
WORK = os.environ.get("HEIAN_WORK", os.path.join(_REPO, "output"))
os.makedirs(WORK, exist_ok=True)
import csv
import math
import random
import re
import time
import zlib

import bmesh
from mathutils import Vector

T0 = time.time()


def log(*a):
    print(*a, "t=%.0fs" % (time.time() - T0), flush=True)


argv = _sys.argv[_sys.argv.index("--") + 1:] if "--" in _sys.argv else []
OUT_BLEND = os.path.abspath(argv[0]) if argv and not argv[0].startswith("--") else \
    os.path.join(WORK, "heian_daidairi_detail_v22.blend")
DO_RENDER = "--no-render" not in argv
OUT = os.path.join(WORK, "view_v22")

if "COL_91_Environment" not in bpy.data.collections:
    raise RuntimeError("環境レイヤー（COL_91_Environment）がない。先に build_environment.py を適用する")


# ---------------------------------------------------------------- コレクションと共通
def fresh_collection(name, layer):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    for ob in list(c.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    c["layer"] = layer
    return c


COL_VEG = fresh_collection("COL_92_Vegetation", "vegetation_sourced")
COL_LIFE = fresh_collection("COL_93_Life", "procedural_life")
ENV_NAMES = {o.name for o in bpy.data.collections["COL_91_Environment"].objects}


def mat(name, color, rough=0.9, color2=None, scale=1.0, emit=None, emit_e=0.0):
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    if color2 is not None:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = scale
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        ins = [s for s in mx.inputs if s.type == "RGBA"]
        ins[0].default_value = (*color, 1)
        ins[1].default_value = (*color2, 1)
        nt.links.new(nz.outputs["Fac"], mx.inputs[0])
        nt.links.new([s for s in mx.outputs if s.type == "RGBA"][0], b.inputs["Base Color"])
    if emit is not None:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = emit_e
    return m


M = {
    "trunk": bpy.data.materials.get("MAT_TrunkBrown") or mat("MAT_TrunkBrown", (0.25, 0.17, 0.10)),
    "wood": bpy.data.materials["MAT_WoodDark"],
    "wood2": bpy.data.materials.get("MAT_WoodLight") or mat("MAT_WoodLight", (0.52, 0.42, 0.30)),
    "water": bpy.data.materials["MAT_EnvWater"],
    "iron": mat("MAT_LifeIron", (0.06, 0.055, 0.05), 0.6),
    "rut": mat("MAT_LifeRut", (0.29, 0.26, 0.21), 1.0, (0.23, 0.20, 0.16), 0.4),
    "cloth_w": mat("MAT_LifeClothWhite", (0.86, 0.84, 0.78), 0.9),
    "cloth_b": mat("MAT_LifeClothIndigo", (0.08, 0.12, 0.28), 0.9),
    "cloth_t": mat("MAT_LifeClothTan", (0.55, 0.42, 0.26), 0.9),
    "flame": mat("MAT_LifeFlame", (1.0, 0.5, 0.15), 1.0, emit=(1.0, 0.45, 0.10), emit_e=60.0),
    "glow": mat("MAT_LifeWindowGlow", (0.9, 0.6, 0.3), 1.0, emit=(1.0, 0.62, 0.30), emit_e=4.0),
    "lampglow": mat("MAT_LifeLanternGlow", (0.9, 0.6, 0.3), 1.0, emit=(1.0, 0.58, 0.25), emit_e=12.0),
}


def tag(ob, evidence, certainty, fid, night=False):
    ob["evidence"] = evidence
    ob["certainty"] = certainty
    ob["facility_id"] = fid
    if night:
        ob["heian_night"] = 1
        ob.hide_render = True
    return ob


_shared = {}


def shared_mesh(kind, m):
    key = (kind, m.name)
    if key in _shared:
        return _shared[key]
    me = bpy.data.meshes.new("Life_%s_%s" % (kind, m.name))
    bm = bmesh.new()
    if kind == "cube":
        bmesh.ops.create_cube(bm, size=1.0)
    elif kind == "sphere":
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.5)
    elif kind == "cyl":
        bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.5, radius2=0.5, depth=1.0)
    elif kind == "cone":
        bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.5, radius2=0.0, depth=1.0)
    elif kind == "smoke":     # 炊煙：下が細く上が太い筒（z=0〜1）
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.15, radius2=1.0, depth=1.0)
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 0.5))
    bm.to_mesh(me)
    bm.free()
    if kind in ("sphere", "cyl", "cone"):
        me.shade_smooth()
    me.materials.append(m)
    _shared[key] = me
    return me


def prim(kind, name, loc, dims, m, col, evidence, cert, fid, rot=(0, 0, 0), night=False):
    ob = bpy.data.objects.new(name, shared_mesh(kind, m))
    ob.location = loc
    ob.scale = dims
    ob.rotation_euler = rot
    col.objects.link(ob)
    return tag(ob, evidence, cert, fid, night)


def point_light(name, loc, energy, color, radius, col, fid, night=True):
    ld = bpy.data.lights.new(name, "POINT")
    ld.energy = energy
    ld.color = color
    ld.shadow_soft_size = radius
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    col.objects.link(ob)
    return tag(ob, "procedural_life", "D", fid, night)


# 地面の高さ：上から光線を当て、環境レイヤー（霞の箱・地形）と自分の作ったものを除いた最初の上向き面
DEPS = bpy.context.evaluated_depsgraph_get()


def ground_z(x, y, top=60.0):
    origin = Vector((x, y, top))
    for _ in range(12):
        hit, loc, nrm, _i, ob, _m = bpy.context.scene.ray_cast(DEPS, origin, Vector((0, 0, -1)))
        if not hit:
            return 0.0
        if ob.name in ENV_NAMES or nrm.z < 0.6:
            origin = loc - Vector((0, 0, 0.01))
            continue
        return loc.z
    return 0.0


# ================================================================ E5 植生
# 樹は scripts/heian_trees.py で枝分かれと1枚ずつの葉から組んだ原型を作り、
# その原型コレクションのインスタンスとして置く（原型の数だけメッシュを持つ）。
import heian_trees as TREES  # noqa: E402

# --- 既存の汎用樹・生垣を隠して置き換える（市街レイヤー・宴の松原）
# 他のレイヤーのオブジェクトは消さず、hide_render/hide_viewport を立てて印を付けるだけにする
# （市街レイヤーを再生成すると元に戻るので、生成の連鎖では必ずこのスクリプトを後に流す）。
REPLACE_COLS = ["COL_70_City", "COL_05_Offices"]
OLD_LEAF = {"MAT_PineGreen": "pine", "MAT_CityLeaf2": "broadleaf"}
old_trunks, old_canopy, old_hedges = [], [], []
for cn in REPLACE_COLS:
    c = bpy.data.collections.get(cn)
    if c is None:
        continue
    for o in c.all_objects:
        if o.type != "MESH" or not o.material_slots or o.material_slots[0].material is None:
            continue
        mn = o.material_slots[0].material.name
        if re.search(r"_Trunk(\.\d+)?$", o.name) and mn == "MAT_TrunkBrown":
            old_trunks.append(o)
        elif re.search(r"_(Canopy\d?|Crown)(\.\d+)?$", o.name) and mn in OLD_LEAF:
            old_canopy.append(o)
        elif re.search(r"_Hedge(\.\d+)?$", o.name) and mn in OLD_LEAF:
            old_hedges.append(o)
grid = {}
for o in old_canopy:
    grid.setdefault((int(o.location.x // 8), int(o.location.y // 8)), []).append(o)


def near_canopies(x, y, r=4.5):
    out = []
    gx, gy = int(x // 8), int(y // 8)
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            for o in grid.get((gx + i, gy + j), []):
                if (o.location.x - x) ** 2 + (o.location.y - y) ** 2 < r * r:
                    out.append(o)
    return out


def retire(o):
    o.hide_render = True
    o.hide_viewport = True
    o["heian_replaced_by"] = "COL_92_Vegetation"


tree_sites = []          # (種類, x, y, 縮尺, facility_id, 元の名前)
for t in old_trunks:
    x, y = t.location.x, t.location.y
    cans = near_canopies(x, y)
    for o in cans:
        retire(o)
    retire(t)
    if t.name.startswith("CITY_Tree_"):
        continue         # 朱雀大路の汎用樹（x=±50）は柳の並木に置き換える（下）
    kinds = [OLD_LEAF[o.material_slots[0].material.name] for o in cans]
    kind = "pine" if t.name.startswith("EN_Pine") else \
        (max(set(kinds), key=kinds.count) if kinds else "broadleaf")
    if t.name.startswith("EN_Pine"):
        s0 = t.dimensions.z / 2.2
    else:
        s0 = t.dimensions.z / 2.6
    tree_sites.append((kind, x, y, s0, t.get("facility_id", ""), t.name))
for o in old_hedges:
    retire(o)
bpy.context.view_layer.update()
DEPS = bpy.context.evaluated_depsgraph_get()
log("OLD_TREES_RETIRED trunks=%d canopies=%d hedges=%d" % (len(old_trunks), len(old_canopy), len(old_hedges)))


PENDING = []


def tree(kind, variant, name, x, y, s, fid, evidence, cert, top=12.0):
    """地面の高さだけ先に求めて控えておき、置くのは flush_trees() でまとめて行う
    （置くたびに光線判定の depsgraph が作り直されて遅くなるのを避ける）。"""
    PENDING.append((kind, variant, name, x, y, ground_z(x, y, top), s, fid, evidence, cert))


def flush_trees():
    for kind, variant, name, x, y, z0, s, fid, evidence, cert in PENDING:
        r = random.Random(zlib.crc32(name.encode()))
        em = TREES.place(kind, variant, name, (x, y, z0 - 0.05), r.uniform(0, 2 * math.pi), s, COL_VEG)
        em["tree_kind"] = kind
        tag(em, evidence, cert, fid)
    PENDING.clear()


# --- 朱雀大路の柳：260m区画ごとに3本（約87m間隔）、路肩（x=±43.6）に
# 路面の端（x=±42）と側溝（x=±45.2）の間。町の築地塀は x=±49 付近にあるので、
# 元の汎用樹（x=±50）の位置ではなく路肩に植える
n_willow = 0
for i in range(15):
    for off in (0.0, 87.0, 173.0):
        y = -150.0 - i * 260.0 - off
        if y < -3830:
            continue
        for side in (-1, 1):
            nm = "VEG_SuzakuWillow_%d_%d_%d" % (i, int(off), side)
            v = zlib.crc32(nm.encode()) % 2
            s = 0.8 + (zlib.crc32((nm + "s").encode()) % 100) / 100 * 0.2
            tree("willow", v, nm, side * 43.6, y, s, "VEG_SUZAKU_WILLOW", "vegetation_sourced", "B")
            n_willow += 1
log("WILLOW_DONE", n_willow)

# --- 市街・神泉苑・宴の松原の樹：元の樹冠の材質で松か広葉樹かを決め、同じ場所に
n_city = {"pine": 0, "broadleaf": 0}
for kind, x, y, s0, fid, oname in tree_sites:
    nm = "VEG_" + oname.replace("_Trunk", "")
    v = zlib.crc32(nm.encode()) % (3 if kind == "pine" else 4)
    s = s0 * (0.95 if kind == "pine" else 0.85)
    tree(kind, v, nm, x, y, s, fid, "procedural_vegetation", "D")
    n_city[kind] += 1
log("CITY_TREES_DONE", n_city)

# --- 生垣：元の箱と同じ場所・長さに、10mの区画の原型を並べる
n_hedge = 0
for o in old_hedges:
    L = max(o.dimensions.x, o.dimensions.y)
    along_x = o.dimensions.x >= o.dimensions.y
    rz = o.rotation_euler.z + (0 if along_x else math.pi / 2)
    nseg = max(1, round(L / 10.0))
    seg = L / nseg
    ax = Vector((math.cos(rz), math.sin(rz), 0))
    for k in range(nseg):
        c = o.location + ax * (-L / 2 + seg * (k + 0.5))
        nm = "VEG_%s_%d" % (o.name, k)
        em = TREES.place("hedge", 0, nm, (c.x, c.y, o.location.z - o.dimensions.z / 2), rz, 1.0, COL_VEG)
        em.scale = (seg / 10.0, 1.0, 1.0)
        tag(em, "procedural_vegetation", "D", o.get("facility_id", ""))
        n_hedge += 1
log("HEDGES_DONE", n_hedge)

# --- 紫宸殿南庭：左近の梅（東）・右近の橘（西）。基準年（818年以降の9世紀前半）は左近が梅
# （桜に替わるのは承和年間（834〜848）頃とされる）。位置は南階の東西11mの模式
for tag_, x, kind in (("SAKON_UME", 291.0, "plum"), ("UKON_TACHIBANA", 269.0, "tachibana")):
    y = 712.0
    fid = "VEG_" + tag_
    tree(kind, 0, fid, x, y, 1.0, fid, "vegetation_sourced", "B", top=3.0)
    z0 = PENDING[-1][5]
    # 低い竹垣（籬）で囲む（模式）：細い柱16本と、柱をつなぐ上下2段の横竹
    R_F = 3.2
    for k in range(16):
        a = 2 * math.pi * k / 16
        prim("cyl", "%s_FencePost%d" % (fid, k), (x + R_F * math.cos(a), y + R_F * math.sin(a), z0 + 0.38),
             (0.06, 0.06, 0.76), M["wood2"], COL_VEG, "vegetation_sourced", "D", fid)
        am = a + math.pi / 16
        for hz in (0.28, 0.66):
            prim("cyl", "%s_FenceRail%d" % (fid, k), (x + R_F * 0.99 * math.cos(am), y + R_F * 0.99 * math.sin(am),
                                                       z0 + hz),
                 (0.035, 0.035, 2 * R_F * math.sin(math.pi / 16) + 0.06), M["wood2"], COL_VEG,
                 "vegetation_sourced", "D", fid, rot=(math.pi / 2, 0, am))
flush_trees()
log("SOUTH_GARDEN_DONE")

# ================================================================ E6 生活の気配
rng = random.Random(2026)
city = bpy.data.collections.get("COL_70_City")
city_obs = sorted(city.objects, key=lambda o: o.name) if city else []
house_walls = [o for o in city_obs if re.search(r"_S\d+_Wall$", o.name)]
log("COMMONER_HOUSES", len(house_walls))

# ---- 炊煙（体積の煙）
smoke_mat = bpy.data.materials.get("MAT_LifeSmoke")
if smoke_mat is None:
    smoke_mat = bpy.data.materials.new("MAT_LifeSmoke")
    smoke_mat.use_nodes = True
    nt = smoke_mat.node_tree
    nt.nodes.clear()
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (0.70, 0.70, 0.72, 1)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 3.0
    nz.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    shape = nt.nodes.new("ShaderNodeMapRange")       # ノイズで煙のちぎれ
    shape.inputs["From Min"].default_value = 0.42
    shape.inputs["From Max"].default_value = 0.7
    nt.links.new(nz.outputs["Fac"], shape.inputs["Value"])
    fade = nt.nodes.new("ShaderNodeMapRange")        # 上へ行くほど薄く
    fade.inputs["From Min"].default_value = 1.0
    fade.inputs["From Max"].default_value = 0.0
    nt.links.new(sep.outputs["Z"], fade.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nt.links.new(shape.outputs["Result"], mul.inputs[0])
    nt.links.new(fade.outputs["Result"], mul.inputs[1])
    dens = nt.nodes.new("ShaderNodeMath")
    dens.operation = "MULTIPLY"
    dens.inputs[1].default_value = 2.6
    nt.links.new(mul.outputs[0], dens.inputs[0])
    nt.links.new(dens.outputs[0], vol.inputs["Density"])
    nt.links.new(vol.outputs["Volume"], outn.inputs["Volume"])
n_smoke = 0
for w in house_walls:
    if rng.random() > 0.035:
        continue
    x, y = w.location.x, w.location.y
    h = rng.uniform(20, 34)
    ob = bpy.data.objects.new(w.name.replace("_Wall", "_Smoke"), shared_mesh("smoke", smoke_mat))
    ob.location = (x + rng.uniform(-1.5, 1.5), y, 4.2)
    ob.scale = (rng.uniform(3.5, 5.0), rng.uniform(3.5, 5.0), h)
    ob.rotation_euler = (0.0, math.radians(rng.uniform(10, 22)), 0.0)   # 西風で東へなびく
    ob.visible_shadow = False
    COL_LIFE.objects.link(ob)
    tag(ob, "procedural_life", "D", "LIFE_SMOKE")
    n_smoke += 1
log("SMOKE_DONE", n_smoke)

# ---- 干し物（家の北側に竿と布）
n_laundry = 0
LAUNDRY_SAMPLE = None
for w in house_walls:
    if rng.random() > 0.12:
        continue
    x, y = w.location.x, w.location.y
    hw, hd = w.scale.x / 2, w.scale.y / 2
    py = y + hd + 2.2
    span = min(5.5, hw * 1.4)
    p = w.name.replace("_Wall", "_Laundry")
    for sx in (-span / 2, span / 2):
        prim("cube", p + "_Post", (x + sx, py, 0.9), (0.1, 0.1, 1.8), M["wood"], COL_LIFE,
             "procedural_life", "D", "LIFE_LAUNDRY")
    prim("cube", p + "_Pole", (x, py, 1.78), (span + 0.4, 0.06, 0.06), M["wood2"], COL_LIFE,
         "procedural_life", "D", "LIFE_LAUNDRY")
    n_cl = rng.randint(2, 3)
    for k in range(n_cl):
        cx = x - span / 2 + span * (k + 0.5) / n_cl
        m_ = M[rng.choice(("cloth_w", "cloth_w", "cloth_b", "cloth_t"))]
        prim("cube", "%s_Cloth%d" % (p, k), (cx, py, 1.25), (span / n_cl * 0.8, 0.03, 1.0), m_, COL_LIFE,
             "procedural_life", "D", "LIFE_LAUNDRY")
    if LAUNDRY_SAMPLE is None and abs(x) < 1600 and -3000 < y < -1000:
        LAUNDRY_SAMPLE = (x, py)
    n_laundry += 1
log("LAUNDRY_DONE", n_laundry)

# ---- 夜の灯り：家の窓（発光面）、石灯籠（灯と光源）、門の篝火
n_glow = 0
for o in city_obs:
    if not o.name.endswith("_Window"):
        continue
    if rng.random() > 0.22:
        continue
    prim("cube", o.name + "_Glow", (o.location.x, o.location.y - 0.06, o.location.z),
         (o.scale.x * 0.9, 0.02, o.scale.z * 0.85), M["glow"], COL_LIFE, "procedural_life", "D",
         "LIFE_NIGHT", night=True)
    n_glow += 1
n_lantern = 0
for o in city_obs:
    if not o.name.endswith("_Firebox"):
        continue
    x, y, z = o.location
    prim("cube", o.name + "_Light", (x, y - o.scale.y / 2 - 0.01, z), (o.scale.x * 0.45, 0.02, o.scale.z * 0.55),
         M["lampglow"], COL_LIFE, "procedural_life", "D", "LIFE_NIGHT", night=True)
    point_light(o.name + "_Lamp", (x, y - o.scale.y / 2 - 0.25, z), 6.0, (1.0, 0.62, 0.32), 0.1,
                COL_LIFE, "LIFE_NIGHT")
    n_lantern += 1


def brazier(name, x, y, fid):
    z0 = ground_z(x, y, 6.0)
    for k in range(3):
        a = 2 * math.pi * k / 3
        prim("cyl", "%s_Leg%d" % (name, k), (x + 0.35 * math.cos(a), y + 0.35 * math.sin(a), z0 + 0.8),
             (0.07, 0.07, 1.7), M["iron"], COL_LIFE, "procedural_life", "D", fid,
             rot=(0.2 * math.sin(a), -0.2 * math.cos(a), 0))
    prim("cyl", name + "_Basket", (x, y, z0 + 1.75), (0.75, 0.75, 0.4), M["iron"], COL_LIFE,
         "procedural_life", "D", fid)
    prim("cone", name + "_Flame", (x, y, z0 + 2.35), (0.6, 0.6, 1.1), M["flame"], COL_LIFE,
         "procedural_life", "D", fid, night=True)
    point_light(name + "_Light", (x, y, z0 + 2.6), 450.0, (1.0, 0.55, 0.22), 0.4, COL_LIFE, fid)


GATES = {}
with open(os.path.join(_REPO, "data", "daidairi_layout_v3_1.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["type"] == "gate":
            GATES[r["facility_id"]] = (float(r["center_x_m"]), float(r["center_y_m"]),
                                       float(r["size_x_m"]), float(r["size_y_m"]))
n_brazier = 0
fire_gates = [g for g in GATES if g.startswith("GATE_")] + ["CHD_OTENMON"]
for g in fire_gates:
    gx, gy, sx, sy = GATES[g]
    if abs(gy) < 1 or abs(gy - 1394) < 1 or g == "CHD_OTENMON":   # 南辺・北辺の門
        out = -1 if (abs(gy) < 1 or g == "CHD_OTENMON") else 1
        pts = [(gx + s * (sx / 2 + 2.5), gy + out * (sy / 2 + 5.0)) for s in (-1, 1)]
    else:                                                         # 東辺・西辺の門
        out = 1 if gx > 0 else -1
        pts = [(gx + out * (sx / 2 + 5.0), gy + s * (sy / 2 + 2.5)) for s in (-1, 1)]
    for k, (bx, by) in enumerate(pts):
        brazier("LIFE_Brazier_%s_%d" % (g, k), bx, by, "LIFE_BRAZIER")
        n_brazier += 1
for k, s in enumerate((-1, 1)):                                    # 羅城門（京の南の正門）
    brazier("LIFE_Brazier_RAJOMON_%d" % k, s * 21.0, -3850.0 - 14.0, "LIFE_BRAZIER")
    n_brazier += 1
log("NIGHT_LIGHTS_DONE windows=%d lanterns=%d braziers=%d" % (n_glow, n_lantern, n_brazier))

# ---- 筏（堀川）と小舟（鴨川・桂川）
n_boat = 0
for k, (x, y) in enumerate(((840, 620), (840, -880), (840, -2650), (-840, 300), (-840, -1300), (-840, -3200))):
    for j in range(7):
        prim("cyl", "LIFE_Raft%d_Log%d" % (k, j), (x - 1.5 + j * 0.5, y, 0.14), (0.46, 0.46, 9.0), M["trunk"],
             COL_LIFE, "procedural_life", "D", "LIFE_RAFT", rot=(math.pi / 2, 0, 0))
    n_boat += 1
for rid, idxs in (("RIV_KAMO_Water", (40, 95, 150)), ("RIV_KATSURA_Water", (30, 70, 110))):
    ob = bpy.data.objects.get(rid)
    if ob is None:
        continue
    vs = ob.data.vertices
    npair = len(vs) // 2
    for i in idxs:
        if i + 1 >= npair:
            continue
        a = (vs[2 * i].co + vs[2 * i + 1].co) / 2
        b = (vs[2 * i + 2].co + vs[2 * i + 3].co) / 2
        ang = math.atan2(b.y - a.y, b.x - a.x) - math.pi / 2
        p = "LIFE_Boat_%s_%d" % (rid.split("_")[1], i)
        off = Vector((math.cos(ang), math.sin(ang), 0)) * 3.0
        c = a + off
        prim("cube", p + "_Hull", (c.x, c.y, -0.02), (1.5, 6.5, 0.55), M["wood"], COL_LIFE,
             "procedural_life", "D", "LIFE_BOAT", rot=(0, 0, ang))
        prim("cube", p + "_Cargo", (c.x, c.y, 0.45), (1.1, 2.6, 0.5), M["cloth_t"], COL_LIFE,
             "procedural_life", "D", "LIFE_BOAT", rot=(0, 0, ang))
        prim("cyl", p + "_Pole", (c.x + 0.4, c.y, 1.6), (0.07, 0.07, 3.6), M["wood2"], COL_LIFE,
             "procedural_life", "D", "LIFE_BOAT", rot=(0.35, 0, ang))
        n_boat += 1
log("BOATS_DONE", n_boat)

# ================================================================ E4 地面の質感（轍と水たまり）
n_rut = 0
for xs in (-16.9, -15.1, 15.1, 16.9):                 # 朱雀大路（南北）
    prim("cube", "LIFE_Rut_Suzaku_%d" % int(xs * 10), (xs, -1925.0, 0.053), (0.45, 3840.0, 0.006), M["rut"],
         COL_LIFE, "procedural_life", "D", "LIFE_RUT")
    n_rut += 1
for b in range(1, 8):                                  # 二条〜八条の東西大路
    y = -550.0 * b
    for ys in (-4.9, -3.1, 3.1, 4.9):
        for side in (-1, 1):
            prim("cube", "LIFE_Rut_EW%d_%d_%d" % (b, int(ys * 10), side), (side * 1106.0, y + ys, 0.048),
                 (2120.0, 0.45, 0.006), M["rut"], COL_LIFE, "procedural_life", "D", "LIFE_RUT")
            n_rut += 1
rp = random.Random(31)
n_puddle = 0
for k in range(60):
    if k < 20:
        x, y = rp.choice((-1, 1)) * rp.uniform(8, 30), rp.uniform(-3800, -60)
    else:
        b = rp.randint(1, 7)
        x, y = rp.choice((-1, 1)) * rp.uniform(60, 2100), -550.0 * b + rp.uniform(-8, 8)
    prim("sphere", "LIFE_Puddle%d" % k, (x, y, 0.05), (rp.uniform(2.5, 7.0), rp.uniform(1.5, 4.0), 0.02),
         M["water"], COL_LIFE, "procedural_life", "D", "LIFE_PUDDLE", rot=(0, 0, rp.uniform(0, math.pi)))
    n_puddle += 1
log("GROUND_MARKS_DONE ruts=%d puddles=%d" % (n_rut, n_puddle))

# ---------------------------------------------------------------- 保存
apply_time("day")
scene = bpy.context.scene
for c in bpy.data.cameras:
    c.clip_end = max(c.clip_end, 60000.0)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
log("SAVED", OUT_BLEND, "veg=%d life=%d" % (len(COL_VEG.objects), len(COL_LIFE.objects)))

# ---------------------------------------------------------------- 確認描画
if DO_RENDER:
    use_gpu(scene)
    cam_data = bpy.data.cameras.new("V22Cam")
    cam_data.clip_start = 0.1
    cam_data.clip_end = 80000
    cam = bpy.data.objects.new("V22Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    ONLY = [s for s in os.environ.get("HEIAN_SHOTS", "").split(",") if s]

    def shot(name, loc, target, lens=35, samples=48, tod="day"):
        if ONLY and name not in ONLY:
            return
        apply_time(tod)
        cam.location = loc
        cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        cam_data.lens = lens
        scene.render.resolution_x, scene.render.resolution_y = 1280, 720
        scene.cycles.samples = int(os.environ.get("HEIAN_SAMPLES", samples))
        scene.render.filepath = OUT + "_" + name + ".png"
        t = time.time()
        bpy.ops.render.render(write_still=True)
        log("RENDERED", name, "sec=%.0f" % (time.time() - t))

    shot("willow", (34, -1258, 1.8), (44, -1278, 4.2), lens=24)
    shot("suzaku", (-8, -1080, 2.2), (0, -1500, 4.0), lens=30)
    shot("garden", (55, -25, 12), (84, -58, 3), lens=28)
    shot("hedge", (88, -975, 3.0), (112, -950, 1.5), lens=28)
    shot("matsubara", (-300, 790, 9), (-340, 850, 4), lens=28)
    shot("nantei", (280, 724.5, 4.8), (280, 707, 1.2), lens=18)
    shot("sakon_ume", (284, 720, 2.0), (291, 712, 2.0), lens=28)
    shot("ukon_tachibana", (276, 720, 1.8), (269, 712, 1.7), lens=28)
    shot("smoke_evening", (700, -2350, 90), (1250, -3000, 5), lens=35, tod="evening")
    if LAUNDRY_SAMPLE:
        lx, ly = LAUNDRY_SAMPLE
        shot("laundry", (lx + 9, ly + 11, 3.2), (lx, ly, 1.3), lens=30)
    shot("raft", (846, -930, 5), (840, -870, 0.3), lens=30)
    shot("ruts", (-10, -2300, 2.2), (18, -2150, 0), lens=28)
    shot("night_gate", (0, -140, 14), (0, 10, 8), lens=32, samples=64, tod="night")
    shot("night_city", (300, -2600, 260), (300, -1200, 0), lens=35, samples=64, tod="night")
    apply_time("day")
log("LIFE_DONE")
