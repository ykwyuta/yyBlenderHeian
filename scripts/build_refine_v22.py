"""作り込みの続きスクリプト（部品v9、モデルv22）

使い方：
    blender --background heian_daidairi_detail_v21.blend \
        --python build_refine_v22.py

モデルv21を開き、次を追加して heian_daidairi_detail_v22.blend
として保存する。確認画像つき。

内容（2026-11-22）：
- **組物・礎石の全展開**：部品v7・v8で主要殿舎に付けた組物と
  礎石を、残っていたすべての柱（官衙の庁舎・倉庫・厩舎、門の柱、
  豊楽院と朝堂院の回廊の柱など84接頭辞・3,496本）にも付け、
  大内裏の柱はすべて組物と礎石を持つようになった。組物は0.8倍。
  推定レイヤー（CONJ_）の建物の分には evidence=conjectural を
  付けた。新規分は専用コレクション COL_10_ExteriorRefine6。
- **扁額への門名は入れない**：当初は門名の金文字を入れたが、
  2026-11-22に利用者が「フォント含めてかなりこだわらないと
  違和感がある」として削除を指示したため、モデルv23で全52枚分を
  取り除いた。このスクリプトにも文字入れは含めない。扁額は
  無地のままにする。

利用者の提案 docs/proposal/01_non-building-enrichment.md の
E1〜E10 には手をつけていない。
"""
import bpy
from collections import defaultdict
from mathutils import Vector

def base_name(o):
    n = o.name
    return n.rsplit(".", 1)[0] if "." in n and n.rsplit(".", 1)[1].isdigit() else n

def wbbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

ecol = bpy.data.collections.new("COL_10_ExteriorRefine6")
bpy.context.scene.collection.children.link(ecol)
ecol["layer"] = "exterior_refine_v9"

_cubes = {}
def fbox(name, loc, dims, mat, fid="", evidence=None):
    key = mat.name if mat else "None"
    mesh = _cubes.get(key)
    if mesh is None:
        mesh = bpy.data.meshes.new("Refine6Cube_" + key)
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
STONE = bpy.data.materials["MAT_Stone"]

DONE = ("CHD_Daigokuden", "CHD_E", "CHD_W", "CHD_CHOSHU", "CHD_KOANDEN", "BURAKUDEN",
        "DAIRI_SHISHINDEN", "DAIRI_SEIRYODEN", "DAIRI_JIJUDEN", "DAIRI_HIKASHA",
        "DAIRI_GYOKASHA", "DAIRI_KOKIDEN", "DAIRI_REIKEIDEN", "DAIRI_SHUKUKEISHA",
        "DAIRI_SHOYOSHA", "DAIRI_SHUHOSHA", "DAIRI_JONEIDEN", "DAIRI_JOGANDEN",
        "DAIRI_TOKADEN", "DAIRI_SENYODEN", "DAIRI_SHOKADEN", "CHUKAIN", "SHINGONIN",
        "UCHISAKEDONO")

cols_by = defaultdict(list)
for o in bpy.data.objects:
    bn = base_name(o)
    if bn.endswith("_Col"):
        p = bn[:-4]
        if not any(p.startswith(d) for d in DONE):
            cols_by[p].append(o)

def clusters(boxes):
    pts = [((b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0, b) for b in boxes]
    groups = []
    for px, py, b in pts:
        for g in groups:
            gx = sum(p[0] for p in g) / len(g)
            gy = sum(p[1] for p in g) / len(g)
            if abs(px - gx) < 16 and abs(py - gy) < 16:
                g.append((px, py, b))
                break
        else:
            groups.append([(px, py, b)])
    return [[p[2] for p in g] for g in groups]

S = 0.8
n_bracket = 0
n_soseki = 0
first_office = None
for prefix in sorted(cols_by):
    cols = cols_by[prefix]
    fid = cols[0].get("facility_id", "")
    ev = "conjectural" if prefix.startswith("CONJ_") else None
    for boxes in clusters([wbbox(o) for o in cols]):
        cx = sum((b[0] + b[1]) / 2.0 for b in boxes) / len(boxes)
        cy = sum((b[2] + b[3]) / 2.0 for b in boxes) / len(boxes)
        hx = max(abs((b[0] + b[1]) / 2.0 - cx) for b in boxes)
        hy = max(abs((b[2] + b[3]) / 2.0 - cy) for b in boxes)
        if first_office is None and len(boxes) >= 12 and "KAIRO" not in prefix:
            first_office = (cx, cy)
        seen = set()
        for b in boxes:
            px, py = (b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0
            key = (round(px, 1), round(py, 1))
            if key in seen:
                continue
            seen.add(key)
            z0, z1 = b[4], b[5]
            dx, dy = px - cx, py - cy
            on_x_face = abs(dy) > hy - 1.0
            on_y_face = abs(dx) > hx - 1.0
            fbox(prefix + "_Soseki", (px, py, z0 + 0.03), (0.5, 0.5, 0.16), STONE, fid, ev)
            n_soseki += 1
            fbox(prefix + "_BracketLow", (px, py, z1 - 0.57 * S), (0.36 * S, 0.36 * S, 0.18 * S), WOOD, fid, ev)
            fbox(prefix + "_BracketMid", (px, py, z1 - 0.37 * S), (0.46 * S, 0.46 * S, 0.22 * S), WOOD, fid, ev)
            if on_x_face:
                fbox(prefix + "_BracketArmX", (px, py, z1 - 0.13 * S), (1.15 * S, 0.26 * S, 0.26 * S), WOOD, fid, ev)
                n_bracket += 1
            if on_y_face:
                fbox(prefix + "_BracketArmY", (px, py, z1 - 0.13 * S), (0.26 * S, 1.15 * S, 0.26 * S), WOOD, fid, ev)
                n_bracket += 1
            n_bracket += 2
print("BRACKET_ALL_DONE brackets=%d soseki=%d office_cam=%s" % (n_bracket, n_soseki, first_office), flush=True)

# 扁額への門名は入れない（2026-11-22の利用者の判断で見送り。
# モデルv23で文字はすべて削除済み）

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v22.blend")
print("SAVED_V22", flush=True)

# ---------------------------------------------------------------- 確認描画
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
cam_data = bpy.data.cameras.new("V22Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V22Cam", cam_data)
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

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v22"
setup_cam((2.5, -17, 3.2), (0, -4.5, 4.1), lens=42)
render(OUT + "_suzaku.png", 1280, 720, 64)
print("SUZAKU_DONE", flush=True)
setup_cam((2.5, 158, 3.4), (0, 176, 4.1), lens=42)
render(OUT + "_oten.png", 1280, 720, 64)
print("OTEN_DONE", flush=True)
if first_office:
    cx, cy = first_office
    setup_cam((cx - 6, cy - 15, 2.6), (cx, cy + 5, 3.8), lens=35)
    render(OUT + "_office.png", 1280, 720, 48)
    print("OFFICE_DONE", flush=True)
setup_cam((430, 60, 330), (0, 640, 0), lens=35)
render(OUT + "_top.png", 1600, 1600, 32)
print("TOP_DONE", flush=True)
