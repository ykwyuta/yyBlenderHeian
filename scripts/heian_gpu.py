# -*- coding: utf-8 -*-
"""Cycles のレンダーデバイス選択（各スクリプト共通）。

既定では GPU を探して使い（OptiX → CUDA → HIP → oneAPI → Metal の順）、
見つからなければ CPU で描く。環境変数で上書きできる:
  HEIAN_DEVICE=CPU     … 常に CPU
  HEIAN_DEVICE=OPTIX   … 種類を指定（CUDA / HIP / ONEAPI / METAL も可）
注意: GPU の選択はプリファレンス側の設定で .blend には保存されない。
保存済み .blend をコマンドラインで描くときは `-- --cycles-device OPTIX`
のように指定する（render_axis_anim.ps1 / .sh を参照）。
"""
import os

import bpy

_ORDER = ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL")


def use_gpu(scene):
    """scene のデバイスを設定し、使ったデバイス種別（"CPU" か "OPTIX" など）を返す。"""
    want = os.environ.get("HEIAN_DEVICE", "GPU").upper()
    if want == "CPU":
        scene.cycles.device = "CPU"
        return "CPU"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    order = _ORDER if want == "GPU" else (want,)
    for dtype in order:
        try:
            prefs.compute_device_type = dtype
        except TypeError:
            continue  # このビルド／OSに無い種別
        if hasattr(prefs, "refresh_devices"):
            prefs.refresh_devices()
        else:
            prefs.get_devices()
        devs = [d for d in prefs.devices if d.type == dtype]
        if not devs:
            continue
        for d in prefs.devices:
            d.use = d.type == dtype
        scene.cycles.device = "GPU"
        print("RENDER_DEVICE", dtype, [d.name for d in devs], flush=True)
        return dtype
    scene.cycles.device = "CPU"
    print("RENDER_DEVICE CPU (GPU not found)", flush=True)
    return "CPU"
