"""殿舎の扉・窓の格子と方立スクリプト（部品v17、モデルv31）

使い方：
    blender --background heian_daidairi_detail_v30.blend \
        --python build_refine_v31.py

モデルv30を開き、部品v6（v18）で付けた殿舎の扉・窓の板面に
格子と方立を付け、heian_daidairi_detail_v31.blend として保存する。
確認画像つき。

内容（2026-11-24）：
- 部品v6で内裏・後宮・朝堂院・中和院・真言院・官衙の殿舎に付けた
  扉158枚と窓316枚は、暗い木の板面のままで、近景では
  建具らしく見えなかった。扉に方立2本、窓に縦格子3本と
  横桟1本を付け、蔀パネル（部品v6で縦桟つき）と並ぶ表情にする。
- 位置と向きは各扉・窓の実測bboxから求め、壁面からの
  出っ張りは板面の外面よりわずかに前に出す。
- 内裏・後宮・朝堂院の正殿級は、部品v7（v11）・v8（v19）・
  v9（v21）の内部化で壁が4枚パネル（_WallS等）に置き換わって
  おり、_Wall の箱はもうない。殿舎中心の参照は _Wall →
  _Kidan → _Base → _Roof → 壁パネルの順で探す。
  （初版は _Wall しか見ず、官衙129棟分しか格子が付かなかった
  ため修正。内裏・朝堂院29棟分が対象外になっていた。）
- 新規分は専用コレクション COL_18_ExteriorRefine14。
  CONJ_分の扉・窓には evidence=conjectural を引き継ぐ。

利用者の提案 docs/proposal/01_non-building-enrichment.md の
E1〜E10 には手をつけていない。
"""
import bpy
from mathutils import Vector

def base_name(o):
    n = o.name
    return n.rsplit(".", 1)[0] if "." in n and n.rsplit(".", 1)[1].isdigit() else n

def wbbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

ecol = bpy.data.collections.new("COL_18_ExteriorRefine14")
bpy.context.scene.collection.children.link(ecol)
ecol["layer"] = "exterior_refine_v17"

_cubes = {}
def fbox(name, loc, dims, mat, fid="", evidence=None):
    key = mat.name if mat else "None"
    mesh = _cubes.get(key)
    if mesh is None:
        mesh = bpy.data.meshes.new("Refine14Cube_" + key)
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
    if evidence:
        ob["evidence"] = evidence
    ecol.objects.link(ob)
    return ob

WOOD = bpy.data.materials["MAT_WoodDark"]

byname = {}
for o in bpy.data.objects:
    byname.setdefault(base_name(o), []).append(o)

def hall_center(prefix):
    """殿舎中心（薄い軸方向の符号判定用）。壁の箱が内部化で
    パネルに置き換わっている棟もあるため、中心が同じものを順に探す。"""
    for suf in ("_Wall", "_Kidan", "_Base", "_Roof",
                "_WallS", "_WallN", "_WallE", "_WallW"):
        objs = byname.get(prefix + suf, [])
        if objs:
            b = wbbox(objs[0])
            return ((b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0)
    return None

n_door = n_win = n_parts = 0
for o in list(bpy.data.objects):
    bn = base_name(o)
    if bn.endswith("_OpenDoor"):
        kind = "door"
        prefix = bn[:-len("_OpenDoor")]
    elif bn.endswith("_OpenWindow"):
        kind = "window"
        prefix = bn[:-len("_OpenWindow")]
    else:
        continue
    hc = hall_center(prefix)
    if hc is None:
        print("NOWALL", bn, flush=True)
        continue
    wcx, wcy = hc
    x0, x1, y0, y1, z0, z1 = wbbox(o)
    cx, cy, cz = (x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0
    w, d, h = x1 - x0, y1 - y0, z1 - z0
    fid = o.get("facility_id", "")
    ev = o.get("evidence")
    # 薄い軸が外法線。壁中心から見た扉・窓の側が外向き。
    if w >= d:
        axis = "y"
        sgn = 1 if cy >= wcy else -1
        off = 0.045 * sgn
    else:
        axis = "x"
        sgn = 1 if cx >= wcx else -1
        off = 0.045 * sgn
    if kind == "door":
        # 方立2本（扉幅を3分割）。方立の外面は板面より0.03前に出る。
        for k in (-1, 1):
            along = k * (w if axis == "y" else d) / 6.0
            if axis == "y":
                fbox(bn + "_Mullion", (cx + along, cy + off, cz),
                     (0.09, 0.06, h), WOOD, fid, ev)
            else:
                fbox(bn + "_Mullion", (cx + off, cy + along, cz),
                     (0.06, 0.09, h), WOOD, fid, ev)
            n_parts += 1
        n_door += 1
    else:
        # 縦格子3本＋横桟1本
        for k in (-1, 0, 1):
            along = k * w / 4.0 if axis == "y" else k * d / 4.0
            if axis == "y":
                fbox(bn + "_Lattice", (cx + along, cy + off, cz),
                     (0.08, 0.06, h), WOOD, fid, ev)
            else:
                fbox(bn + "_Lattice", (cx + off, cy + along, cz),
                     (0.06, 0.08, h), WOOD, fid, ev)
            n_parts += 1
        if axis == "y":
            fbox(bn + "_Rail", (cx, cy + off, cz), (w, 0.06, 0.12), WOOD, fid, ev)
        else:
            fbox(bn + "_Rail", (cx + off, cy, cz), (0.06, d, 0.12), WOOD, fid, ev)
        n_parts += 1
        n_win += 1
print("DOOR_LATTICE_DONE doors=%d windows=%d parts=%d" % (n_door, n_win, n_parts), flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v31.blend")
print("SAVED_V31", flush=True)

# ---------------------------------------------------------------- 確認描画
for c in bpy.data.collections:
    if c.name.startswith("COL_70"):
        c.hide_render = True
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
cam_data = bpy.data.cameras.new("V31Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V31Cam", cam_data)
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

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v31"
setup_cam((245, 805, 3.2), (245, 823.5, 3.2), lens=35)
render(OUT + "_kokyo.png", 1280, 720, 48)
print("KOKYO_DONE", flush=True)
setup_cam((238, 745, 3.5), (238, 764, 3.5), lens=35)
render(OUT + "_seiryo.png", 1280, 720, 48)
print("SEIRYO_DONE", flush=True)
setup_cam((10, -17, 1.7), (0, 3, 1.7), lens=38)
render(OUT + "_suzaku.png", 1280, 720, 48)
print("SUZAKU_DONE", flush=True)
