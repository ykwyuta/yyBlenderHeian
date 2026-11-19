# -*- coding: utf-8 -*-
"""
大内裏ディテール生成スクリプト v5（全域建物化）

配置CSV（採用済み v3.1）を読み、大内裏の全エリアを「建物生成部品」で
形にする。文脈として残るのは外郭の築地と地面のみ。
v3の追加: 内裏の殿舎・門10門・二重の回廊。
v4の追加: 門の通り抜け開口（make_gate の passage）、豊楽院。
v5の追加（2026-11-18）: 外郭門11門の建物化、官衙ゾーンへの汎用庁舎の
充填（infill_zone。棟配置そのものは未同定の模式）、中和院・真言院の
回廊と主殿、宴の松原の松。出力画像の内訳は末尾の render 部を見ること。
v6（フェーズ6）: マテリアルにプロシージャルな質感（ノイズのまだら＋
凹凸）を追加し、照明を暖色の太陽光＋空のグラデーション＋Filmic の
コントラストに変更。v6モデル自体は v5 にこの変更を適用して作成した
（build スクリプト側にも同じ変更を反映済み）。
推定レイヤー（v7）: 第4引数に推定CSV（data/daidairi_conjectural_v1.csv、
確度D）を渡すと、「あったはずだが根拠がない」施設を推測で補って生成する。
見た目は区別しないが、データ上は専用コレクション COL_80_Conjectural と
オブジェクト属性 evidence=conjectural で厳密に分離する。v7モデル自体は
v6 へこのレイヤーを追加して作成した。

部品:
  make_hall  : 基壇＋白壁＋朱柱＋寄棟屋根（＋鴟尾）の殿舎
  make_gate  : 二重屋根の門（朱雀門・応天門・会昌門・昭慶門）
  make_tower : 二層の楼（栖鳳楼・翔鸞楼）＝ make_gate の方形版
  add_hip_roof: 寄棟屋根 v2。格子状メッシュで反り（軒の持ち上がり）と
               起りを付けた曲面屋根。軒下に垂れ（厚み）付き
  make_corridor_run: 回廊の直線区間（柱列＋低い屋根）。朝堂院を囲む

v2の変更（2026-11-18）:
  - 屋根を直線から曲面に（反り・起り）
  - 朝堂院に回廊を追加（南辺は応天門の両脇で分断）
  - 大極殿を平城宮第1次大極殿の復元値に寄せて再設定（全高約27m）

使い方:
  blender --background --python build_chodoin_detailed.py -- \
      <layout.csv> <output.blend> <output_prefix>
出力画像: <prefix>_top.png / _oblique.png / _chodoin_inner.png /
          _dairi_oblique.png / _dairi_inner.png

注意: 形状は部品レベルの模式であり、個別建物の考証形状ではない。
      大極殿は第1次（単層寄棟造・緑釉瓦の系統）を想定した仮の姿。
座標系: 原点=朱雀門中心、X=東、Y=北、Z=上、単位=メートル。
"""

import csv
import hashlib
import sys

import bpy
from mathutils import Vector

# ---------------------------------------------------------------- materials

def make_mat(name, color, roughness=0.85, color2=None, tex_scale=None, bump=0.0, metallic=0.0):
    """単色マテリアル。color2 と tex_scale を渡すと、オブジェクト座標の
    ノイズで2色をまだらに混ぜ、bump で凹凸も付ける（フェーズ6の質感）。"""
    m = bpy.data.materials.new(name=name)
    m.diffuse_color = (*color, 1.0)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    if metallic:
        bsdf.inputs["Metallic"].default_value = metallic
    if color2 is not None and tex_scale:
        coord = nt.nodes.new("ShaderNodeTexCoord")
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = tex_scale
        noise.inputs["Detail"].default_value = 2.5
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.25
        ramp.color_ramp.elements[0].color = (*color2, 1.0)
        ramp.color_ramp.elements[1].position = 0.75
        ramp.color_ramp.elements[1].color = (*color, 1.0)
        nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        if bump:
            bnode = nt.nodes.new("ShaderNodeBump")
            bnode.inputs["Strength"].default_value = bump
            bnode.inputs["Distance"].default_value = 0.12
            nt.links.new(noise.outputs["Fac"], bnode.inputs["Height"])
            nt.links.new(bnode.outputs["Normal"], bsdf.inputs["Normal"])
    return m

def setup_sky(world):
    """空のグラデーション（地平線は暖かい白、天頂は青）をワールドに設定する。"""
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 1.1
    mix = nt.nodes.new("ShaderNodeMixRGB")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    rng = nt.nodes.new("ShaderNodeMapRange")
    rng.inputs["From Min"].default_value = 0.45
    rng.inputs["From Max"].default_value = 0.8
    rng.inputs["To Min"].default_value = 0.0
    rng.inputs["To Max"].default_value = 1.0
    rng.clamp = True
    mix.inputs[1].default_value = (0.90, 0.89, 0.84, 1.0)  # 地平線
    mix.inputs[2].default_value = (0.30, 0.48, 0.74, 1.0)  # 天頂
    nt.links.new(coord.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], rng.inputs["Value"])
    nt.links.new(rng.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(mix.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

MAT = {}

def init_materials():
    MAT["vermilion"] = make_mat("MAT_Vermilion", (0.60, 0.10, 0.05), 0.55,
                                color2=(0.48, 0.07, 0.035), tex_scale=0.6, bump=0.05)
    MAT["white"] = make_mat("MAT_WhiteWall", (0.93, 0.91, 0.85), 0.95,
                            color2=(0.88, 0.86, 0.79), tex_scale=0.22, bump=0.05)
    MAT["roof"] = make_mat("MAT_RoofTile", (0.24, 0.26, 0.30), 0.8,
                           color2=(0.15, 0.16, 0.19), tex_scale=0.9, bump=0.35)
    MAT["roof_green"] = make_mat("MAT_RoofGreenGlaze", (0.06, 0.22, 0.17), 0.55,
                                 color2=(0.04, 0.15, 0.12), tex_scale=0.9, bump=0.2)
    MAT["stone"] = make_mat("MAT_Stone", (0.56, 0.54, 0.50), 0.95,
                            color2=(0.40, 0.39, 0.36), tex_scale=0.7, bump=0.4)
    MAT["wood"] = make_mat("MAT_WoodDark", (0.32, 0.21, 0.12), 0.8,
                           color2=(0.20, 0.12, 0.06), tex_scale=1.1, bump=0.08)
    MAT["gold"] = make_mat("MAT_Gold", (0.83, 0.62, 0.18), 0.32, metallic=1.0)
    MAT["sand"] = make_mat("MAT_SandGround", (0.85, 0.80, 0.68), 1.0,
                           color2=(0.72, 0.66, 0.53), tex_scale=0.05, bump=0.04)
    MAT["earth"] = make_mat("MAT_EarthGround", (0.74, 0.69, 0.57), 1.0,
                            color2=(0.58, 0.53, 0.42), tex_scale=0.05, bump=0.04)
    MAT["pine"] = make_mat("MAT_PineGreen", (0.15, 0.30, 0.14), 1.0,
                           color2=(0.08, 0.19, 0.08), tex_scale=1.4)
    MAT["trunk"] = make_mat("MAT_TrunkBrown", (0.34, 0.23, 0.14), 1.0,
                            color2=(0.22, 0.14, 0.08), tex_scale=1.2)
    MAT["road"] = make_mat("MAT_RoadGravel", (0.79, 0.76, 0.69), 1.0,
                           color2=(0.62, 0.59, 0.52), tex_scale=1.6, bump=0.15)

PALETTE = [
    (0.85, 0.35, 0.25), (0.25, 0.55, 0.85), (0.35, 0.75, 0.40),
    (0.90, 0.70, 0.25), (0.65, 0.40, 0.80), (0.30, 0.75, 0.75),
    (0.90, 0.50, 0.65), (0.55, 0.45, 0.30),
]

# ---------------------------------------------------------------- primitives

def get_or_make_collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col

def _move(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)
    return obj

def add_box(name, loc, dims, mat, col, fid=""):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        obj.data.materials.append(mat)
    obj["facility_id"] = fid
    return _move(obj, col)

def add_cylinder(name, loc, radius, depth, mat, col):
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=radius, depth=depth, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    if mat:
        obj.data.materials.append(mat)
    return _move(obj, col)

def _roof_profile(t):
    """屋根の断面曲線。t=0 が軒先、t=1 が棟。
    smoothstep で軒先と棟付近の勾配を緩やかにし、反りと起りを表現する。"""
    return t * t * (3.0 - 2.0 * t)

def add_hip_roof(name, cx, cy, w, d, eave_z, roof_h, mat, col):
    """寄棟屋根 v2（曲面）。w,d は軒先寸法。
    高さは「最も近い軒辺までの距離」で決めるため寄棟の稜線が自然に出る。
    四隅は追加で持ち上げて軒の反りを付け、軒下には垂れ（厚み）を付ける。"""
    short = min(w, d)
    seg = max(1.2, short / 12.0)
    nx = max(10, min(44, int(round(w / seg))))
    ny = max(10, min(44, int(round(d / seg))))
    verts = []
    for j in range(ny + 1):
        y = -d / 2.0 + d * j / ny
        for i in range(nx + 1):
            x = -w / 2.0 + w * i / nx
            t = min(w / 2.0 - abs(x), d / 2.0 - abs(y)) / (short / 2.0)
            t = max(0.0, min(1.0, t))
            z = eave_z + roof_h * _roof_profile(t)
            corner = (abs(x) / (w / 2.0)) * (abs(y) / (d / 2.0))
            z += roof_h * 0.055 * corner * (1.0 - t)  # 隅の反り
            verts.append((cx + x, cy + y, z))
    faces = []
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    top_faces = len(faces)
    loop = ([i for i in range(nx + 1)]
            + [j * (nx + 1) + nx for j in range(1, ny + 1)]
            + [ny * (nx + 1) + i for i in range(nx - 1, -1, -1)]
            + [j * (nx + 1) for j in range(ny - 1, 0, -1)])
    skirt0 = len(verts)
    for idx in loop:
        x, y, z = verts[idx]
        verts.append((x, y, z - 0.35))
    L = len(loop)
    for k in range(L):
        a, b = loop[k], loop[(k + 1) % L]
        a2, b2 = skirt0 + k, skirt0 + (k + 1) % L
        faces.append((a, a2, b2, b))
    faces.append(tuple(skirt0 + k for k in range(L - 1, -1, -1)))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for k, poly in enumerate(mesh.polygons):
        poly.use_smooth = k < top_faces
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    if mat:
        mesh.materials.append(mat)
    # 棟木
    top = eave_z + roof_h
    if w >= d:
        add_box(name + "_Ridge", (cx, cy, top + 0.18), (max(0.4, w - d) + 0.8, 0.55, 0.36), mat, col)
    else:
        add_box(name + "_Ridge", (cx, cy, top + 0.18), (0.55, max(0.4, d - w) + 0.8, 0.36), mat, col)
    return obj

# ---------------------------------------------------------------- builders

def make_hall(prefix, cx, cy, roof_w, roof_d, col, fid,
              kidan=None, wall_h=3.6, roof_h=None, roof_mat=None, shibi=False):
    """殿舎。roof_w/roof_d は屋根（軒先）寸法。kidan=(w,d,h) or None。"""
    roof_mat = roof_mat or MAT["roof"]
    if kidan:
        kw, kd, kh = kidan
        add_box(prefix + "_Kidan", (cx, cy, kh / 2), (kw, kd, kh), MAT["stone"], col, fid)
        base_z = kh
    else:
        base_z = 0.4
        add_box(prefix + "_Base", (cx, cy, 0.2), (roof_w * 0.92, roof_d * 0.92, 0.4), MAT["stone"], col, fid)
    bw, bd = roof_w * 0.80, roof_d * 0.80
    add_box(prefix + "_Wall", (cx, cy, base_z + wall_h / 2), (bw, bd, wall_h), MAT["white"], col, fid)
    # 朱柱：長辺側に等間隔、短辺側に両端
    long_is_x = roof_w >= roof_d
    span = max(bw, bd)
    n = max(2, int(span / 4.0))
    for i in range(n + 1):
        t = -span / 2 + span * i / n
        if long_is_x:
            for sy in (-1, 1):
                add_cylinder(prefix + "_Col", (cx + t, cy + sy * bd / 2, base_z + (wall_h + 0.6) / 2),
                             0.22, wall_h + 0.6, MAT["vermilion"], col)
        else:
            for sx in (-1, 1):
                add_cylinder(prefix + "_Col", (cx + sx * bw / 2, cy + t, base_z + (wall_h + 0.6) / 2),
                             0.22, wall_h + 0.6, MAT["vermilion"], col)
    eave_z = base_z + wall_h + 0.55
    rh = roof_h if roof_h else min(roof_w, roof_d) * 0.42
    add_hip_roof(prefix + "_Roof", cx, cy, roof_w, roof_d, eave_z, rh, roof_mat, col)
    if shibi:
        top = eave_z + rh + 0.2
        if long_is_x:
            r = max(0.2, (roof_w - roof_d) / 2.0)
            for sx in (-1, 1):
                add_box(prefix + "_Shibi", (cx + sx * r, cy, top + 0.45), (0.55, 0.85, 1.3), MAT["gold"], col, fid)
        else:
            r = max(0.2, (roof_d - roof_w) / 2.0)
            for sy in (-1, 1):
                add_box(prefix + "_Shibi", (cx, cy + sy * r, top + 0.45), (0.85, 0.55, 1.3), MAT["gold"], col, fid)

def make_gate(prefix, cx, cy, w, d, col, fid, upper=True, passage=True):
    """二重屋根の門。w は間口（東西）、d は奥行。
    passage=True の場合、下層中央に通り抜けの開口を開ける（v4で追加）。
    楼（栖鳳楼など）は passage=False で壁を閉じる。"""
    add_box(prefix + "_Kidan", (cx, cy, 0.5), (w * 1.08, d * 1.7, 1.0), MAT["stone"], col, fid)
    body_h = 3.4
    bw, bd = w * 0.86, d * 0.8
    if passage:
        pw = min(6.0, w * 0.30)   # 開口幅
        open_h = 2.9              # 開口高さ（基壇上面から）
        side_w = (bw - pw) / 2.0
        for s in (-1, 1):
            add_box(prefix + "_Wall", (cx + s * (pw / 2 + side_w / 2), cy, 1.0 + body_h / 2),
                    (side_w, bd, body_h), MAT["white"], col, fid)
        add_box(prefix + "_Lintel", (cx, cy, 1.0 + open_h + (body_h - open_h) / 2),
                (pw, bd, body_h - open_h), MAT["wood"], col, fid)
        for s in (-1, 1):  # 基壇への踏み段
            add_box(prefix + "_Step", (cx, cy + s * (d * 0.85 + 0.7), 0.25),
                    (pw + 1.5, 1.4, 0.5), MAT["stone"], col, fid)
    else:
        pw = 0.0
        add_box(prefix + "_Wall", (cx, cy, 1.0 + body_h / 2), (bw, bd, body_h), MAT["white"], col, fid)
    n = max(3, int(w / 5.0))
    for i in range(n + 1):
        x = cx - w * 0.43 + (w * 0.86) * i / n
        if passage and abs(x - cx) < pw / 2 + 0.35:
            continue  # 開口に掛かる位置には柱を立てない
        for sy in (-1, 1):
            add_cylinder(prefix + "_Col", (x, cy + sy * d * 0.42, 1.0 + (body_h + 0.6) / 2),
                         0.26, body_h + 0.6, MAT["vermilion"], col)
    add_hip_roof(prefix + "_Roof1", cx, cy, w * 1.18, d * 1.55, 1.0 + body_h + 0.55, 2.3, MAT["roof"], col)
    if upper:
        uw, ud = w * 0.52, d * 0.55
        add_box(prefix + "_Wall2", (cx, cy, 7.3 + 1.3), (uw, ud, 2.6), MAT["white"], col, fid)
        for sx in (-1, 1):
            for sy in (-1, 1):
                add_cylinder(prefix + "_Col2", (cx + sx * uw / 2, cy + sy * ud / 2, 7.3 + 1.3),
                             0.22, 3.0, MAT["vermilion"], col)
        add_hip_roof(prefix + "_Roof2", cx, cy, w * 0.82, d * 1.05, 7.3 + 2.6 + 0.4, 2.8, MAT["roof"], col)
        top = 7.3 + 2.6 + 0.4 + 2.8 + 0.2
        r = max(0.2, (w * 0.82 - d * 1.05) / 2.0)
        for sx in (-1, 1):
            add_box(prefix + "_Shibi", (cx + sx * r, cy, top + 0.4), (0.5, 0.8, 1.1), MAT["gold"], col, fid)

def make_corridor_run(prefix, x1, y1, x2, y2, col):
    """回廊の直線区間（軸平行のみ）。礎石代わりの台＋朱柱列＋低い屋根。"""
    horizontal = (y1 == y2)
    length = abs(x2 - x1) if horizontal else abs(y2 - y1)
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    width = 3.6
    if horizontal:
        add_box(prefix + "_Base", (cx, cy, 0.15), (length, width, 0.3), MAT["stone"], col, "CHD_CORRIDOR")
    else:
        add_box(prefix + "_Base", (cx, cy, 0.15), (width, length, 0.3), MAT["stone"], col, "CHD_CORRIDOR")
    n = max(2, int(length / 4.5))
    for i in range(n + 1):
        t = -length / 2.0 + length * i / n
        for s in (-1, 1):
            if horizontal:
                add_cylinder(prefix + "_Col", (cx + t, cy + s * (width / 2 - 0.25), 0.3 + 1.3),
                             0.09, 2.6, MAT["vermilion"], col)
            else:
                add_cylinder(prefix + "_Col", (cx + s * (width / 2 - 0.25), cy + t, 0.3 + 1.3),
                             0.09, 2.6, MAT["vermilion"], col)
    if horizontal:
        add_hip_roof(prefix + "_Roof", cx, cy, length + 1.2, width + 1.0, 3.15, 1.15, MAT["roof"], col)
    else:
        add_hip_roof(prefix + "_Roof", cx, cy, width + 1.0, length + 1.2, 3.15, 1.15, MAT["roof"], col)

def build_chodoin_corridors(col):
    """朝堂院の回廊。区画（x -85..85、y 180..586）の内側に沿って張る。
    南辺は応天門と両脇の楼を避けて両側に分断する。北辺は大極殿基壇の北側。"""
    make_corridor_run("KAIRO_E", 78, 190, 78, 581, col)
    make_corridor_run("KAIRO_W", -78, 190, -78, 581, col)
    make_corridor_run("KAIRO_N", -78, 581, 78, 581, col)
    make_corridor_run("KAIRO_S_E", 24, 190, 78, 190, col)
    make_corridor_run("KAIRO_S_W", -78, 190, -24, 190, col)

def rotate_objects_90(objs, cx, cy):
    """生成直後のオブジェクト群を中心 (cx, cy) の周りに90度回す。
    頂点に座標を焼き込んだ屋根メッシュは頂点ごと回す。"""
    import math
    for obj in objs:
        if obj.type == "MESH" and abs(obj.location.x) < 1e-6 and abs(obj.location.y) < 1e-6:
            for v in obj.data.vertices:
                dx, dy = v.co.x - cx, v.co.y - cy
                v.co.x, v.co.y = cx - dy, cy + dx
            obj.data.update()
        else:
            dx, dy = obj.location.x - cx, obj.location.y - cy
            obj.location.x, obj.location.y = cx - dy, cy + dx
            obj.rotation_euler.z += math.radians(90)

def build_gate_rotated(prefix, cx, cy, w, d, col, fid, upper):
    """東西の壁に付く門：間口を東西に作ってから90度回して南北向きにする。"""
    before = set(bpy.data.objects)
    make_gate(prefix, cx, cy, w, d, col, fid, upper=upper)
    rotate_objects_90([o for o in bpy.data.objects if o not in before], cx, cy)

def build_dairi_corridors(col):
    """内裏の回廊：外郭（x 170..390、y 670..970）と内郭（x 194.5..365.5、
    y 702..918）の内側に沿う二重。正門の基壇に当たる区間は分断する。"""
    make_corridor_run("D_KAIRO_G_E", 383, 677, 383, 963, col)
    make_corridor_run("D_KAIRO_G_W", 177, 677, 177, 963, col)
    make_corridor_run("D_KAIRO_G_N_E", 294, 963, 383, 963, col)
    make_corridor_run("D_KAIRO_G_N_W", 177, 963, 266, 963, col)
    make_corridor_run("D_KAIRO_G_S_E", 300, 677, 383, 677, col)
    make_corridor_run("D_KAIRO_G_S_W", 177, 677, 260, 677, col)
    make_corridor_run("D_KAIRO_N_E", 359, 708.5, 359, 911.5, col)
    make_corridor_run("D_KAIRO_N_W", 201, 708.5, 201, 911.5, col)
    make_corridor_run("D_KAIRO_N_N", 201, 911.5, 359, 911.5, col)
    make_corridor_run("D_KAIRO_N_S_E", 296, 708.5, 359, 708.5, col)
    make_corridor_run("D_KAIRO_N_S_W", 201, 708.5, 264, 708.5, col)

def build_burakuin_corridors(col):
    """豊楽院の回廊。区画（x -380..-180、y 200..560）の内側に沿う。
    門の施設データがないため分断せず一周させる（模式）。"""
    make_corridor_run("B_KAIRO_E", -187, 207, -187, 553, col)
    make_corridor_run("B_KAIRO_W", -373, 207, -373, 553, col)
    make_corridor_run("B_KAIRO_N", -373, 553, -187, 553, col)
    make_corridor_run("B_KAIRO_S", -373, 207, -187, 207, col)

def _hash01(*keys):
    h = int(hashlib.md5(":".join(str(k) for k in keys).encode()).hexdigest()[:8], 16)
    return (h % 10000) / 10000.0

def make_pine(prefix, x, y, s, col):
    """松の模式：幹＋2段の傘状の樹冠。"""
    add_cylinder(prefix + "_Trunk", (x, y, 1.1 * s), 0.16 * s, 2.2 * s, MAT["trunk"], col)
    for dz, r in ((2.9, 2.3), (4.0, 1.6)):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=r * s, location=(x, y, dz * s))
        obj = bpy.context.active_object
        obj.name = prefix + "_Crown"
        obj.scale = (1.0, 1.0, 0.45)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(MAT["pine"])
        _move(obj, col)

INFILL_STYLE = {
    "GOV_SE_ADMIN": "office", "GOV_SW_POLICE": "office",
    "GOV_N_OKURA": "warehouse", "GOV_E_GUARD": "office",
    "GOV_W_GUARD": "office", "JINGIKAN": "office", "CHUMUSHO": "office",
    "TOGU_GAIN": "office", "DAIRI_SURROUND": "office",
    "ZOSHUSHI": "warehouse", "SHUISUSHI": "office", "SAMARYO": "stable",
}

def infill_zone(row, col, style=None):
    """官衙ゾーンに汎用庁舎を並べる。個別の建物配置は未同定のため、
    ゾーンの用途に合わせた模式的な充填であり、実在の棟配置ではない。"""
    fid = row["facility_id"]
    style = style or INFILL_STYLE[fid]
    cx, cy = float(row["center_x_m"]), float(row["center_y_m"])
    sx, sy = float(row["size_x_m"]), float(row["size_y_m"])
    # 地面の高さは 0.26 とし、宴の松原（0.28）など隣接スラブと同一平面にしない
    # （同一平面の重なりは描画で黒く潰れる。造酒司と松原の角で発生した）
    add_box(fid + "_Ground", (cx, cy, 0.13), (sx, sy, 0.26), MAT["earth"], col, fid)
    x0, x1 = cx - sx / 2 + 14, cx + sx / 2 - 14
    y0, y1 = cy - sy / 2 + 14, cy + sy / 2 - 14
    if style == "warehouse":
        bw, bd, gap_x, gap_y, wall_h, roof_h, cap = 24, 9, 12, 16, 2.8, 3.0, 14
    elif style == "stable":
        bw, bd, gap_x, gap_y, wall_h, roof_h, cap = 26, 8, 12, 18, 2.6, 2.6, 8
    else:
        bw, bd, gap_x, gap_y, wall_h, roof_h, cap = 18, 10, 14, 18, 3.2, None, 10
    if style == "office":
        make_hall(fid + "_Main", cx, y1 - 12, 26, 14, col, fid,
                  kidan=(29, 17, 0.8), wall_h=4.0)
        y1 -= 34
    def grid_positions(scale):
        gx, gy = gap_x * scale, gap_y * scale
        pos = []
        yy, row_i = y0 + bd / 2, 0
        while yy <= y1 - bd / 2 + 0.01:
            xx = x0 + bw / 2 + (row_i % 2) * (bw + gx) / 2
            while xx <= x1 - bw / 2 + 0.01:
                jx = (_hash01(fid, int(xx), int(yy)) - 0.5) * 6
                jy = (_hash01(fid, int(yy), int(xx)) - 0.5) * 6
                pos.append((xx + jx, yy + jy))
                xx += bw + gx
            yy += bd + gy
            row_i += 1
        return pos
    # 間隔を広げて棟数を上限に収める（等間隔サンプリングは斜め縞になるため使わない）
    positions = []
    for scale in (1.0, 1.4, 1.9, 2.5, 3.3, 4.2):
        positions = grid_positions(scale)
        if len(positions) <= cap:
            break
    for hx, hy in positions:
        make_hall(fid + "_B", hx, hy, bw + 3, bd + 3, col, fid,
                  wall_h=wall_h, roof_h=roof_h)

def build_enclosure_compound(row, col, main_name):
    """中和院・真言院：区画スラブ＋回廊＋主殿級の1棟と脇殿。"""
    fid = row["facility_id"]
    cx, cy = float(row["center_x_m"]), float(row["center_y_m"])
    sx, sy = float(row["size_x_m"]), float(row["size_y_m"])
    add_box(fid + "_Ground", (cx, cy, 0.15), (sx, sy, 0.3), MAT["sand"], col, fid)
    ix, iy = sx / 2 - 7, sy / 2 - 7
    make_corridor_run(fid + "_K_E", cx + ix, cy - iy, cx + ix, cy + iy, col)
    make_corridor_run(fid + "_K_W", cx - ix, cy - iy, cx - ix, cy + iy, col)
    make_corridor_run(fid + "_K_N", cx - ix, cy + iy, cx + ix, cy + iy, col)
    make_corridor_run(fid + "_K_S", cx - ix, cy - iy, cx + ix, cy - iy, col)
    make_hall(fid + "_Main", cx, cy + sy * 0.18, 30, 15, col, fid,
              kidan=(33, 18, 1.0), wall_h=4.5)
    for s in (-1, 1):
        make_hall(fid + "_Side", cx + s * sx * 0.24, cy - sy * 0.16, 18, 11, col, fid, wall_h=3.4)

def build_compound_wall(prefix, cx, cy, sx, sy, col):
    """官衙区画を囲む築地塀（推定レイヤー用）。南辺中央に門の開口を空ける。
    白い塀本体＋瓦色の笠木で表現する。"""
    inset = 1.2
    h, t = 2.4, 0.7
    ix, iy = sx / 2 - inset, sy / 2 - inset
    runs = [
        ("N", cx, cy + iy, 2 * ix, t),
        ("E", cx + ix, cy, t, 2 * iy),
        ("W", cx - ix, cy, t, 2 * iy),
    ]
    gap = 8.0
    seg = (2 * ix - gap) / 2
    runs.append(("S1", cx - gap / 2 - seg / 2, cy - iy, seg, t))
    runs.append(("S2", cx + gap / 2 + seg / 2, cy - iy, seg, t))
    for tag, x, y, w, d in runs:
        add_box(prefix + "_Wall" + tag, (x, y, h / 2), (w, d, h), MAT["white"], col, prefix)
        add_box(prefix + "_Cap" + tag, (x, y, h + 0.15), (w, d + 0.35, 0.3), MAT["roof"], col, prefix)

def build_conjectural(row, col):
    """推定レイヤー（daidairi_conjectural_v1.csv）の1行を生成する。
    根拠のある施設とは混ぜず、呼び出し側で専用コレクションに入れる。"""
    fid = row["facility_id"]
    cx, cy = float(row["center_x_m"]), float(row["center_y_m"])
    sx, sy = float(row["size_x_m"]), float(row["size_y_m"])
    typ = row["type"]
    if typ == "compound_wall":
        build_compound_wall(fid, cx, cy, sx, sy, col)
    elif typ == "office_compound":
        infill_zone(row, col, style="office")
        build_compound_wall(fid, cx, cy, sx, sy, col)
    elif typ == "warehouse":
        make_hall(fid, cx, cy, sx + 3, sy + 3, col, fid, wall_h=2.8, roof_h=3.0)
    elif typ == "court_sand":
        add_box(fid + "_Sand", (cx, cy, 0.04), (sx, sy, 0.08), MAT["sand"], col, fid)
    else:  # hall
        kidan = (sx + 3, sy + 3, 0.8) if sx >= 24 else None
        make_hall(fid, cx, cy, sx + 4, sy + 4, col, fid, kidan=kidan, wall_h=3.8)

KOKYO_HALLS = {"DAIRI_SHOYOSHA", "DAIRI_HIGYOSHA", "DAIRI_REIKEIDEN",
               "DAIRI_SHOKADEN", "DAIRI_KOKIDEN", "DAIRI_GYOKASHA",
               "DAIRI_TOKADEN", "DAIRI_JOGANDEN", "DAIRI_SHUHOSHA",
               "DAIRI_JONEIDEN", "DAIRI_SENYODEN", "DAIRI_SHUKUKEISHA"}

def build_detail_dairi(row, col):
    fid = row["facility_id"]
    cx, cy = float(row["center_x_m"]), float(row["center_y_m"])
    sx, sy = float(row["size_x_m"]), float(row["size_y_m"])
    if fid == "DAIRI_SHISHINDEN":
        make_hall(fid, cx, cy, sx + 6, sy + 6, col, fid,
                  kidan=(sx + 4, sy + 4, 1.5), wall_h=5.5, roof_h=8.5, shibi=True)
    elif fid in ("DAIRI_SEIRYODEN", "DAIRI_JIJU_JOKYO"):
        make_hall(fid, cx, cy, sx + 5, sy + 5, col, fid,
                  kidan=(sx + 2, sy + 2, 1.0), wall_h=4.5)
    elif fid in KOKYO_HALLS:
        make_hall(fid, cx, cy, sx + 4, sy + 4, col, fid, wall_h=3.2)
    elif fid == "DAIRI_KENREIMON":
        make_gate(fid, cx, cy, 26, 12, col, fid)
    elif fid == "DAIRI_SAKUHEIMON":
        make_gate(fid, cx, cy, 22, 11, col, fid)
    elif fid in ("DAIRI_KENSHUNMON", "DAIRI_GISHUMON"):
        build_gate_rotated(fid, cx, cy, 20, 10, col, fid, upper=True)
    elif fid == "DAIRI_SHOMEIMON":
        make_gate(fid, cx, cy, 22, 11, col, fid)
    elif fid == "DAIRI_GENKIMON":
        make_gate(fid, cx, cy, 20, 10, col, fid, upper=False)
    elif fid in ("DAIRI_SENYOMON", "DAIRI_INMEIMON"):
        build_gate_rotated(fid, cx, cy, 18, 9, col, fid, upper=False)
    elif fid in ("DAIRI_CHORAKUMON", "DAIRI_EIANMON"):
        make_gate(fid, cx, cy, 13, 8, col, fid, upper=False)

# ---------------------------------------------------------------- context boxes

HEIGHT_BY_TYPE = {"wall": 5.0, "enclosure": 0.6, "gate": 11.0, "殿舎": 13.0,
                  "hall": 8.0, "halls": 8.0, "platform": 1.8, "zone": 0.3, "reference": 0.0}

def context_box(row, col, palette_mats, flat_counter):
    fid = row["facility_id"]
    rtype = row["type"]
    cx, cy = float(row["center_x_m"]), float(row["center_y_m"])
    sx, sy = float(row["size_x_m"]), float(row["size_y_m"])
    h = HEIGHT_BY_TYPE.get(rtype, 6.0)
    if fid == "OUTER_WALL":
        t = 3.0
        for nm, loc, dims in [
            ("WALL_Tsuiji_South", (cx, cy - sy / 2, h / 2), (sx, t, h)),
            ("WALL_Tsuiji_North", (cx, cy + sy / 2, h / 2), (sx, t, h)),
            ("WALL_Tsuiji_East", (cx + sx / 2, cy, h / 2), (t, sy, h)),
            ("WALL_Tsuiji_West", (cx - sx / 2, cy, h / 2), (t, sy, h)),
        ]:
            add_box(nm, loc, dims, MAT["white"], col, fid)
        return flat_counter
    z_base = 0.0
    if rtype in ("enclosure", "zone"):
        z_base = flat_counter * 0.12
        flat_counter += 1
    idx = int(hashlib.md5(fid.encode()).hexdigest(), 16) % len(palette_mats)
    add_box("%s_%s" % (fid, row["name"]), (cx, cy, z_base + h / 2), (sx, sy, h), palette_mats[idx], col, fid)
    return flat_counter

# ---------------------------------------------------------------- main

DETAIL = {"GATE_SUJAKU", "CHD_OTENMON", "CHD_KAISHOMON", "CHD_SHOKEMON",
          "CHD_SEIHO", "CHD_SHORAN", "CHD_DAIGOKUDEN", "CHD_KOANDEN",
          "CHD_CHOSHUDO_E", "CHD_CHOSHUDO_W", "CHD_RYUBIDAN",
          "CHD_E1", "CHD_E2", "CHD_E3", "CHD_E4", "CHD_E5", "CHD_E6",
          "CHD_W1", "CHD_W2", "CHD_W3", "CHD_W4", "CHD_W5", "CHD_W6",
          "DAIRI_SHISHINDEN", "DAIRI_SEIRYODEN", "DAIRI_JIJU_JOKYO",
          "DAIRI_KENREIMON", "DAIRI_SAKUHEIMON", "DAIRI_KENSHUNMON",
          "DAIRI_GISHUMON", "DAIRI_SHOMEIMON", "DAIRI_GENKIMON",
          "DAIRI_SENYOMON", "DAIRI_INMEIMON", "DAIRI_CHORAKUMON",
          "DAIRI_EIANMON", "BURAKUDEN", "UCHISAKEDONO",
          "GATE_KOKA", "GATE_BIFUKU", "GATE_TATCHI", "GATE_ANKA", "GATE_IKAN",
          "GATE_IKUHO", "GATE_TAIKEN", "GATE_YOMEI",
          "GATE_DANTEN", "GATE_MOHEKI", "GATE_INPU"} | KOKYO_HALLS

def build_detail(row, col):
    fid = row["facility_id"]
    cx, cy = float(row["center_x_m"]), float(row["center_y_m"])
    sx, sy = float(row["size_x_m"]), float(row["size_y_m"])
    if fid.startswith("DAIRI_"):
        build_detail_dairi(row, col)
    elif fid == "BURAKUDEN":
        make_hall(fid, cx, cy, sx + 5, sy + 5, col, fid,
                  kidan=(sx + 4, sy + 4, 1.5), wall_h=6.0, roof_h=9.5, shibi=True)
    elif fid == "UCHISAKEDONO":
        make_hall(fid, cx, cy, sx + 4, sy + 4, col, fid, wall_h=3.6)
    elif fid in ("GATE_IKUHO", "GATE_TAIKEN", "GATE_YOMEI",
                 "GATE_DANTEN", "GATE_MOHEKI", "GATE_INPU"):
        build_gate_rotated(fid, cx, cy, 24, 10, col, fid, upper=False)  # 東西の外郭門
    elif fid.startswith("GATE_") and fid != "GATE_SUJAKU":
        make_gate(fid, cx, cy, 24, 10, col, fid,
                  upper=fid in ("GATE_ANKA", "GATE_KOKA", "GATE_BIFUKU"))
    elif fid == "GATE_SUJAKU":
        make_gate("GATE_Sujakumon", cx, cy, 32, 12, col, fid)
    elif fid == "CHD_OTENMON":
        make_gate("CHD_Otenmon", cx, cy, 36, 14, col, fid)
    elif fid in ("CHD_KAISHOMON", "CHD_SHOKEMON"):
        make_gate(fid, cx, cy, sx, sy, col, fid)
    elif fid in ("CHD_SEIHO", "CHD_SHORAN"):
        make_gate(fid, cx, cy, 17, 15, col, fid, passage=False)  # 楼は通り抜けなし
    elif fid == "CHD_DAIGOKUDEN":
        # v2で規模を再設定：壁高9m＋屋根14mで全高約27m。
        # 平城宮第1次大極殿の復元値（全高約27m）に寄せた仮設定
        make_hall("CHD_Daigokuden", cx, cy, 53, 26, col, fid,
                  kidan=(59, 24, 2.0), wall_h=9.0, roof_h=14.0,
                  roof_mat=MAT["roof_green"], shibi=True)
    elif fid == "CHD_RYUBIDAN":
        add_box("CHD_Ryubidan", (cx, cy, 0.9), (sx, sy, 1.8), MAT["stone"], col, fid)
    elif fid in ("CHD_CHOSHUDO_E", "CHD_CHOSHUDO_W", "CHD_KOANDEN"):
        make_hall(fid, cx, cy, sx + 4, sy + 4, col, fid, wall_h=4.0)
    else:  # 朝堂12堂
        make_hall(fid, cx, cy, sx + 5, sy + 5, col, fid, wall_h=3.8)

def main():
    argv = sys.argv
    args = argv[argv.index("--") + 1:]
    csv_path, blend_out, prefix = args[0], args[1], args[2]
    conj_path = args[3] if len(args) > 3 else None

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    init_materials()
    palette_mats = [make_mat("BlockoutColor_%d" % i, c) for i, c in enumerate(PALETTE)]

    col_detail = get_or_make_collection("COL_02_Chodoin")
    col_gate = get_or_make_collection("COL_01_OuterWall_Gates")
    col_dairi = get_or_make_collection("COL_03_Dairi")
    col_bura = get_or_make_collection("COL_04_Burakuin")
    col_office = get_or_make_collection("COL_05_Offices")
    col_ctx = get_or_make_collection("COL_90_Blockout")

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    flat = 0
    n_detail = n_ctx = 0
    for row in rows:
        if row["type"] == "reference" or row.get("blockout", "yes") == "no":
            continue
        fid = row["facility_id"]
        if fid == "CHD_ENCLOSURE":
            add_box("CHD_Ground", (float(row["center_x_m"]), float(row["center_y_m"]), 0.15),
                    (float(row["size_x_m"]), float(row["size_y_m"]), 0.3), MAT["sand"], col_detail, fid)
            build_chodoin_corridors(col_detail)
            n_ctx += 1
            continue
        if fid in ("DAIRI_GAIKAKU", "DAIRI_NAIKAKU", "DAIRI_KOKYO"):
            thick = {"DAIRI_GAIKAKU": 0.30, "DAIRI_NAIKAKU": 0.42, "DAIRI_KOKYO": 0.54}[fid]
            mat = MAT["earth"] if fid == "DAIRI_NAIKAKU" else MAT["sand"]
            add_box(fid + "_Ground", (float(row["center_x_m"]), float(row["center_y_m"]), thick / 2),
                    (float(row["size_x_m"]), float(row["size_y_m"]), thick), mat, col_dairi, fid)
            if fid == "DAIRI_GAIKAKU":
                build_dairi_corridors(col_dairi)  # 外郭・内郭の両方をここで一括生成
            n_ctx += 1
            continue
        if fid in INFILL_STYLE:
            infill_zone(row, col_office)
            n_ctx += 1
            continue
        if fid in ("CHUKAIN", "SHINGONIN"):
            build_enclosure_compound(row, col_office, fid)
            n_ctx += 1
            continue
        if fid == "EN_MATSUBARA":
            add_box("EN_Ground", (float(row["center_x_m"]), float(row["center_y_m"]), 0.14),
                    (float(row["size_x_m"]), float(row["size_y_m"]), 0.28), MAT["sand"], col_office, fid)
            for i in range(14):
                px = float(row["center_x_m"]) + (_hash01(fid, i, 1) - 0.5) * (float(row["size_x_m"]) - 40)
                py = float(row["center_y_m"]) + (_hash01(fid, i, 2) - 0.5) * (float(row["size_y_m"]) - 40)
                make_pine("EN_Pine", px, py, 0.9 + _hash01(fid, i, 3) * 0.5, col_office)
            n_ctx += 1
            continue
        if fid == "BURAKUIN_ENCLOSURE":
            add_box("BURA_Ground", (float(row["center_x_m"]), float(row["center_y_m"]), 0.15),
                    (float(row["size_x_m"]), float(row["size_y_m"]), 0.3), MAT["sand"], col_bura, fid)
            build_burakuin_corridors(col_bura)
            n_ctx += 1
            continue
        if fid in DETAIL:
            if fid.startswith("GATE_"):
                target = col_gate
            elif fid.startswith("DAIRI_"):
                target = col_dairi
            elif fid == "BURAKUDEN":
                target = col_bura
            elif fid == "UCHISAKEDONO":
                target = col_office
            else:
                target = col_detail
            build_detail(row, target)
            n_detail += 1
        else:
            flat = context_box(row, col_ctx, palette_mats, flat)
            n_ctx += 1

    # 推定レイヤー（任意）：根拠のある施設とは混ぜず、専用コレクションと
    # オブジェクト属性 evidence=conjectural でデータ上区別する
    if conj_path:
        col_conj = get_or_make_collection("COL_80_Conjectural")
        col_conj["layer"] = "conjectural"
        with open(conj_path, newline="", encoding="utf-8") as f:
            conj_rows = list(csv.DictReader(f))
        for row in conj_rows:
            if row.get("blockout", "yes") == "no":
                continue
            build_conjectural(row, col_conj)
        for obj in col_conj.objects:
            obj["evidence"] = "conjectural"
        print("CONJECTURAL_DONE rows=%d objects=%d" % (len(conj_rows), len(col_conj.objects)))

    # 地面と朱雀大路（軸線ビューのための文脈）
    add_box("GROUND_Plane", (0, 697, -0.15), (2400, 2400, 0.3), MAT["earth"], col_ctx, "GROUND")
    add_box("ROAD_SuzakuOji", (0, -215, 0.06), (84, 430, 0.12), MAT["road"], col_ctx, "ROAD")

    # ライト（フェーズ6：暖色の太陽光＋空のグラデーション）
    sun_data = bpy.data.lights.new(name="Sun", type="SUN")
    sun_data.energy = 3.2
    sun_data.color = (1.0, 0.93, 0.82)
    sun = bpy.data.objects.new(name="Sun", object_data=sun_data)
    bpy.context.scene.collection.objects.link(sun)
    sun.rotation_euler = (0.9, 0.2, 0.6)

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.use_denoising = False
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = 0.1
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    setup_sky(scene.world)

    def setup_cam(loc, target, ortho=None, lens=35):
        bpy.ops.object.camera_add(location=loc)
        cam = bpy.context.active_object
        direction = Vector(target) - cam.location
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        cam.data.clip_start = 0.5
        cam.data.clip_end = 5000.0
        if ortho:
            cam.data.type = "ORTHO"
            cam.data.ortho_scale = ortho
        else:
            cam.data.lens = lens
        scene.camera = cam
        return cam

    bpy.ops.wm.save_as_mainfile(filepath=blend_out)

    def render(path, res_x, res_y, samples):
        scene.cycles.samples = samples
        scene.render.resolution_x, scene.render.resolution_y = res_x, res_y
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)

    # 真上図
    setup_cam((0, 697, 1800), (0, 697, 0), ortho=1500)
    render(prefix + "_top.png", 1000, 1200, 16)
    # 全景斜めビュー：南東上空から大内裏全体を望む
    # （残りのビューは生成時間短縮のため、保存済みモデルから別途描く）
    setup_cam((620, -260, 300), (0, 650, 0), lens=35)
    render(prefix + "_hero.png", 1280, 720, 20)

    # レンダー用カメラを除いて保存し直す（モデル本体のみ残す）
    print("DETAIL_DONE detail=%d context=%d objects=%d" % (n_detail, n_ctx, len(bpy.data.objects)))

if __name__ == "__main__":
    main()
