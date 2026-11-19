# -*- coding: utf-8 -*-
"""
大内裏ブロックアウト生成スクリプト v1

配置CSV（daidairi_layout_v0.csv）を読み、全施設を白箱で配置して
.blend を保存し、真上からの確認画像をレンダリングする。

使い方（Blender導入後）:
  blender --background --python build_daidairi_blockout.py -- \
      <layout.csv> <output.blend> <output_topview.png>

座標系: 原点=朱雀門中心、X=東、Y=北、Z=上、単位=メートル。
CSVの確度Cは仮置きであり、本スクリプトの出力は規模検証用である。
"""

import csv
import sys

import bpy
import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from heian_gpu import use_gpu  # noqa: E402  GPU があれば使う（HEIAN_DEVICE=CPU で無効）

HEIGHT_BY_TYPE = {
    "wall": 5.0,
    "enclosure": 0.6,
    "gate": 11.0,
    "殿舎": 13.0,
    "hall": 8.0,
    "halls": 8.0,
    "platform": 1.8,
    "zone": 0.3,
    "reference": 0.0,
}


def parse_args():
    argv = sys.argv
    args = argv[argv.index("--") + 1:] if "--" in argv else []
    if len(args) != 3:
        raise SystemExit("usage: -- <layout.csv> <output.blend> <output_topview.png>")
    return args


def get_or_make_collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def box(name, loc, dims, collection, facility_id="", certainty=""):
    if dims[0] <= 0 or dims[1] <= 0 or dims[2] <= 0:
        return None
    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    collection.objects.link(obj)
    obj["facility_id"] = facility_id
    obj["certainty"] = certainty
    return obj


def main():
    csv_path, blend_out, png_out = parse_args()
    blend_out, png_out = _os.path.abspath(blend_out), _os.path.abspath(png_out)

    # 既存オブジェクトを消してから始める
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    blockout = get_or_make_collection("COL_90_Blockout")

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    count = 0
    flat_counter = 0  # 薄い区画スラブ同士の上面が重なって描画が乱れるのを避ける段差
    for row in rows:
        fid = row["facility_id"]
        rtype = row["type"]
        if rtype == "reference":
            continue
        if row.get("blockout", "yes") == "no":
            continue  # 基準年時点で存在しない等、CSV側で除外指定された施設
        cx = float(row["center_x_m"])
        cy = float(row["center_y_m"])
        sx = float(row["size_x_m"])
        sy = float(row["size_y_m"])
        h = HEIGHT_BY_TYPE.get(rtype, 6.0)

        if fid == "OUTER_WALL":
            # 外郭は四辺の築地として描く（中身が見えるように）
            t = 3.0
            box("WALL_Tsuiji_South", (cx, cy - sy / 2, h / 2), (sx, t, h), blockout, fid, row["certainty"])
            box("WALL_Tsuiji_North", (cx, cy + sy / 2, h / 2), (sx, t, h), blockout, fid, row["certainty"])
            box("WALL_Tsuiji_East", (cx + sx / 2, cy, h / 2), (t, sy, h), blockout, fid, row["certainty"])
            box("WALL_Tsuiji_West", (cx - sx / 2, cy, h / 2), (t, sy, h), blockout, fid, row["certainty"])
            count += 4
            continue

        z_base = 0.0
        if rtype in ("enclosure", "zone"):
            z_base = flat_counter * 0.12
            flat_counter += 1
        name = "%s_%s" % (fid, row["name"])
        box(name, (cx, cy, z_base + h / 2), (sx, sy, h), blockout, fid, row["certainty"])
        count += 1

        if fid == "CHD_DAIGOKUDEN":
            # 基壇の上に建物本体の白箱を重ねる（第1次・単層の想定ボリューム）
            box("CHD_DAIGOKUDEN_Building", (cx, cy, 2.0 + 6.5), (45.0, 20.0, 13.0),
                blockout, fid, row["certainty"])
            count += 1

    # 地面（対比用）＋施設ごとの色分けマテリアル
    # ※ヘッドレス環境では Workbench/Eevee が OpenGL を使えず真っ暗になるため、
    #   確認画像は Cycles(CPU) で描く（2026-11-18 実測で確認した制約）
    import hashlib

    palette = [
        (0.85, 0.35, 0.25, 1.0), (0.25, 0.55, 0.85, 1.0), (0.35, 0.75, 0.40, 1.0),
        (0.90, 0.70, 0.25, 1.0), (0.65, 0.40, 0.80, 1.0), (0.30, 0.75, 0.75, 1.0),
        (0.90, 0.50, 0.65, 1.0), (0.55, 0.45, 0.30, 1.0),
    ]
    mats = []
    for i, color in enumerate(palette):
        m = bpy.data.materials.new(name="BlockoutColor_%d" % i)
        m.diffuse_color = color
        m.use_nodes = True
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color
        mats.append(m)

    ground = box("GROUND_Plane", (0.0, 697.0, -0.15), (2400.0, 2400.0, 0.3), blockout, "GROUND", "")
    gm = bpy.data.materials.new(name="GroundMat")
    gm.diffuse_color = (0.82, 0.80, 0.72, 1.0)
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.82, 0.80, 0.72, 1.0)
    ground.data.materials.append(gm)

    for obj in blockout.objects:
        if obj.type != "MESH" or obj.name == "GROUND_Plane":
            continue
        idx = int(hashlib.md5(obj.get("facility_id", "").encode()).hexdigest(), 16) % len(mats)
        obj.data.materials.append(mats[idx])

    # 真上カメラ（正投影）で全体確認画像を撮る
    from mathutils import Vector

    bpy.ops.object.camera_add(location=(0.0, 697.0, 1800.0))
    cam = bpy.context.active_object
    direction = Vector((0.0, 697.0, 0.0)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 1500.0
    cam.data.clip_start = 10.0
    cam.data.clip_end = 5000.0  # 対象が1km級のため既定の1000mでは何も映らない
    bpy.context.scene.camera = cam

    sun_data = bpy.data.lights.new(name="Sun", type="SUN")
    sun_data.energy = 3.0
    sun = bpy.data.objects.new(name="Sun", object_data=sun_data)
    bpy.context.scene.collection.objects.link(sun)
    sun.rotation_euler = (0.9, 0.2, 0.6)

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 16
    use_gpu(scene)
    scene.cycles.use_denoising = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.92, 0.93, 0.95, 1.0)
        bg.inputs[1].default_value = 1.0
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 1200
    scene.render.filepath = png_out

    bpy.ops.wm.save_as_mainfile(filepath=blend_out)
    bpy.ops.render.render(write_still=True)
    print("BLOCKOUT_DONE objects=%d blend=%s png=%s" % (count, blend_out, png_out))


if __name__ == "__main__":
    main()
