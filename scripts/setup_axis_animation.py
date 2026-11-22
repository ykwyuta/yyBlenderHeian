"""軸線動画のセットアップ：v6にカメラ経路を設定し、テストフレームを描く。
経路：朱雀大路（南）→朱雀門→応天門→会昌門→朝堂院→大極殿。
門の開口（基壇上面 z=1.0 から高さ2.9）を通るため、門の通過時は
カメラ高さを 2.2 に保ち、朝堂院に入ってから緩やかに上昇する。"""
import bpy
import time
import sys
import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from heian_gpu import use_gpu  # noqa: E402  GPU があれば使う（HEIAN_DEVICE=CPU で無効）
import os
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_SCRIPT_DIR)
# 生成物（.blend・画像）の置き場所。環境変数 HEIAN_WORK で変更できる（既定: <リポジトリ>/output）
WORK = os.environ.get("HEIAN_WORK", os.path.join(_REPO, "output"))
os.makedirs(WORK, exist_ok=True)

FPS = 24
FRAME_END = 288  # 12秒

# (frame, camera xyz, target xyz)
KEYS = [
    (1,   (0, -170, 3.0), (0, 0, 8)),
    (60,  (0, -45, 2.3),  (0, 180, 9)),
    (96,  (0, 5, 2.2),    (0, 250, 10)),
    (144, (0, 120, 2.3),  (0, 300, 10)),
    (180, (0, 185, 2.2),  (0, 400, 12)),
    (216, (0, 255, 2.6),  (0, 540, 14)),
    (252, (0, 350, 5.0),  (0, 565, 15)),
    (288, (0, 445, 8.0),  (0, 565, 16)),
]

scene = bpy.context.scene

# 既存のレンダー用カメラがあれば消す（P6Cam等）
for obj in list(bpy.data.objects):
    if obj.type == "CAMERA":
        bpy.data.objects.remove(obj, do_unlink=True)

tgt = bpy.data.objects.new("AxisTarget", None)
bpy.context.collection.objects.link(tgt)

cam_data = bpy.data.cameras.new("AxisCam")
cam_data.lens = 30
cam_data.clip_start = 0.5
cam_data.clip_end = 60000.0  # 遠景の山（環境レイヤー）まで描く
cam = bpy.data.objects.new("AxisCam", cam_data)
bpy.context.collection.objects.link(cam)
con = cam.constraints.new(type="TRACK_TO")
con.target = tgt
con.track_axis = "TRACK_NEGATIVE_Z"
con.up_axis = "UP_Y"

for frame, cpos, tpos in KEYS:
    scene.frame_set(frame)
    cam.location = cpos
    cam.keyframe_insert(data_path="location", frame=frame)
    tgt.location = tpos
    tgt.keyframe_insert(data_path="location", frame=frame)

scene.frame_start = 1
scene.frame_end = FRAME_END
scene.render.fps = FPS
scene.camera = cam

scene.render.engine = "CYCLES"
use_gpu(scene)
# この Debian 版 Blender には OpenImageDenoise が無いため、デノイズは
# 使わず、適応サンプリングで空・地面などの平坦部を高速化する
scene.cycles.samples = 32
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.03
scene.cycles.adaptive_min_samples = 8
scene.cycles.use_denoising = False
scene.render.resolution_x = 960
scene.render.resolution_y = 540

OUTDIR = os.path.join(WORK, "axis_anim")
os.makedirs(OUTDIR, exist_ok=True)
scene.render.filepath = OUTDIR + "/frame_"
scene.render.image_settings.file_format = "PNG"

bpy.ops.wm.save_as_mainfile(
    filepath=os.path.join(WORK, "heian_daidairi_axis_anim.blend"))
print("ANIM_SAVED")

for f in (1, 96, 216, 288):
    scene.frame_set(f)
    scene.render.filepath = os.path.join(WORK, "anim_test_%03d" % f)
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print("TEST_FRAME", f, "sec=%.1f" % (time.time() - t0))
print("SETUP_DONE")
