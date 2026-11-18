# -*- coding: utf-8 -*-
"""
保存済み .blend から追加ビューを描く汎用スクリプト。

使い方:
  blender --background <model.blend> --python render_views.py -- <out_prefix>
出力: <out_prefix>_axis_oblique.png / <out_prefix>_chodoin_inner.png
前提: モデル側に Sun と World が含まれていること（build系スクリプトが保存）。
"""
import sys

import bpy
from mathutils import Vector


def setup_cam(scene, loc, target, lens):
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.active_object
    direction = Vector(target) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_start = 0.5
    cam.data.clip_end = 5000.0
    cam.data.lens = lens
    scene.camera = cam
    return cam


def main():
    argv = sys.argv
    prefix = argv[argv.index("--") + 1]

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720

    views = [
        ("axis_oblique", (120, -190, 70), (0, 420, 10), 35),
        ("chodoin_inner", (26, 232, 4), (0, 565, 15), 30),
    ]
    for name, loc, target, lens in views:
        cam = setup_cam(scene, loc, target, lens)
        scene.render.filepath = "%s_%s.png" % (prefix, name)
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(cam, do_unlink=True)
        print("VIEW_DONE", name)


if __name__ == "__main__":
    main()
