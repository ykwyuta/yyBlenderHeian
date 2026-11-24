"""小物の作り込みスクリプト（部品v21、モデルv35）

使い方：
    blender --background heian_daidairi_detail_v34.blend \
        --python build_refine_v35.py

モデルv34を開き、床だけの空の間だった殿舎に建物の用途に
応じた小物（調度）を置いて heian_daidairi_detail_v35.blend
として保存する。確認画像つき。

内容（2026-11-24）：
- 利用者の指摘「小物の作り込みがなく、ただの箱なのでよく
  分からない」を受けた作り込み。内部を持つ殿舎のうち調度が
  なかった44棟に、用途別の模式の小物を置いた。すべて
  COL_90_Interior、evidence=schematic_interior（推定レイヤー
  の棟は conjectural）。
- 官衙の庁舎：文机の列（紙と硯つき）、北端の屏風、棚
- 朝堂院の堂：机の列（朝集堂は茵の列、小安殿は茵と屏風・几帳）
- 豊楽殿と豊楽院の付属殿：宴の卓の列（器つき）、隅の壺、屏風
- 内酒殿：壁沿いの酒壺の列と中央の樽
- 推定の蔵：米俵の列と木箱の積み重ね
- 東寺・西寺の堂：須弥壇と金像、燭台、花壺、茵
- 推定の後宮殿舎：御帳台、畳、几帳、唐櫃、屏風、火鉢
- 中和院・真言院の脇殿：祭祀具の棚と卓
- 宮内省（推定）：調理の台、壺、木箱、棚
- 小物は文机・茵・屏風・几帳・御帳台・壺・樽・米俵・木箱・
  宴卓・作業台・棚・唐櫃・燭台・火鉢・金像の部品で組む

利用者の提案 docs/proposal/01_non-building-enrichment.md の
E1〜E10 には手をつけていない。
"""
import bpy
import math
from mathutils import Vector

M = {k: bpy.data.materials[n] for k, n in {
    "vermilion": "MAT_Vermilion", "white": "MAT_WhiteWall",
    "wood": "MAT_WoodDark", "light": "MAT_WoodLight",
    "tatami": "MAT_Tatami", "curtain": "MAT_Curtain",
    "lacquer": "MAT_LacquerBlack", "paper": "MAT_PaperPanel",
    "gold": "MAT_Gold", "stone": "MAT_Stone", "iron": "MAT_IronDark",
}.items()}

icol = bpy.data.collections.get("COL_90_Interior")

def base_name(o):
    n = o.name
    return n.rsplit(".", 1)[0] if "." in n and n.rsplit(".", 1)[1].isdigit() else n

def wbbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

_cube = {}
def cube_mesh(mat):
    if mat.name not in _cube:
        m = bpy.data.meshes.new("PropCube_" + mat.name)
        m.from_pydata(
            [(-.5, -.5, -.5), (.5, -.5, -.5), (.5, .5, -.5), (-.5, .5, -.5),
             (-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5)],
            [],
            [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2),
             (2, 6, 7, 3), (3, 7, 4, 0)])
        m.update()
        m.materials.append(mat)
        _cube[mat.name] = m
    return _cube[mat.name]

_cyl = {}
def cyl_mesh(mat, seg=14):
    key = mat.name + str(seg)
    if key not in _cyl:
        verts, faces = [], []
        for zz in (-0.5, 0.5):
            for k in range(seg):
                a = 2 * math.pi * k / seg
                verts.append((math.cos(a), math.sin(a), zz))
        for k in range(seg):
            k2 = (k + 1) % seg
            faces.append((k, k2, seg + k2, seg + k))
        faces.append(tuple(range(seg - 1, -1, -1)))
        faces.append(tuple(range(seg, 2 * seg)))
        m = bpy.data.meshes.new("PropCyl_" + key)
        m.from_pydata(verts, [], faces)
        m.update()
        m.materials.append(mat)
        _cyl[key] = m
    return _cyl[key]

def lathe_mesh(name, profile, mat, seg=14):
    verts, faces = [], []
    for (r, z) in profile:
        for k in range(seg):
            a = 2 * math.pi * k / seg
            verts.append((r * math.cos(a), r * math.sin(a), z))
    nr = len(profile)
    for i in range(nr - 1):
        for k in range(seg):
            k2 = (k + 1) % seg
            faces.append((i * seg + k, i * seg + k2, (i + 1) * seg + k2, (i + 1) * seg + k))
    m = bpy.data.meshes.new(name)
    m.from_pydata(verts, [], faces)
    m.update()
    m.materials.append(mat)
    return m

JAR = lathe_mesh("PropJarMesh", [
    (0.001, 0.0), (0.26, 0.0), (0.38, 0.18), (0.44, 0.45),
    (0.36, 0.72), (0.20, 0.85), (0.20, 0.95), (0.27, 1.0)], M["stone"])
STATUE = lathe_mesh("PropStatueMesh", [
    (0.001, 0.0), (0.34, 0.0), (0.36, 0.08), (0.27, 0.30),
    (0.30, 0.46), (0.20, 0.62), (0.13, 0.74), (0.155, 0.88),
    (0.10, 1.02), (0.001, 1.08)], M["gold"])

CUR = {}
_counter = [0]

def _mk(mesh, loc, scale):
    _counter[0] += 1
    ob = bpy.data.objects.new("PROP_%s_%04d" % (CUR["tag"], _counter[0]), mesh)
    ob.location = loc
    ob.scale = scale
    ob["facility_id"] = CUR["fid"]
    ob["evidence"] = CUR["ev"]
    icol.objects.link(ob)
    return ob

def place(du, dv, h, mat, u, v, z0=0.0, swap=False):
    """(u,v) は棟の長軸方向 u・短軸方向 v の局所座標"""
    if CUR["lx"]:
        loc = (CUR["cx"] + u, CUR["cy"] + v, CUR["fz"] + z0 + h / 2.0)
        dims = (dv, du, h) if swap else (du, dv, h)
    else:
        loc = (CUR["cx"] + v, CUR["cy"] + u, CUR["fz"] + z0 + h / 2.0)
        dims = (du, dv, h) if swap else (dv, du, h)
    return _mk(cube_mesh(M[mat]), loc, dims)

def cyl(r, h, mat, u, v, z0=0.0, seg=14):
    if CUR["lx"]:
        loc = (CUR["cx"] + u, CUR["cy"] + v, CUR["fz"] + z0 + h / 2.0)
    else:
        loc = (CUR["cx"] + v, CUR["cy"] + u, CUR["fz"] + z0 + h / 2.0)
    return _mk(cyl_mesh(M[mat], seg), loc, (r, r, h))

def lathe(mesh, s, u, v, z0=0.0):
    if CUR["lx"]:
        loc = (CUR["cx"] + u, CUR["cy"] + v, CUR["fz"] + z0)
    else:
        loc = (CUR["cx"] + v, CUR["cy"] + u, CUR["fz"] + z0)
    return _mk(mesh, loc, (s, s, s))

# ---------------------------------------------------------------- 小物
def desk(u, v):
    place(1.3, 0.65, 0.05, "lacquer", u, v, 0.31)
    place(0.08, 0.6, 0.31, "lacquer", u - 0.55, v)
    place(0.08, 0.6, 0.31, "lacquer", u + 0.55, v)
    place(0.55, 0.38, 0.025, "paper", u - 0.2, v, 0.335)
    place(0.16, 0.11, 0.03, "stone", u + 0.35, v + 0.1, 0.335)

def mat(u, v):
    place(1.8, 0.9, 0.05, "tatami", u, v)

def screen(u, v):
    for i, s in enumerate((-0.74, 0.74)):
        place(1.44, 0.04, 1.45, "paper", u + s, v + (0.16 if i == 0 else -0.16), 0.0)
        place(1.44, 0.07, 0.07, "wood", u + s, v + (0.16 if i == 0 else -0.16), 1.45)

def kichou(u, v):
    place(0.06, 0.06, 1.3, "wood", u - 0.85, v)
    place(0.06, 0.06, 1.3, "wood", u + 0.85, v)
    place(1.8, 0.07, 0.07, "wood", u, v, 1.24)
    place(1.7, 0.03, 1.05, "curtain", u, v, 0.19)

def michodai(u, v):
    place(2.6, 2.6, 0.22, "wood", u, v)
    place(2.5, 2.5, 0.04, "tatami", u, v, 0.22)
    for su in (-1.15, 1.15):
        for sv in (-1.15, 1.15):
            place(0.09, 0.09, 2.0, "vermilion", u + su, v + sv, 0.22)
    place(2.6, 0.1, 0.08, "wood", u, v - 1.15, 2.22)
    place(2.6, 0.1, 0.08, "wood", u, v + 1.15, 2.22)
    place(0.1, 2.6, 0.08, "wood", u - 1.15, v, 2.22)
    place(0.1, 2.6, 0.08, "wood", u + 1.15, v, 2.22)
    place(2.4, 0.04, 1.5, "curtain", u, v + 1.08, 0.5)

def jar(u, v, s=1.0):
    lathe(JAR, s, u, v)

def barrel(u, v):
    cyl(0.34, 0.8, "light", u, v)
    cyl(0.355, 0.06, "iron", u, v, 0.15)
    cyl(0.355, 0.06, "iron", u, v, 0.59)

def bale(u, v):
    cyl(0.33, 0.62, "tatami", u, v)
    cyl(0.34, 0.05, "wood", u, v, 0.14)
    cyl(0.34, 0.05, "wood", u, v, 0.43)

def crate(u, v, z0=0.0):
    place(0.85, 0.85, 0.6, "light", u, v, z0)
    place(0.9, 0.9, 0.07, "wood", u, v, z0 + 0.6)

def feast(u, v):
    place(1.5, 0.8, 0.05, "lacquer", u, v, 0.28)
    place(0.07, 0.7, 0.28, "lacquer", u - 0.62, v)
    place(0.07, 0.7, 0.28, "lacquer", u + 0.62, v)
    cyl(0.10, 0.035, "white", u - 0.4, v, 0.33)
    cyl(0.10, 0.035, "gold", u, v + 0.15, 0.33)
    cyl(0.10, 0.035, "white", u + 0.4, v - 0.1, 0.33)

def worktable(u, v):
    place(1.8, 0.9, 0.06, "light", u, v, 0.52)
    for su in (-0.8, 0.8):
        for sv in (-0.35, 0.35):
            place(0.08, 0.08, 0.52, "wood", u + su, v + sv)

def shelf(u, v, swap=False):
    place(0.04, 0.4, 1.5, "wood", u - 1.18, v, 0.0, swap)
    place(0.04, 0.4, 1.5, "wood", u + 1.18, v, 0.0, swap)
    for z in (0.08, 0.73, 1.38):
        place(2.4, 0.4, 0.04, "wood", u, v, z, swap)
    place(0.5, 0.3, 0.35, "light", u - 0.7, v, 0.12, swap)
    jar(u + 0.45, v, 0.55) if not swap else None
    place(0.45, 0.28, 0.3, "lacquer", u + 0.6, v, 0.77, swap)
    place(0.4, 0.26, 0.28, "light", u - 0.5, v, 0.77, swap)

def chest(u, v):
    place(1.25, 0.62, 0.55, "lacquer", u, v)
    place(1.3, 0.67, 0.08, "lacquer", u, v, 0.55)

def candle(u, v):
    cyl(0.07, 0.8, "gold", u, v)
    cyl(0.15, 0.05, "gold", u, v, 0.8)

def altar(u, v):
    place(3.2, 1.6, 0.3, "stone", u, v)
    place(2.6, 1.2, 0.25, "wood", u, v, 0.3)
    cyl(0.45, 0.35, "lacquer", u, v, 0.55, seg=8)
    lathe(STATUE, 1.0, u, v, 0.9)
    candle(u - 1.3, v + 0.2)
    candle(u + 1.3, v + 0.2)
    lathe(JAR, 0.55, u - 0.85, v + 0.25, 0.55)
    lathe(JAR, 0.55, u + 0.85, v + 0.25, 0.55)

def brazier(u, v):
    cyl(0.32, 0.28, "iron", u, v)

# ---------------------------------------------------------------- 配置
def frame_of(prefix):
    bs = [wbbox(o) for o in bpy.data.objects
          if base_name(o).startswith(prefix + "_Wall")]
    if not bs:
        return None
    x0 = min(b[0] for b in bs); x1 = max(b[1] for b in bs)
    y0 = min(b[2] for b in bs); y1 = max(b[3] for b in bs)
    z0 = min(b[4] for b in bs)
    fid = ""
    for o in bpy.data.objects:
        if base_name(o).startswith(prefix + "_Wall"):
            fid = o.get("facility_id", "")
            break
    ex, ey = x1 - x0, y1 - y0
    return {"cx": (x0 + x1) / 2, "cy": (y0 + y1) / 2, "fz": z0 + 0.06,
            "lx": ex >= ey, "hu": max(ex, ey) / 2 - 1.0,
            "hv": min(ex, ey) / 2 - 1.0, "fid": fid}

def row(u0, u1, step):
    out, u = [], u0
    while u <= u1 + 0.01:
        out.append(u)
        u += step
    return out

def lay_office():
    hu, hv = CUR["hu"], CUR["hv"]
    for v in (-hv * 0.42, hv * 0.42):
        for u in row(-hu + 1.2, hu - 1.2, 2.3):
            desk(u, v)
    screen(0, hv - 0.8)
    shelf(-hu + 0.45, 0, swap=True)

def lay_office_ritual():
    lay_office()
    feast(0, CUR["hv"] - 1.9)
    jar(-1.2, CUR["hv"] - 1.9, 0.7)
    jar(1.2, CUR["hv"] - 1.9, 0.7)

def lay_feast():
    hu, hv = CUR["hu"], CUR["hv"]
    for v in (-hv * 0.38, hv * 0.38):
        for u in row(-hu + 1.6, hu - 1.6, 2.8):
            feast(u, v)
    feast(0, hv - 1.7)
    screen(0, hv - 0.75)
    for su in (-hu + 0.9, hu - 0.9):
        for sv in (-hv + 0.9, hv - 0.9):
            jar(su, sv, 1.1)

def lay_chodo():
    hu, hv = CUR["hu"], CUR["hv"]
    for v in (-hv * 0.4, hv * 0.4):
        for u in row(-hu + 1.2, hu - 1.2, 2.5):
            desk(u, v)
    screen(0, hv - 0.8)

def lay_mats(nrows=2):
    hu, hv = CUR["hu"], CUR["hv"]
    vs = [hv * f for f in (-0.45, 0.0, 0.45)][:nrows] if nrows == 3 else \
         [hv * f for f in (-0.35, 0.35)]
    for v in vs:
        for u in row(-hu + 1.3, hu - 1.3, 2.1):
            mat(u, v)
    screen(0, hv - 0.8)

def lay_store():
    hu, hv = CUR["hu"], CUR["hv"]
    for v in (-hv * 0.5, 0.0, hv * 0.5):
        for u in row(-hu + 1.0, hu - 1.6, 1.15):
            bale(u, v)
    for u in row(-hu + 1.0, hu - 1.0, 2.2):
        crate(u, -hv + 0.7)
        crate(u, -hv + 0.7, 0.67)

def lay_sake():
    hu, hv = CUR["hu"], CUR["hv"]
    for v in (-(hv - 0.75), hv - 0.75):
        for u in row(-hu + 0.8, hu - 0.8, 1.25):
            jar(u, v, 1.05)
    for u in row(-hu + 1.4, hu - 1.4, 1.7):
        barrel(u, -0.55)
        barrel(u + 0.85, 0.55)

def lay_temple():
    hv = CUR["hv"]
    altar(0, hv - 1.6)
    for u in row(-3.2, 3.2, 2.1):
        mat(u, -0.5)

def lay_residence():
    hu, hv = CUR["hu"], CUR["hv"]
    michodai(0, hv - 2.1)
    mat(-1.0, -0.3)
    mat(1.0, -0.3)
    kichou(-hu + 1.3, -hv + 1.6)
    chest(hu - 1.3, hv - 1.2)
    screen(hu - 2.2, -hv + 0.9)
    brazier(0, -hv + 1.8)

def lay_kitchen():
    hu, hv = CUR["hu"], CUR["hv"]
    for v in (-hv * 0.4, hv * 0.4):
        for u in row(-hu + 1.6, hu - 1.6, 2.6):
            worktable(u, v)
    for u in row(-hu + 0.8, hu - 0.8, 1.6):
        jar(u, -hv + 0.75, 0.95)
    crate(-hu + 1.0, hv - 0.8)
    crate(-hu + 1.0, hv - 0.8, 0.67)
    shelf(hu - 0.45, 0, swap=True)

def lay_ritual_side():
    hu, hv = CUR["hu"], CUR["hv"]
    shelf(0, -hv + 0.35)
    shelf(0, hv - 0.35)
    worktable(0, 0)
    jar(-hu + 1.0, 0, 0.8)
    jar(hu - 1.0, 0, 0.8)

def lay_pavilion():
    hu, hv = CUR["hu"], CUR["hv"]
    for u in row(-hu + 1.4, hu - 1.4, 2.3):
        desk(u, hv * 0.3)
    mat(-1.0, -hv * 0.35)
    mat(1.0, -hv * 0.35)
    screen(0, hv - 0.8)

JOBS = [
    ("CHUMUSHO_Main", lay_office), ("GOV_E_GUARD_Main", lay_office),
    ("GOV_SE_ADMIN_Main", lay_office), ("GOV_SW_POLICE_Main", lay_office),
    ("GOV_W_GUARD_Main", lay_office), ("TOGU_GAIN_Main", lay_office),
    ("SHUISUSHI_Main", lay_office), ("JINGIKAN_Main", lay_office_ritual),
    ("CONJ_DAIRI_KURANDO", lay_office),
    ("BURAKUDEN", lay_feast), ("CONJ_BURAKU_EAST", lay_feast),
    ("CONJ_BURAKU_WEST", lay_feast), ("CONJ_BURAKU_SOUTH", lay_feast),
    ("UCHISAKEDONO", lay_sake),
    ("CONJ_BURAKU_STORE_N1", lay_store), ("CONJ_BURAKU_STORE_N2", lay_store),
    ("CONJ_BURAKU_STORE_N3", lay_store),
    ("LM_TOJI_Hall", lay_temple), ("LM_SAIJI_Hall", lay_temple),
    ("CONJ_DAIRI_ANPUKU", lay_residence), ("CONJ_DAIRI_KORYO", lay_residence),
    ("CONJ_DAIRI_SHUNKO", lay_residence),
    ("CONJ_KUNAISHŌ_Main", lay_kitchen),
    ("CHUKAIN_Side", lay_ritual_side), ("SHINGONIN_Side", lay_ritual_side),
    ("LM_SHINSENEN_Hall", lay_pavilion),
    ("CHD_SEIHO", lay_mats), ("CHD_SHORAN", lay_mats),
    ("CONJ_CHD_SHOANDEN", lay_mats),
    ("CHD_CHOSHUDO_E", lambda: lay_mats(3)), ("CHD_CHOSHUDO_W", lambda: lay_mats(3)),
    ("CHD_KOANDEN", lay_mats),
]
JOBS += [("CHD_E%d" % i, lay_chodo) for i in range(1, 7)]
JOBS += [("CHD_W%d" % i, lay_chodo) for i in range(1, 7)]

done = 0
for prefix, fn in JOBS:
    fr = frame_of(prefix)
    if fr is None:
        print("SKIP_NOFRAME", prefix, flush=True)
        continue
    CUR.clear()
    CUR.update(fr)
    CUR["tag"] = prefix.replace("Ō", "O")
    CUR["ev"] = "conjectural" if prefix.startswith("CONJ_") else "schematic_interior"
    before = _counter[0]
    fn()
    done += 1
    print("PROPS", prefix, _counter[0] - before, flush=True)
print("PROPS_DONE halls=%d objects=%d" % (done, _counter[0]), flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v35.blend")
print("SAVED_V35", flush=True)

# ---------------------------------------------------------------- 確認描画
for c in bpy.data.collections:
    if c.name.startswith("COL_70"):
        c.hide_render = True
for o in bpy.data.objects:
    if base_name(o).startswith("BURAKUDEN_Roof") or base_name(o).startswith("UCHISAKEDONO_Roof"):
        o.hide_render = True
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
cam_data = bpy.data.cameras.new("V35Cam")
cam_data.clip_end = 9000
cam = bpy.data.objects.new("V35Cam", cam_data)
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

fr = frame_of("BURAKUDEN")
setup_cam((fr["cx"], fr["cy"] - 13.5, fr["fz"] + 2.0),
          (fr["cx"], fr["cy"] + 14, fr["fz"] + 0.8), lens=30)
render("/home/hatch/workspace/heiankyo-blender/output/view_v35_buraku.png", 1280, 720, 48)
print("BURAKU_DONE", flush=True)
fr = frame_of("UCHISAKEDONO")
setup_cam((fr["cx"], fr["cy"] - 5.2, fr["fz"] + 1.9),
          (fr["cx"], fr["cy"] + 6, fr["fz"] + 0.7), lens=30)
render("/home/hatch/workspace/heiankyo-blender/output/view_v35_sake.png", 1280, 720, 48)
print("SAKE_DONE", flush=True)
setup_cam((430, 60, 330), (0, 640, 0), lens=35)
render("/home/hatch/workspace/heiankyo-blender/output/view_v35_top.png", 1400, 1400, 24)
print("TOP_DONE", flush=True)
