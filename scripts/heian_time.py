# -*- coding: utf-8 -*-
"""時刻のプリセット（昼・朝・夕・夜）を開いているモデルに適用する（各スクリプト共通）。

環境レイヤー（build_environment.py）が作ったワールドのノード（HEIAN_Bg・HEIAN_SkyMix・
HEIAN_CloudTone・HEIAN_CloudRamp）と霞のマテリアル（MAT_EnvHaze）、太陽（Sun）の値を
書き換える。環境レイヤーのないモデルでは使えない。

使い方:
    from heian_time import apply_time, PRESETS
    apply_time("evening")

保存済みモデルで描く時刻を変えるだけなら、render_views.py などから呼べばよい。
"""
import math

import bpy
from mathutils import Vector

PRESETS = {
    # 太陽の方位（北から時計回り、度）・高度（度）・色・強さ、空の地平線と天頂の色と強さ、
    # 霞の密度（1/m）と色、雲の色・影の色・量、露出。day の太陽は v6（フェーズ6）の値を基準にした。
    # night の「太陽」は月の光として使う（青白く弱い）。
    "day": dict(az=160, el=48, sun=(1.0, 0.93, 0.82), sun_e=3.2,
                horizon=(0.66, 0.76, 0.88), zenith=(0.16, 0.34, 0.68), sky_e=1.0,
                haze=0.00008, haze_col=(0.50, 0.64, 0.88),
                cloud=(0.98, 0.97, 0.95), cloud_sh=(0.62, 0.66, 0.74), cloud_cov=0.44, exposure=-0.1),
    "morning": dict(az=105, el=12, sun=(1.0, 0.76, 0.52), sun_e=3.4,
                    horizon=(0.92, 0.74, 0.58), zenith=(0.26, 0.40, 0.66), sky_e=0.75,
                    haze=0.00013, haze_col=(0.86, 0.76, 0.70),
                    cloud=(1.0, 0.82, 0.68), cloud_sh=(0.55, 0.52, 0.58), cloud_cov=0.40, exposure=0.0),
    "evening": dict(az=250, el=7, sun=(1.0, 0.52, 0.26), sun_e=3.6,
                    horizon=(0.98, 0.56, 0.30), zenith=(0.20, 0.25, 0.48), sky_e=0.6,
                    haze=0.00010, haze_col=(0.95, 0.66, 0.48),
                    cloud=(1.0, 0.62, 0.40), cloud_sh=(0.45, 0.36, 0.42), cloud_cov=0.42, exposure=0.0),
    "night": dict(az=200, el=40, sun=(0.62, 0.72, 1.0), sun_e=0.07,
                  horizon=(0.030, 0.040, 0.075), zenith=(0.006, 0.010, 0.028), sky_e=1.0,
                  haze=0.00005, haze_col=(0.40, 0.50, 0.75),
                  cloud=(0.09, 0.10, 0.13), cloud_sh=(0.025, 0.03, 0.045), cloud_cov=0.32, exposure=1.8),
}


def apply_time(name):
    p = PRESETS[name]
    scene = bpy.context.scene
    nt = scene.world.node_tree
    nt.nodes["HEIAN_Bg"].inputs["Strength"].default_value = p["sky_e"]
    sky_in = [s for s in nt.nodes["HEIAN_SkyMix"].inputs if s.type == "RGBA"]
    sky_in[0].default_value = (*p["horizon"], 1)
    sky_in[1].default_value = (*p["zenith"], 1)
    tone = [s for s in nt.nodes["HEIAN_CloudTone"].inputs if s.type == "RGBA"]
    tone[0].default_value = (*p["cloud_sh"], 1)
    tone[1].default_value = (*p["cloud"], 1)
    scene.view_settings.exposure = p["exposure"]
    cr = nt.nodes["HEIAN_CloudRamp"]
    cr.inputs["From Min"].default_value = 1.0 - p["cloud_cov"]
    cr.inputs["From Max"].default_value = 1.0 - p["cloud_cov"] + 0.09
    vol = bpy.data.materials["MAT_EnvHaze"].node_tree.nodes["HEIAN_Haze"]
    vol.inputs["Density"].default_value = p["haze"]
    vol.inputs["Color"].default_value = (*p["haze_col"], 1)
    sun = bpy.data.objects.get("Sun")
    if sun is None:
        sd = bpy.data.lights.new("Sun", "SUN")
        sun = bpy.data.objects.new("Sun", sd)
        scene.collection.objects.link(sun)
    az, el = math.radians(p["az"]), math.radians(p["el"])
    d = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    sun.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    sun.data.color = p["sun"]
    sun.data.energy = p["sun_e"]
    sun.data.angle = math.radians(0.6)
    # 夜だけ点く灯り（第2弾の生活レイヤー）。オブジェクト属性 heian_night=1 を持つものを切り替える
    for ob in bpy.data.objects:
        if ob.get("heian_night"):
            ob.hide_render = (name != "night")
    scene["heian_time"] = name
