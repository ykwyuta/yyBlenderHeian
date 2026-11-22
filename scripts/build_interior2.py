"""内裏・後宮の内部拡張スクリプト（モデルv19）

使い方：
    blender --background heian_daidairi_detail_v18.blend \
        --python build_interior2.py

v18を開き、後宮の殿舎11棟（御花舎・弘徽殿・麗景殿・淑景舎・昭陽舎・
承香殿・常寧殿・上東殿・登華殿・宣耀殿・襲芳舎）の壁を空洞化して
模式の内部（間仕切り・御帳台・屏風・几帳・畳・調度）を追加し、
heian_daidairi_detail_v19.blend として保存する。確認画像つき。

v11（build_interior.py）で記録の残る4棟に作った内部の続き。
後宮の各棟に部屋割りを示す記録は残っていないため、こちらは
全棟とも模式（evidence=schematic_interior）で、寝殿造の一般的な
構成（北側に寝所・小室、南に接客の間）をもとに、棟の大きさに
合わせて自動配置する。奇数番目の棟は左右を反転させて単調さを避ける。
内部は専用コレクション COL_90_Interior に入れる（v11と共用）。
壁の空洞化は外形を変えない（v11と同じ方式）。

利用者の提案 docs/proposal/01_non-building-enrichment.md（建築物
以外の要素：地形・大気・河川・植生・生活の気配・儀式・季節・人物）
とは対象が重ならない、建物側の作り込みとして実施する。
"""
import bpy
import os
import sys as _sys
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_SCRIPT_DIR)
_sys.path.insert(0, _SCRIPT_DIR)
from heian_gpu import use_gpu  # noqa: E402  GPU があれば使う（HEIAN_DEVICE=CPU で無効）
# 生成物（.blend・画像）の置き場所。環境変数 HEIAN_WORK で変更できる（既定: <リポジトリ>/output）
WORK = os.environ.get("HEIAN_WORK", os.path.join(_REPO, "output"))
os.makedirs(WORK, exist_ok=True)
import importlib.util
import math
from mathutils import Vector

spec = importlib.util.spec_from_file_location(
    "build_detail",
    os.path.join(_SCRIPT_DIR, "build_chodoin_detailed.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

M = {
    "vermilion": bpy.data.materials["MAT_Vermilion"],
    "white": bpy.data.materials["MAT_WhiteWall"],
    "wood": bpy.data.materials["MAT_WoodDark"],
    "light": bpy.data.materials["MAT_WoodLight"],
    "tatami": bpy.data.materials["MAT_Tatami"],
    "curtain": bpy.data.materials["MAT_Curtain"],
    "lacquer": bpy.data.materials["MAT_LacquerBlack"],
    "paper": bpy.data.materials["MAT_PaperPanel"],
}

col = mod.get_or_make_collection("COL_90_Interior")
BEFORE = len(col.objects)

CUR = {"cx": 0.0, "cy": 0.0, "fz": 0.0, "fid": "", "tag": ""}

def FB(name, loc, dims, mat_key):
    return mod.fast_box(CUR["tag"] + "_" + name, loc, dims, M[mat_key], col, CUR["fid"])

def P(name, u, v, du, dv, h, mat_key, z0=0.0):
    return FB(name, (CUR["cx"] + u, CUR["cy"] + v, CUR["fz"] + z0 + h / 2.0),
              (du, dv, h), mat_key)

def panel_x(name, u0, u1, v, h=2.3, mat_key="white"):
    return P(name, (u0 + u1) / 2.0, v, u1 - u0, 0.12, h, mat_key)

def panel_v(name, u, v0, v1, h=2.3, mat_key="white"):
    return P(name, u, (v0 + v1) / 2.0, 0.12, v1 - v0, h, mat_key)

def cyl(name, u, v, r, h, mat_key, z0=0.0):
    ob = mod.add_cylinder(CUR["tag"] + "_" + name,
                          (CUR["cx"] + u, CUR["cy"] + v, CUR["fz"] + z0 + h / 2.0),
                          r, h, M[mat_key], col)
    ob["facility_id"] = CUR["fid"]
    return ob

def kichou(name, u, v, rotz=0.0):
    g = []
    for s in (-1, 1):
        g.append(P(name + "_Post", u + s * 0.78, v, 0.07, 0.07, 1.4, "wood"))
    g.append(P(name + "_Bar", u, v, 1.66, 0.07, 0.08, "wood", z0=1.32))
    g.append(P(name + "_Cloth", u, v, 1.5, 0.04, 1.05, "paper", z0=0.22))
    if rotz:
        for ob in g:
            dx, dy = ob.location.x - CUR["cx"], ob.location.y - CUR["cy"]
            ob.location.x = CUR["cx"] + dx * math.cos(rotz) - dy * math.sin(rotz)
            ob.location.y = CUR["cy"] + dx * math.sin(rotz) + dy * math.cos(rotz)
            ob.rotation_euler.z += rotz
    return g

def byobu(name, u, v):
    for i in range(4):
        ang = math.radians(28 if i % 2 == 0 else -28)
        uu = u + (i - 1.5) * 0.78
        ob = P(name + "_P%d" % i, uu, v + (0.18 if i % 2 == 0 else -0.18),
               0.88, 0.05, 1.7, "paper", z0=0.05)
        ob.rotation_euler.z = ang

def tatami(name, u, v):
    return P(name, u, v, 1.8, 0.92, 0.05, "tatami", z0=0.06)

def canopy_dais(name, u, v, w, d):
    # 後宮の殿舎は壁高3.2mと低いため、v11の正殿級より低く作る（天井に収める）
    P(name + "_Base", u, v, w, d, 0.45, "wood")
    for sx in (-1, 1):
        for sy in (-1, 1):
            cyl(name + "_Post", u + sx * (w / 2 - 0.15), v + sy * (d / 2 - 0.15),
                0.07, 2.0, "vermilion", z0=0.45)
    P(name + "_CurtainB", u, v + d / 2 - 0.08, w - 0.2, 0.05, 1.75, "curtain", z0=0.6)
    for sx in (-1, 1):
        P(name + "_CurtainS", u + sx * (w / 2 - 0.08), v, 0.05, d - 0.2, 1.75, "curtain", z0=0.6)
    P(name + "_Seat", u, v, w * 0.5, d * 0.45, 0.35, "lacquer", z0=0.45)
    mod.add_hip_roof(CUR["tag"] + "_" + name + "_Canopy",
                     CUR["cx"] + u, CUR["cy"] + v, w + 0.7, d + 0.7,
                     CUR["fz"] + 2.45, 0.45, M["lacquer"], col)

def cabinet(name, u, v, w=1.5, d=0.75, h=1.7):
    P(name, u, v, w, d, h, "wood", z0=0.1)
    P(name + "_Top", u, v, w + 0.25, d + 0.25, 0.1, "lacquer", z0=h + 0.1)

def low_table(name, u, v):
    P(name + "_Top", u, v, 1.6, 0.9, 0.08, "lacquer", z0=0.42)
    P(name + "_Legs", u, v, 1.35, 0.68, 0.42, "wood")

def bench(name, u, v):
    P(name + "_Top", u, v, 2.4, 0.65, 0.1, "wood", z0=0.42)
    P(name + "_Legs", u, v, 2.1, 0.5, 0.42, "wood")

# ---------------------------------------------------------------- 殿舎の特定
def world_bbox(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))

def hall_frame(token):
    xs0, xs1, ys0, ys1, zs0 = [], [], [], [], []
    for ob in bpy.data.objects:
        if token in ob.name and "_Wall" in ob.name:
            (ax0, ax1), (ay0, ay1), (az0, az1) = world_bbox(ob)
            xs0.append(ax0); xs1.append(ax1)
            ys0.append(ay0); ys1.append(ay1)
            zs0.append(az0)
    x0, x1, y0, y1, z0 = min(xs0), max(xs1), min(ys0), max(ys1), min(zs0)
    return {"cx": (x0 + x1) / 2.0, "cy": (y0 + y1) / 2.0,
            "hu": (x1 - x0) / 2.0 - 0.45, "hv": (y1 - y0) / 2.0 - 0.45, "fz": z0}

def hollow_walls(token):
    wall = None
    for ob in bpy.data.objects:
        if token in ob.name and ob.name.endswith("_Wall"):
            wall = ob
            break
    (x0, x1), (y0, y1), (z0, z1) = world_bbox(wall)
    hcol = wall.users_collection[0]
    fid = wall.get("facility_id", "")
    prefix = wall.name[: -len("_Wall")]
    bpy.data.objects.remove(wall, do_unlink=True)
    t = 0.35
    cz = (z0 + z1) / 2.0
    hh = z1 - z0
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    panels = [
        ("_WallN", (cx, y1 - t / 2.0, cz), (x1 - x0, t, hh)),
        ("_WallS", (cx, y0 + t / 2.0, cz), (x1 - x0, t, hh)),
        ("_WallE", (x1 - t / 2.0, cy, cz), (t, (y1 - y0) - 2 * t, hh)),
        ("_WallW", (x0 + t / 2.0, cy, cz), (t, (y1 - y0) - 2 * t, hh)),
    ]
    for suffix, loc, dims in panels:
        mod.fast_box(prefix + suffix, loc, dims, M["white"], hcol, fid)

def begin(token, fid, tag):
    fr = hall_frame(token)
    hollow_walls(token)
    CUR.update(fr)
    CUR["fid"] = fid
    CUR["tag"] = tag
    P("Floor", 0, 0, fr["hu"] * 2 - 0.1, fr["hv"] * 2 - 0.1, 0.06, "light")
    return fr

def finish(evidence):
    for ob in col.objects:
        if ob.name.startswith(CUR["tag"] + "_"):
            ob["evidence"] = evidence

# ---------------------------------------------------------------- 模式レイアウト
def build_residence(token, tag, mirror):
    fr = begin(token, token, tag)
    hu, hv = fr["hu"], fr["hv"]
    sx = -1.0 if mirror else 1.0

    def X(a, b=None):
        if b is None:
            return sx * a
        return (min(sx * a, sx * b), max(sx * a, sx * b))

    v1 = hv * 0.38                      # 母屋と北側の小部屋群の境
    # 北側の間仕切り（中央に通路の開き）
    a, b = X(-hu, -1.6)
    panel_x("PartN1", a, b, v1)
    a, b = X(1.6, hu)
    panel_x("PartN2", a, b, v1)
    # 北東の小室（塗籠風）：境の壁に出入り口の開きを残す
    ux = X(hu * 0.45)
    panel_v("ClosetW1", ux, v1, hv * 0.74)
    panel_v("ClosetW2", ux, hv * 0.90, hv)
    P("ClosetCurtain", ux, (hv * 0.74 + hv * 0.90) / 2.0, 0.05,
      hv * 0.16, 1.7, "curtain", z0=0.25)
    # 御帳台（北西寄り）
    cw = min(3.2, hu * 0.52)
    cd = min(2.8, (hv - v1) * 0.82)
    canopy_dais("Michodai", X(-hu * 0.44), (v1 + hv) / 2.0, cw, cd)
    # 中央の接客の間：畳と調度
    tatami("Mat1", X(0.05), -hv * 0.08)
    tatami("Mat2", X(0.05), -hv * 0.08 + 0.97)
    tatami("Mat3", X(1.9), -hv * 0.08)
    tatami("Mat4", X(1.9), -hv * 0.08 + 0.97)
    byobu("Byobu", X(-hu * 0.52), -hv * 0.28)
    kichou("Kichou1", X(hu * 0.58), -hv * 0.34)
    kichou("Kichou2", X(-hu * 0.08), -hv * 0.66, rotz=sx * 0.4)
    low_table("Table", X(hu * 0.38), hv * 0.02)
    cabinet("Cabinet", X(-hu * 0.74), hv - 0.62)
    bench("Bench", X(0.0), -hv + 0.72)
    finish("schematic_interior")
    print("HALL_DONE", tag, flush=True)

HALLS = [
    ("DAIRI_GYOKASHA", "INT_GYOKA"),
    ("DAIRI_KOKIDEN", "INT_KOKI"),
    ("DAIRI_REIKEIDEN", "INT_REIKEI"),
    ("DAIRI_SHUKUKEISHA", "INT_SHUKUKEI"),
    ("DAIRI_SHOYOSHA", "INT_SHOYO"),
    ("DAIRI_SHUHOSHA", "INT_SHUHO"),
    ("DAIRI_JONEIDEN", "INT_JONEI"),
    ("DAIRI_JOGANDEN", "INT_JOGAN"),
    ("DAIRI_TOKADEN", "INT_TOKA"),
    ("DAIRI_SENYODEN", "INT_SENYO"),
    ("DAIRI_SHOKADEN", "INT_SHOKA"),
]
for i, (token, tag) in enumerate(HALLS):
    build_residence(token, tag, mirror=(i % 2 == 1))

print("INTERIOR2_DONE added=%d" % (len(col.objects) - BEFORE), flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath=os.path.join(WORK, "heian_daidairi_detail_v19.blend"))
print("SAVED_V19", flush=True)

# ---------------------------------------------------------------- 確認画像
scene = bpy.context.scene
scene.render.engine = "CYCLES"
use_gpu(scene)

def hide_roof(token):
    for ob in bpy.data.objects:
        if token in ob.name and "_Roof" in ob.name:
            ob.hide_render = True

def setup_cam(loc, target, ortho=None, lens=30):
    cam_data = bpy.data.cameras.new("Int2Cam")
    cam_data.clip_start = 0.3
    cam_data.clip_end = 400.0
    if ortho:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho
    else:
        cam_data.lens = lens
    cam = bpy.data.objects.new("Int2Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

def render(path, rx, ry, samples):
    scene.cycles.samples = samples
    scene.render.resolution_x, scene.render.resolution_y = rx, ry
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)

OUT = os.path.join(WORK, "view_v19")
fr = hall_frame("DAIRI_KOKIDEN")
hide_roof("DAIRI_KOKIDEN")
setup_cam((fr["cx"], fr["cy"], fr["fz"] + 48), (fr["cx"], fr["cy"], fr["fz"]), ortho=30)
render(OUT + "_kokiden_plan.png", 1150, 900, 24)
print("PLAN_DONE", flush=True)
setup_cam((fr["cx"] + 8.6, fr["cy"] - 4.6, fr["fz"] + 1.8),
          (fr["cx"] - 6.5, fr["cy"] + 3.4, fr["fz"] + 1.2), lens=27)
render(OUT + "_kokiden_room.png", 1280, 720, 48)
print("ROOM_DONE", flush=True)
fr2 = hall_frame("DAIRI_TOKADEN")
hide_roof("DAIRI_TOKADEN")
setup_cam((fr2["cx"], fr2["cy"], fr2["fz"] + 48), (fr2["cx"], fr2["cy"], fr2["fz"]), ortho=30)
render(OUT + "_tokaden_plan.png", 1150, 900, 24)
print("PLAN2_DONE", flush=True)
