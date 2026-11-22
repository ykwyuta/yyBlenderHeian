"""大内裏・外観精密化その4（部品v7）スクリプト

使い方：
    blender --background heian_daidairi_detail_v19.blend \
        --python build_exterior_refine4.py

モデルv19を開いた状態で実行し、大内裏側にだけ外観の作り込みを足して
heian_daidairi_detail_v20.blend として保存し、確認画像を描く。
部品v4〜v6の続き。今回は柱まわりの構造と装いの細部。

内容（2026-11-22）：
- **組物（斗栱）**：主要殿舎21棟（大極殿、朝堂12堂・朝集堂・小安殿、
  豊楽殿、紫宸殿・清涼殿・仁寿殿・飛香舎）の柱の頭に、簡略な組物を
  付けた。軒下に垂木（部品v4・v5）はあるが、その下の柱頭が素通し
  だったための追加。斗2段と肘木（壁面方向＋直交の短い腕）で
  構成する模式表現で、軒を支える構造の気配を出す。
- **礎石**：同じ殿舎の柱の足元に石の礎石を置いた。柱が基壇から
  直接生えている状態を改める。
- **扁額**：通り抜けのある門27門の両面に、額の板（黒漆＋木の枠）を
  付けた。門名の文字は入れていない（フォントと時代考証の問題が
  あるため、板だけを置き、文字は今後の課題とする）。

利用者の提案 docs/proposal/01_non-building-enrichment.md（建築物
以外の要素：地形・大気・河川・植生・生活の気配・儀式・季節・人物）
には含まれない、建物側の要素として選んだ。同提案の E1〜E10 には
手をつけていない。新規オブジェクトは専用コレクション
COL_08_ExteriorRefine4 に入れる。市街・推定・内部には触れない。
"""
import bpy
import importlib.util
from mathutils import Vector
from collections import defaultdict

spec = importlib.util.spec_from_file_location(
    "build_detail",
    "/home/hatch/docs/proposal/history/3d/heiankyo-blender/scripts/build_chodoin_detailed.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

col = bpy.data.collections.get("COL_08_ExteriorRefine4")
if col is None:
    col = bpy.data.collections.new("COL_08_ExteriorRefine4")
    bpy.context.scene.collection.children.link(col)
col["layer"] = "exterior_refine_v7"
for _ob in list(col.objects):
    bpy.data.objects.remove(_ob, do_unlink=True)

_cubes = {}
def fbox(name, loc, dims, mat, fid=""):
    key = mat.name if mat else "None"
    mesh = _cubes.get(key)
    if mesh is None:
        mesh = bpy.data.meshes.new("Refine4Cube_" + key)
        mesh.from_pydata(
            [(-.5, -.5, -.5), (.5, -.5, -.5), (.5, .5, -.5), (-.5, .5, -.5),
             (-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5)],
            [],
            [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2),
             (2, 6, 7, 3), (3, 7, 4, 0)])
        mesh.update()
        if mat:
            mesh.materials.append(mat)
        _cubes[key] = mesh
    ob = bpy.data.objects.new(name, mesh)
    ob.location = loc
    ob.scale = dims
    if fid:
        ob["facility_id"] = fid
    col.objects.link(ob)
    return ob

def base_name(o):
    n = o.name
    return n.rsplit(".", 1)[0] if "." in n and n.rsplit(".", 1)[1].isdigit() else n

def wbbox(o):
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs = [c.x for c in cs]; ys = [c.y for c in cs]; zs = [c.z for c in cs]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

WOOD = bpy.data.materials["MAT_WoodDark"]
STONE = bpy.data.materials["MAT_Stone"]
LACQUER = bpy.data.materials["MAT_LacquerBlack"]

# ---------------------------------------------------------------- 1. 組物と礎石
HALLS = ["CHD_Daigokuden", "BURAKUDEN",
         "DAIRI_SHISHINDEN", "DAIRI_SEIRYODEN", "DAIRI_JIJU_JOKYO",
         "DAIRI_HIGYOSHA", "CHD_CHOSHUDO_E", "CHD_CHOSHUDO_W", "CHD_KOANDEN"]
HALLS += ["CHD_E%d" % i for i in range(1, 7)]
HALLS += ["CHD_W%d" % i for i in range(1, 7)]

cols_by = defaultdict(list)
for o in bpy.data.objects:
    bn = base_name(o)
    if bn.endswith("_Col"):
        cols_by[bn[:-4]].append(o)

n_bracket = 0
n_soseki = 0
for prefix in HALLS:
    cols = cols_by.get(prefix, [])
    if not cols:
        print("NOCOLS", prefix, flush=True)
        continue
    boxes = [wbbox(o) for o in cols]
    cx = sum((b[0] + b[1]) / 2.0 for b in boxes) / len(boxes)
    cy = sum((b[2] + b[3]) / 2.0 for b in boxes) / len(boxes)
    hx = max(abs((b[0] + b[1]) / 2.0 - cx) for b in boxes)
    hy = max(abs((b[2] + b[3]) / 2.0 - cy) for b in boxes)
    fid = cols[0].get("facility_id", "")
    for b in boxes:
        px, py = (b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0
        z0, z1 = b[4], b[5]
        dx, dy = px - cx, py - cy
        on_x_face = abs(dy) > hy - 1.0    # 南北の面に立つ柱（肘木はX方向）
        on_y_face = abs(dx) > hx - 1.0    # 東西の面に立つ柱（肘木はY方向）
        corner = on_x_face and on_y_face
        # 礎石
        fbox(prefix + "_Soseki", (px, py, z0 + 0.03), (0.58, 0.58, 0.18), STONE, fid)
        n_soseki += 1
        # 組物（柱頭の下0.7mに収める）
        fbox(prefix + "_BracketLow", (px, py, z1 - 0.57), (0.36, 0.36, 0.18), WOOD, fid)
        fbox(prefix + "_BracketMid", (px, py, z1 - 0.37), (0.46, 0.46, 0.22), WOOD, fid)
        if on_x_face or corner:
            fbox(prefix + "_BracketArmX", (px, py, z1 - 0.13), (1.15, 0.26, 0.26), WOOD, fid)
            n_bracket += 1
        if on_y_face or corner:
            fbox(prefix + "_BracketArmY", (px, py, z1 - 0.13), (0.26, 1.15, 0.26), WOOD, fid)
            n_bracket += 1
        n_bracket += 2
print("BRACKET_DONE brackets=%d soseki=%d" % (n_bracket, n_soseki), flush=True)

# ---------------------------------------------------------------- 2. 扁額
walls_by_prefix = defaultdict(list)
for o in bpy.data.objects:
    bn = base_name(o)
    if bn.endswith("_Wall"):
        walls_by_prefix[bn[:-5]].append(o)

n_plaq = 0
for prefix, walls in sorted(walls_by_prefix.items()):
    if len(walls) != 2 or prefix == "CHUKAIN_Side":
        continue
    a, b = wbbox(walls[0]), wbbox(walls[1])
    acx, acy = (a[0] + a[1]) / 2.0, (a[2] + a[3]) / 2.0
    bcx, bcy = (b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0
    fid = walls[0].get("facility_id", "")
    # 額は通り抜け上の梁（Lintel）の帯に掛ける。上端を梁の上面にそろえる
    lintel = next((o for o in bpy.data.objects
                   if base_name(o) == prefix + "_Lintel"), None)
    zc = (wbbox(lintel)[5] - 0.40) if lintel is not None else 3.94
    if abs(acx - bcx) >= abs(acy - bcy):
        # 南北に通り抜ける門：壁はX方向に分かれる
        lo, hi = (a, b) if acx < bcx else (b, a)
        gap = hi[0] - lo[1]
        if not (1.5 <= gap <= 8.0):
            continue
        gx = (lo[1] + hi[0]) / 2.0
        y0 = min(a[2], b[2]); y1 = max(a[3], b[3])
        for sgn, yy in ((-1, y0), (1, y1)):
            fbox(prefix + "_PlaqueFrame", (gx, yy + sgn * 0.03, zc),
                 (3.3, 0.10, 1.06), WOOD, fid)
            fbox(prefix + "_Plaque", (gx, yy + sgn * 0.09, zc),
                 (3.06, 0.06, 0.86), LACQUER, fid)
            n_plaq += 1
    else:
        lo, hi = (a, b) if acy < bcy else (b, a)
        gap = hi[2] - lo[3]
        if not (1.5 <= gap <= 8.0):
            continue
        gy = (lo[3] + hi[2]) / 2.0
        x0 = min(a[0], b[0]); x1 = max(a[1], b[1])
        for sgn, xx in ((-1, x0), (1, x1)):
            fbox(prefix + "_PlaqueFrame", (xx + sgn * 0.03, gy, zc),
                 (0.10, 3.3, 1.06), WOOD, fid)
            fbox(prefix + "_Plaque", (xx + sgn * 0.09, gy, zc),
                 (0.06, 3.06, 0.86), LACQUER, fid)
            n_plaq += 1
print("PLAQUE_DONE gates=%d" % n_plaq, flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v20.blend")
print("SAVED_V20", flush=True)

# ---------------------------------------------------------------- 確認描画
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
cam_data = bpy.data.cameras.new("V20Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V20Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

def setup_cam(loc, target, lens=35):
    cam.location = loc
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam_data.lens = lens

def render(path, w, h, samples):
    scene.render.resolution_x = w
    scene.render.resolution_y = h
    scene.cycles.samples = samples
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v20"
setup_cam((26, 508, 5.5), (0, 566, 12), lens=35)
render(OUT + "_daigokuden.png", 1280, 720, 48)
print("DGK_DONE", flush=True)
setup_cam((30, 330, 3.5), (54, 383, 6), lens=35)
render(OUT + "_chodo.png", 1280, 720, 48)
print("CHODO_DONE", flush=True)
setup_cam((0, -20, 3.2), (0, 0, 4.4), lens=35)
render(OUT + "_plaque.png", 1280, 720, 48)
print("PLAQUE_DONE", flush=True)
setup_cam((-280, 322, 4.5), (-280, 434, 6), lens=35)
render(OUT + "_burakuden.png", 1280, 720, 48)
print("BURA_DONE", flush=True)
setup_cam((430, 60, 330), (0, 640, 0), lens=35)
render(OUT + "_top.png", 1600, 1600, 32)
print("TOP_DONE", flush=True)
