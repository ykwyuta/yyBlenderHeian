"""内裏の内部生成スクリプト（追加工程、モデルv11）

使い方：
    blender --background heian_daidairi_detail_v10.blend \
        --python build_interior.py

v10を開き、内部の記録が残る4棟（清涼殿・紫宸殿・仁寿殿・飛香舎）に
間仕切りと調度を追加して heian_daidairi_detail_v11.blend として保存し、
屋根を一時的に隠した確認画像を描く。根拠と留保は 11_interior.md。
内部は専用コレクション COL_90_Interior に入れ、オブジェクト属性
evidence で資料準拠（documented_interior）と模式（schematic_interior）
を区別する。既存のモデルには触れない。
"""
import bpy
import importlib.util
import math
from mathutils import Vector

spec = importlib.util.spec_from_file_location(
    "build_detail",
    "/home/hatch/docs/proposal/history/3d/heiankyo-blender/scripts/build_chodoin_detailed.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

M = {
    "vermilion": bpy.data.materials["MAT_Vermilion"],
    "white": bpy.data.materials["MAT_WhiteWall"],
    "stone": bpy.data.materials["MAT_Stone"],
    "wood": bpy.data.materials["MAT_WoodDark"],
    "light": bpy.data.materials["MAT_WoodLight"],
    "gold": bpy.data.materials["MAT_Gold"],
    "sand": bpy.data.materials["MAT_SandGround"],
}
M["tatami"] = mod.make_mat("MAT_Tatami", (0.60, 0.56, 0.36), roughness=0.95,
                           color2=(0.53, 0.49, 0.31), tex_scale=2.0, bump=0.08)
M["curtain"] = mod.make_mat("MAT_Curtain", (0.36, 0.12, 0.16), roughness=0.9,
                            color2=(0.30, 0.10, 0.13), tex_scale=2.0, bump=0.05)
M["lacquer"] = mod.make_mat("MAT_LacquerBlack", (0.07, 0.06, 0.07), roughness=0.45,
                            color2=(0.05, 0.05, 0.06), tex_scale=2.0, bump=0.03)
M["paper"] = mod.make_mat("MAT_PaperPanel", (0.84, 0.80, 0.70), roughness=0.95,
                          color2=(0.78, 0.74, 0.64), tex_scale=1.5, bump=0.03)

col = mod.get_or_make_collection("COL_90_Interior")
col["layer"] = "interior"

CUR = {"cx": 0.0, "cy": 0.0, "fz": 0.0, "fid": "", "tag": ""}

def FB(name, loc, dims, mat_key):
    ob = mod.fast_box(CUR["tag"] + "_" + name, loc, dims, M[mat_key], col, CUR["fid"])
    return ob

def P(name, u, v, du, dv, h, mat_key, z0=0.0):
    return FB(name, (CUR["cx"] + u, CUR["cy"] + v, CUR["fz"] + z0 + h / 2.0),
              (du, dv, h), mat_key)

def panel_x(name, u0, u1, v, h=2.4, mat_key="white"):
    return P(name, (u0 + u1) / 2.0, v, u1 - u0, 0.12, h, mat_key)

def panel_v(name, u, v0, v1, h=2.4, mat_key="white"):
    return P(name, u, (v0 + v1) / 2.0, 0.12, v1 - v0, h, mat_key)

def cyl(name, u, v, r, h, mat_key, z0=0.0):
    ob = mod.add_cylinder(CUR["tag"] + "_" + name,
                          (CUR["cx"] + u, CUR["cy"] + v, CUR["fz"] + z0 + h / 2.0),
                          r, h, M[mat_key], col)
    ob["facility_id"] = CUR["fid"]
    return ob

def oct_prism(name, u, v, r, h, mat_key, z0=0.0):
    verts = []
    for zz in (0.0, h):
        for k in range(8):
            a = 2 * math.pi * k / 8 + math.pi / 8
            verts.append((r * math.cos(a), r * math.sin(a), zz))
    faces = []
    for k in range(8):
        k2 = (k + 1) % 8
        faces.append((k, k2, 8 + k2, 8 + k))
    faces.append(tuple(range(7, -1, -1)))
    faces.append(tuple(range(8, 16)))
    mesh = bpy.data.meshes.new(CUR["tag"] + "_" + name + "Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.materials.append(M[mat_key])
    ob = bpy.data.objects.new(CUR["tag"] + "_" + name, mesh)
    ob.location = (CUR["cx"] + u, CUR["cy"] + v, CUR["fz"] + z0)
    ob["facility_id"] = CUR["fid"]
    col.objects.link(ob)
    return ob

# ---------------------------------------------------------------- 調度品
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

def tatami(name, u, v, rotz=0.0):
    ob = P(name, u, v, 1.8, 0.92, 0.05, "tatami", z0=0.06)
    if rotz:
        ob.rotation_euler.z = rotz
    return ob

def canopy_dais(name, u, v, w, d):
    """御帳台：台＋朱柱＋帳（3方）＋黒漆の傘蓋。"""
    P(name + "_Base", u, v, w, d, 0.45, "wood")
    for sx in (-1, 1):
        for sy in (-1, 1):
            cyl(name + "_Post", u + sx * (w / 2 - 0.15), v + sy * (d / 2 - 0.15),
                0.07, 2.6, "vermilion", z0=0.45)
    P(name + "_CurtainB", u, v + d / 2 - 0.08, w - 0.2, 0.05, 1.85, "curtain", z0=0.65)
    for sx in (-1, 1):
        P(name + "_CurtainS", u + sx * (w / 2 - 0.08), v, 0.05, d - 0.2, 1.85, "curtain", z0=0.65)
    P(name + "_Seat", u, v, w * 0.5, d * 0.45, 0.35, "lacquer", z0=0.45)
    mod.add_hip_roof(CUR["tag"] + "_" + name + "_Canopy",
                     CUR["cx"] + u, CUR["cy"] + v, w + 0.7, d + 0.7,
                     CUR["fz"] + 3.05, 0.55, M["lacquer"], col)

def takamikura(name, u, v, s):
    """高御座：八角の台と傘蓋、帳、鳳凰の飾り。s は縮尺（高さ約5m×s）。"""
    oct_prism(name + "_Base", u, v, 2.25 * s, 0.55, "lacquer")
    for k in range(8):
        a = 2 * math.pi * k / 8 + math.pi / 8
        cyl(name + "_Post%d" % k, u + 1.85 * s * math.cos(a), v + 1.85 * s * math.sin(a),
            0.08, 3.9 * s, "lacquer", z0=0.55)
    for k in range(8):
        a = 2 * math.pi * k / 8 + math.pi / 8
        if -0.6 < math.sin(a) < 0.0 or math.sin(a) < -0.85:
            continue  # 正面（南）は開ける
        uu = u + 1.92 * s * math.cos(a)
        vv = v + 1.92 * s * math.sin(a)
        ob = P(name + "_Curtain%d" % k, uu - CUR["cx"] + (CUR["cx"] - CUR["cx"]), vv, 0, 0, 0, "curtain")
        # 位置と寸法を直接設定し直す（八角の辺に沿わせる）
        ob.location = (CUR["cx"] + uu, CUR["cy"] + vv, CUR["fz"] + 0.75 + 1.55 * s)
        ob.scale = (1.42 * s, 0.05, 3.1 * s)
        ob.rotation_euler.z = -a + math.pi / 2
    P(name + "_Chair", u, v + 0.3 * s, 0.95 * s, 0.8 * s, 0.5, "lacquer", z0=0.55)
    P(name + "_ChairBack", u, v + 0.62 * s, 0.95 * s, 0.1, 1.1, "lacquer", z0=1.05)
    oct_prism(name + "_Canopy", u, v, 2.55 * s, 0.4, "lacquer", z0=4.45 * s)
    oct_prism(name + "_Cap", u, v, 1.1 * s, 0.5, "lacquer", z0=4.85 * s)
    FB(name + "_Phoenix", (CUR["cx"] + u, CUR["cy"] + v, CUR["fz"] + 5.55 * s),
       (0.34, 0.2, 0.5), "gold")
    P(name + "_Step1", u, v - 2.5 * s, 1.6 * s, 0.5, 0.2, "wood")
    P(name + "_Step2", u, v - 2.15 * s, 1.6 * s, 0.4, 0.38, "wood")

def liondog(name, u, v):
    P(name + "_Body", u, v, 0.55, 0.36, 0.42, "stone", z0=0.18)
    P(name + "_Base", u, v, 0.65, 0.46, 0.18, "stone")
    P(name + "_Head", u, v + 0.16, 0.3, 0.28, 0.3, "stone", z0=0.55)

def bench(name, u, v):
    P(name + "_Top", u, v, 2.4, 0.65, 0.1, "wood", z0=0.42)
    P(name + "_Legs", u, v, 2.1, 0.5, 0.42, "wood")

def cabinet(name, u, v, w=1.6, d=0.8, h=1.8):
    P(name, u, v, w, d, h, "wood", z0=0.1)
    P(name + "_Top", u, v, w + 0.25, d + 0.25, 0.1, "lacquer", z0=h + 0.1)

def low_table(name, u, v):
    P(name + "_Top", u, v, 1.6, 0.9, 0.08, "lacquer", z0=0.42)
    P(name + "_Legs", u, v, 1.35, 0.68, 0.42, "wood")

def chair_isu(name, u, v):
    P(name + "_Seat", u, v, 0.72, 0.6, 0.1, "wood", z0=0.52)
    P(name + "_Back", u, v - 0.28, 0.72, 0.08, 0.85, "wood", z0=0.62)
    P(name + "_Legs", u, v, 0.6, 0.48, 0.52, "wood")

def nameboard(name, u, v):
    P(name + "_Board", u, v, 0.55, 0.05, 1.05, "paper", z0=0.35)
    P(name + "_Stand", u, v, 0.5, 0.3, 0.35, "wood")

# ---------------------------------------------------------------- 殿舎の特定
def world_bbox(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))

def hall_frame(token):
    # 壁は hollow_walls で4枚のパネルに置き換わるため、合算で外形を取る
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
    """対象殿舎の壁（もともと中身の詰まった箱）を、同じ外形のまま
    4枚のパネルに置き換えて室内を空洞にする。外観は変わらない。"""
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

# ---------------------------------------------------------------- 清涼殿
def build_seiryoden():
    fr = begin("DAIRI_SEIRYODEN", "DAIRI_SEIRYODEN", "INT_SEIRYO")
    hu, hv = fr["hu"], fr["hv"]
    # 母屋と北廂の境（v=+3.4）、母屋と南廂の境（v=-2.6、白壁）
    panel_x("PartN1", -hu, -3.2, 3.4)
    panel_x("PartN2", -0.8, hu, 3.4)
    panel_x("PartS1", -hu, -9.2, -2.6)
    panel_x("PartS2", -6.8, hu, -2.6)
    # 櫛形窓を象徴する開口の枠（南廂との境の西寄り）
    P("KushiPost1", -9.2, -2.6, 0.14, 0.16, 2.4, "wood")
    P("KushiPost2", -6.8, -2.6, 0.14, 0.16, 2.4, "wood")
    P("KushiLintel", -8.0, -2.6, 2.55, 0.16, 0.25, "wood", z0=2.15)
    # 夜御殿（母屋の東寄り、壁で囲った寝所）
    panel_x("YoruS", 2.0, 7.4, -0.4)
    panel_v("YoruW1", 2.0, -0.4, 0.8)
    panel_v("YoruW2", 2.0, 2.0, 3.4)
    panel_v("YoruE", 7.4, -0.4, 3.4)
    P("YoruFloor", 4.7, 1.5, 5.2, 3.6, 0.3, "wood", z0=0.06)
    P("YoruCurtainB", 4.7, 2.9, 3.6, 0.05, 1.7, "curtain", z0=0.7)
    for sx in (-1, 1):
        P("YoruCurtainS", 4.7 + sx * 1.8, 1.5, 0.05, 2.7, 1.7, "curtain", z0=0.7)
    P("YoruPillow", 6.2, 1.5, 0.55, 0.9, 0.28, "paper", z0=0.36)
    # 上御局（東端の2室）
    panel_x("FujiS1", 8.6, 10.4, -0.4)
    panel_x("FujiS2", 11.6, hu, -0.4)
    panel_v("FujiW", 8.6, -0.4, 3.4)
    panel_v("HagiW1", 8.6, 3.4, 5.2)
    panel_v("HagiW2", 8.6, 6.4, hv)
    tatami("FujiMat1", 10.2, 1.6)
    tatami("FujiMat2", 12.1, 1.6)
    kichou("FujiKichou", 11.0, 0.4)
    tatami("HagiMat", 11.2, 5.6)
    cabinet("HagiCabinet", 12.6, 6.9, 1.3, 0.7, 1.5)
    # 北廂の小部屋（西から鬼の間・台盤所・朝餉間・手水間・御湯殿上）
    for i, uu in enumerate((-8.5, -3.5, 1.5, 6.5)):
        panel_v("AislePart%d_a" % i, uu, 3.4, 5.2, h=2.2)
        panel_v("AislePart%d_b" % i, uu, 6.2, hv, h=2.2)
    cabinet("OniCabinet", -12.5, 5.6, 1.4, 0.7, 1.6)
    P("OniPainting", -hu + 0.15, 5.6, 0.08, 2.4, 1.9, "lacquer", z0=0.3)
    low_table("Daiban1", -7.0, 5.6)
    low_table("Daiban2", -4.9, 5.6)
    tatami("AsagareiMat", -1.0, 5.2)
    low_table("AsagareiTable", -1.0, 6.6)
    P("ChozuBasin", 4.0, 5.6, 0.75, 0.75, 0.55, "stone", z0=0.06)
    kichou("OyudonoKichou", 7.6, 5.6)
    # 昼御座まわり
    canopy_dais("Michodai", -10.3, 1.3, 3.4, 3.0)
    liondog("Shishi", -11.3, -0.95)
    liondog("Komainu", -9.3, -0.95)
    bench("Daisho1", -4.6, -0.7)
    bench("Daisho2", -4.6, 0.95)
    bench("Daisho3", -4.6, 2.6)
    cabinet("Zushi", -12.5, 2.3, 1.5, 0.75, 1.7)
    kichou("Kichou1", -8.1, -1.0)
    kichou("Kichou2", -12.5, -1.0)
    tatami("HiruMat1", -7.3, 1.0)
    tatami("HiruMat2", -7.3, 2.9)
    # 平敷の御座（南廂、御帳台の前）
    P("Hirashiki", -10.3, -5.0, 3.2, 2.2, 0.22, "wood", z0=0.06)
    tatami("HirashikiMat", -10.3, -5.0)
    # 殿上間（南廂）
    chair_isu("Goishi", -6.0, -5.6)
    for i, uu in enumerate((-2.0, 0.0, 2.0)):
        nameboard("Fuda%d" % i, uu, -7.2)
    kichou("TenjoKichou", 4.5, -5.4)
    for i, uu in enumerate((6.5, 8.5, 10.5)):
        tatami("TenjoMat%d" % i, uu, -5.4)
    finish("documented_interior")

# ---------------------------------------------------------------- 紫宸殿
def build_shishinden():
    fr = begin("DAIRI_SHISHINDEN", "DAIRI_SHISHINDEN", "INT_SHISHIN")
    hu, hv = fr["hu"], fr["hv"]
    # 賢聖障子（北壁の内側、9間のうち中央は扉）
    for i in range(9):
        uu = -14.4 + 3.2 * i + 1.6
        if i == 4:
            P("KenjoDoor", uu, hv - 0.35, 3.0, 0.12, 3.1, "lacquer", z0=0.06)
        else:
            P("KenjoFrame%d" % i, uu, hv - 0.35, 3.05, 0.1, 3.1, "wood", z0=0.06)
            P("KenjoPanel%d" % i, uu, hv - 0.42, 2.7, 0.05, 2.75, "paper", z0=0.22)
    takamikura("Takamikura", 0.0, 4.4, 1.0)
    takamikura("Michodai", 7.8, 4.4, 0.8)
    P("Runner", 0, -3.2, 2.3, 11.5, 0.05, "tatami", z0=0.06)
    kichou("Kichou1", -3.6, 0.6)
    kichou("Kichou2", 3.6, 0.6)
    finish("documented_interior")

# ---------------------------------------------------------------- 仁寿殿（模式）
def build_jijuden():
    fr = begin("DAIRI_JIJU_JOKYO", "DAIRI_JIJU_JOKYO", "INT_JIJU")
    hu, hv = fr["hu"], fr["hv"]
    panel_x("PartN1", -hu, -6.5, 3.2)
    panel_x("PartN2", -4.5, 3.5, 3.2)
    panel_x("PartN3", 5.5, hu, 3.2)
    panel_v("PartW", -4.0, 3.2, hv)
    panel_v("PartE", 5.0, 3.2, hv)
    canopy_dais("Michodai", -11.0, 0.9, 3.1, 2.7)
    tatami("Mat1", -7.0, 0.8)
    tatami("Mat2", -7.0, 2.6)
    tatami("Mat3", 0.5, 0.8)
    tatami("Mat4", 9.5, 5.4)
    kichou("Kichou1", -5.2, -0.6)
    kichou("Kichou2", 6.8, 0.6, rotz=0.5)
    cabinet("Cabinet", 12.5, 5.6, 1.5, 0.75, 1.7)
    low_table("Table", 0.5, 5.5)
    finish("schematic_interior")

# ---------------------------------------------------------------- 飛香舎（模式）
def build_higyosha():
    fr = begin("DAIRI_HIGYOSHA", "DAIRI_HIGYOSHA", "INT_HIGYO")
    hu, hv = fr["hu"], fr["hv"]
    panel_x("Part1", -hu, -3.2, 1.1, h=2.2)
    panel_x("Part2", 3.2, hu, 1.1, h=2.2)
    canopy_dais("Michodai", 0.0, 2.6, 2.9, 2.5)
    byobu("Byobu", -6.0, 1.8)
    kichou("Kichou1", 4.6, 0.4)
    kichou("Kichou2", -4.4, -1.6, rotz=-0.4)
    tatami("Mat1", 0.0, -2.2)
    tatami("Mat2", 2.0, -2.2)
    tatami("Mat3", -2.0, -2.2)
    cabinet("Cabinet", 8.6, 4.2, 1.4, 0.7, 1.6)
    low_table("Table", 5.8, -2.4)
    finish("schematic_interior")

build_seiryoden()
print("SEIRYO_DONE", flush=True)
build_shishinden()
print("SHISHIN_DONE", flush=True)
build_jijuden()
build_higyosha()
print("INTERIOR_DONE objects=%d" % len(col.objects), flush=True)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v11.blend")
print("SAVED_V11", flush=True)

# ---------------------------------------------------------------- 確認画像
scene = bpy.context.scene

def hide_roof(token):
    hidden = []
    for ob in bpy.data.objects:
        if token in ob.name and ("_Roof" in ob.name):
            ob.hide_render = True
            hidden.append(ob)
    return hidden

def setup_cam(loc, target, ortho=None, lens=30):
    cam_data = bpy.data.cameras.new("IntCam")
    cam_data.clip_start = 0.3
    cam_data.clip_end = 300.0
    if ortho:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho
    else:
        cam_data.lens = lens
    cam = bpy.data.objects.new("IntCam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

def render(path, rx, ry, samples):
    scene.cycles.samples = samples
    scene.render.resolution_x, scene.render.resolution_y = rx, ry
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)

OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v11"
fr = hall_frame("DAIRI_SEIRYODEN")
hide_roof("DAIRI_SEIRYODEN")
setup_cam((fr["cx"], fr["cy"], fr["fz"] + 55), (fr["cx"], fr["cy"], fr["fz"]), ortho=44)
render(OUT + "_seiryo_plan.png", 1150, 900, 24)
print("PLAN_DONE", flush=True)
setup_cam((fr["cx"] + 13.5, fr["cy"] - 6.5, fr["fz"] + 1.75),
          (fr["cx"] - 9.0, fr["cy"] + 2.5, fr["fz"] + 1.1), lens=27)
render(OUT + "_seiryo_room.png", 1280, 720, 48)
print("SEIRYO_ROOM_DONE", flush=True)

fr2 = hall_frame("DAIRI_SHISHINDEN")
hide_roof("DAIRI_SHISHINDEN")
setup_cam((fr2["cx"], fr2["cy"] - 13.5, fr2["fz"] + 1.9),
          (fr2["cx"] + 0.5, fr2["cy"] + 6.0, fr2["fz"] + 2.4), lens=29)
render(OUT + "_shishin_room.png", 1280, 720, 48)
print("SHISHIN_ROOM_DONE", flush=True)
