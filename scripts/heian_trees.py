# -*- coding: utf-8 -*-
"""樹木の手続き生成（植生レイヤー用の共通モジュール）

球や円柱の寄せ集めではなく、
- 幹と枝：分岐を繰り返す折れ線に沿った、先細りの管（樹皮の材質）
- 葉：1枚ずつの葉形の多角形（樹種ごとの形・大きさ・付き方）
で樹を組む。樹種ごとに数本の「原型」を作り、配置は原型コレクションのインスタンス
（Empty の instance_collection）で行う。原型はシーンに直接つながない専用コレクションに置くので、
何百本並べてもメッシュは原型の分しか持たない。

樹種（make_* 関数）：
- willow   柳（シダレヤナギ）。太い幹から弓なりの大枝、そこから細い枝が地面近くまで垂れる
- plum     梅。ジグザグに折れる古枝と、まっすぐ上へ伸びる若い枝（徒長枝）、まばらな葉
- tachibana 橘。低い位置で株立ちし、濃い緑の艶のある葉が密に茂る常緑の小高木。黄橙の実
- pine     松（クロマツ）。傾いて曲がる幹、水平に張る枝、枝先ごとの平たい葉の塊（針葉の束）
- broadleaf 落葉広葉樹（ケヤキ・エノキ風の模式）。低い位置で何本もの枝に分かれる扇形の樹冠

すべて乱数の種で決まり、同じ種なら同じ形になる。単位はメートル、原点は根元。
"""
import math
import random

import bpy
from mathutils import Vector, Matrix

UP = Vector((0, 0, 1))


# ---------------------------------------------------------------- 材質
def _mix_rgb(nt, fac_socket, c1, c2):
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    ins = [s for s in mx.inputs if s.type == "RGBA"]
    ins[0].default_value = (*c1, 1)
    ins[1].default_value = (*c2, 1)
    nt.links.new(fac_socket, mx.inputs[0])
    return [s for s in mx.outputs if s.type == "RGBA"][0]


def bark_material(name, c1, c2, scale=6.0, bump=0.6, stretch=0.35):
    """樹皮：縦に伸ばしたノイズとボロノイで、割れ目と色むらを付ける。"""
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*c1, 1)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.95
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 1.0, stretch)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 8.0
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    vo = nt.nodes.new("ShaderNodeTexVoronoi")
    vo.feature = "DISTANCE_TO_EDGE"
    vo.inputs["Scale"].default_value = scale * 2.2
    nt.links.new(mp.outputs["Vector"], vo.inputs["Vector"])
    col = _mix_rgb(nt, nz.outputs["Fac"], c1, c2)
    # 割れ目（ボロノイの縁）を暗く
    dark = nt.nodes.new("ShaderNodeMix")
    dark.data_type = "RGBA"
    dark.blend_type = "MULTIPLY"
    ins = [s for s in dark.inputs if s.type == "RGBA"]
    nt.links.new(col, ins[0])
    ins[1].default_value = (0.55, 0.52, 0.50, 1)
    cr = nt.nodes.new("ShaderNodeMapRange")
    cr.inputs["From Min"].default_value = 0.0
    cr.inputs["From Max"].default_value = 0.035
    cr.inputs["To Min"].default_value = 1.0
    cr.inputs["To Max"].default_value = 0.0
    nt.links.new(vo.outputs["Distance"], cr.inputs["Value"])
    nt.links.new(cr.outputs["Result"], dark.inputs[0])
    nt.links.new([s for s in dark.outputs if s.type == "RGBA"][0], b.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.02
    nt.links.new(vo.outputs["Distance"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def leaf_material(name, colors, rough=0.55, trans=0.22, spec=0.4):
    """葉：1枚ごと（島ごと）の乱数で色を散らし、裏から透ける光を少し混ぜる。"""
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*colors[0], 1)
    m.use_nodes = True
    nt = m.node_tree
    out = nt.nodes["Material Output"]
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough
    if "Specular IOR Level" in b.inputs:
        b.inputs["Specular IOR Level"].default_value = spec
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position = 0.0
    els[0].color = (*colors[0], 1)
    els[1].position = 1.0
    els[1].color = (*colors[-1], 1)
    for i, c in enumerate(colors[1:-1], 1):
        e = els.new(i / (len(colors) - 1))
        e.color = (*c, 1)
    nt.links.new(geo.outputs["Random Per Island"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    hsv = nt.nodes.new("ShaderNodeHueSaturation")
    hsv.inputs["Value"].default_value = 1.3
    hsv.inputs["Saturation"].default_value = 1.2
    nt.links.new(ramp.outputs["Color"], hsv.inputs["Color"])
    nt.links.new(hsv.outputs["Color"], tr.inputs["Color"])
    ms = nt.nodes.new("ShaderNodeMixShader")
    ms.inputs[0].default_value = trans
    nt.links.new(b.outputs[0], ms.inputs[1])
    nt.links.new(tr.outputs[0], ms.inputs[2])
    nt.links.new(ms.outputs[0], out.inputs["Surface"])
    return m


def plain_material(name, color, rough=0.5):
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    return m


# ---------------------------------------------------------------- 形の組み立て
class Geo:
    """材質ごとの頂点・面の入れ物。最後に1つのメッシュにまとめる。"""

    def __init__(self):
        self.V = []
        self.F = []
        self.Fm = []   # 面ごとの材質番号

    def tube(self, pts, rads, sides, mi=0):
        if len(pts) < 2:
            return
        base = len(self.V)
        n_prev = None
        npts = len(pts)
        for i, p in enumerate(pts):
            t = (pts[min(i + 1, npts - 1)] - pts[max(i - 1, 0)])
            if t.length < 1e-9:
                t = UP.copy()
            t.normalize()
            if n_prev is None:
                a = UP if abs(t.z) < 0.9 else Vector((1, 0, 0))
                n = t.cross(a).normalized()
            else:
                n = n_prev - t * n_prev.dot(t)
                if n.length < 1e-6:
                    n = t.orthogonal()
                n.normalize()
            bvec = t.cross(n)
            n_prev = n
            r = rads[i]
            for k in range(sides):
                ang = 2 * math.pi * k / sides
                self.V.append(tuple(p + (n * math.cos(ang) + bvec * math.sin(ang)) * r))
        for i in range(npts - 1):
            for k in range(sides):
                k2 = (k + 1) % sides
                self.F.append((base + i * sides + k, base + i * sides + k2,
                               base + (i + 1) * sides + k2, base + (i + 1) * sides + k))
                self.Fm.append(mi)
        # 先端を閉じる
        last = base + (npts - 1) * sides
        self.F.append(tuple(last + k for k in range(sides)))
        self.Fm.append(mi)

    def poly(self, verts, mi):
        base = len(self.V)
        self.V.extend(tuple(v) for v in verts)
        self.F.append(tuple(range(base, base + len(verts))))
        self.Fm.append(mi)

    def leaf(self, p, d, nrm, length, width, shape, mi, fold=0.0):
        """葉1枚。p＝付け根、d＝葉先の向き、nrm＝葉の表の向き。shape は輪郭の (y, 半幅) 列。
        fold>0 なら中央脈で少し折る（立体感）。"""
        d = d.normalized()
        s = d.cross(nrm)
        if s.length < 1e-6:
            s = d.orthogonal()
        s.normalize()
        n = s.cross(d)
        right = []
        left = []
        for (yy, hw) in shape:
            c = p + d * (yy * length)
            right.append(c + s * (hw * width) - n * (fold * hw * width))
            left.append(c - s * (hw * width) - n * (fold * hw * width))
        # 中央の脈（付け根と先端は輪郭の端点と共有）
        outline = [right[0]] + right[1:-1] + [right[-1]] + list(reversed(left[1:-1]))
        self.poly(outline, mi)

    def sphere(self, c, r, mi, seg=6, ring=4):
        base = len(self.V)
        self.V.append(tuple(c + Vector((0, 0, -r))))
        for j in range(1, ring):
            phi = math.pi * j / ring - math.pi / 2
            for k in range(seg):
                th = 2 * math.pi * k / seg
                self.V.append(tuple(c + Vector((math.cos(phi) * math.cos(th), math.cos(phi) * math.sin(th),
                                                 math.sin(phi))) * r))
        self.V.append(tuple(c + Vector((0, 0, r))))
        top = len(self.V) - 1
        for k in range(seg):
            k2 = (k + 1) % seg
            self.F.append((base, base + 1 + k2, base + 1 + k))
            self.Fm.append(mi)
            for j in range(ring - 2):
                a = base + 1 + j * seg
                self.F.append((a + k, a + k2, a + seg + k2, a + seg + k))
                self.Fm.append(mi)
            a = base + 1 + (ring - 2) * seg
            self.F.append((a + k, a + k2, top))
            self.Fm.append(mi)

    def to_mesh(self, name, mats):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.V, [], self.F)
        me.update()
        for m in mats:
            me.materials.append(m)
        me.polygons.foreach_set("material_index", self.Fm)
        me.polygons.foreach_set("use_smooth", [True] * len(self.Fm))
        me.update()
        return me


def rot_about(v, axis, ang):
    return Matrix.Rotation(ang, 3, axis.normalized()) @ v


def deviate(d, ang, rng, azimuth=None):
    """向き d から角度 ang だけ傾けた向き（方位は乱数）。"""
    perp = d.orthogonal().normalized()
    perp = rot_about(perp, d, rng.uniform(0, 2 * math.pi) if azimuth is None else azimuth)
    return rot_about(d, perp, ang).normalized()


def grow_branch(g, rng, p0, d0, length, r0, sp, level, ends, mi_wood=0):
    """1本の枝を折れ線で伸ばし、子の枝を再帰で出す。sp は段ごとの設定の列。
    末端の枝は (点列, 向き列) を ends に足す（葉を付ける場所）。"""
    L = sp[level]
    nseg = max(2, int(length / L.get("seg", 0.5)))
    pts = [p0.copy()]
    dirs = [d0.copy()]
    d = d0.copy()
    for i in range(1, nseg + 1):
        jit = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))) * L.get("wobble", 0.1)
        d = (d + jit + UP * L.get("up", 0.0)).normalized()
        if L.get("kink") and rng.random() < L["kink"]:          # ジグザグ（梅）
            d = deviate(d, math.radians(rng.uniform(25, 45)), rng)
        pts.append(pts[-1] + d * (length / nseg))
        dirs.append(d.copy())
    taper = L.get("taper", 0.7)
    rads = [max(r0 * (1 - taper * i / nseg), L.get("rmin", 0.004)) for i in range(nseg + 1)]
    sides = L.get("sides", 6)
    g.tube(pts, rads, sides, mi_wood)
    if level + 1 >= len(sp):
        ends.append((pts, dirs, level))
        return
    C = sp[level + 1]
    nchild = C.get("n", 3)
    if isinstance(nchild, tuple):
        nchild = rng.randint(*nchild)
    lo, hi = C.get("at", (0.3, 1.0))
    az0 = rng.uniform(0, 2 * math.pi)
    for c in range(nchild):
        t = lo + (hi - lo) * (c + rng.uniform(0.2, 0.8)) / nchild
        fi = t * nseg
        i = min(int(fi), nseg - 1)
        f = fi - i
        p = pts[i].lerp(pts[i + 1], f)
        dd = dirs[i + 1]
        r_here = rads[i] * (1 - f) + rads[i + 1] * f
        ang = math.radians(C.get("angle", 45) + rng.uniform(-1, 1) * C.get("angle_var", 10))
        az = az0 + c * 2.39996 + rng.uniform(-0.4, 0.4)       # 黄金角で回す
        cd = deviate(dd, ang, rng, azimuth=az)
        if "flat" in C:                                         # 水平に近づける（松）
            cd = (cd + Vector((0, 0, -cd.z)) * C["flat"]).normalized()
        cl = length * C.get("len", 0.6) * (1 - C.get("len_t", 0.4) * t) * rng.uniform(0.8, 1.2)
        cr = min(r_here * C.get("rad", 0.7), r_here)
        grow_branch(g, rng, p, cd, cl, cr, sp, level + 1, ends, mi_wood)
    # 枝の先も末端として扱う（先端に葉を付けるため）
    if C.get("tip_leaves", True):
        ends.append((pts[int(nseg * 0.6):], dirs[int(nseg * 0.6):], level))


def leaves_along(g, rng, ends, spec, mi):
    """末端の枝に沿って葉を付ける。spec: per_m（1mあたり枚数）、size（長さ, 幅）、shape、
    spread（枝からの離れ）、droop（葉先の下がり）、up（表が上を向く度合い）、fold、
    from_t（枝のどこから付けるか 0〜1）、only_last（最終段の枝だけ）。"""
    n = 0
    maxlv = max(e[2] for e in ends) if ends else 0
    for pts, dirs, lv in ends:
        if spec.get("only_last") and lv != maxlv:
            continue
        seglen = sum((pts[i + 1] - pts[i]).length for i in range(len(pts) - 1))
        cnt = int(seglen * spec["per_m"] * rng.uniform(0.8, 1.2))
        from_t = spec.get("from_t", 0.0)
        for _ in range(cnt):
            t = rng.uniform(from_t, 1.0)
            fi = t * (len(pts) - 1)
            i = min(int(fi), len(pts) - 2)
            p = pts[i].lerp(pts[i + 1], fi - i)
            bd = dirs[i + 1]
            off = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))) * spec.get("spread", 0.08)
            p = p + off
            d = (bd * spec.get("follow", 0.4) + deviate(bd, math.radians(rng.uniform(40, 80)), rng)
                 - UP * spec.get("droop", 0.3)).normalized()
            nrm = (UP * spec.get("up", 1.0) + Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))) * 0.5)
            ln, wd = spec["size"]
            sc = rng.uniform(0.75, 1.25)
            g.leaf(p, d, nrm, ln * sc, wd * sc, spec["shape"], mi, spec.get("fold", 0.15))
            n += 1
    return n


# 葉の輪郭（y：付け根0→先端1、半幅）
SHAPE_OVATE = [(0, 0), (0.15, 0.32), (0.4, 0.5), (0.7, 0.36), (1.0, 0)]          # 卵形（ケヤキ・梅）
SHAPE_ELLIPSE = [(0, 0), (0.12, 0.3), (0.45, 0.5), (0.8, 0.35), (1.0, 0)]        # 楕円（橘）
SHAPE_LANCE = [(0, 0), (0.1, 0.35), (0.35, 0.5), (0.7, 0.3), (1.0, 0)]           # 披針形（柳）
SHAPE_NEEDLE = [(0, 0), (0.05, 0.5), (0.9, 0.4), (1.0, 0)]                       # 針葉の束


# ---------------------------------------------------------------- 樹種
def _mats():
    return {
        "bark": bark_material("MAT_TreeBark", (0.13, 0.11, 0.09), (0.22, 0.19, 0.16)),
        "bark_willow": bark_material("MAT_TreeBarkWillow", (0.10, 0.09, 0.075), (0.19, 0.17, 0.14),
                                     scale=9.0, stretch=0.2),
        "bark_plum": bark_material("MAT_TreeBarkPlum", (0.07, 0.055, 0.05), (0.15, 0.12, 0.10),
                                   scale=7.0, bump=0.9),
        "bark_pine": bark_material("MAT_TreeBarkPine", (0.13, 0.09, 0.07), (0.24, 0.19, 0.16),
                                   scale=4.0, bump=1.0, stretch=0.6),
        "bark_zelkova": bark_material("MAT_TreeBarkZelkova", (0.17, 0.155, 0.135), (0.27, 0.25, 0.22),
                                      scale=5.0, bump=0.5),
        "leaf_willow": leaf_material("MAT_TreeLeafWillow",
                                     [(0.20, 0.32, 0.07), (0.30, 0.42, 0.10), (0.40, 0.50, 0.16)],
                                     rough=0.6, trans=0.3),
        "leaf_plum": leaf_material("MAT_TreeLeafPlum",
                                   [(0.10, 0.20, 0.05), (0.16, 0.27, 0.07), (0.22, 0.31, 0.09)]),
        "leaf_tachi": leaf_material("MAT_TreeLeafTachibana",
                                    [(0.035, 0.10, 0.03), (0.055, 0.15, 0.045), (0.09, 0.20, 0.06)],
                                    rough=0.3, trans=0.12, spec=0.6),
        "fruit": plain_material("MAT_TreeTachibanaFruit", (0.85, 0.45, 0.04), 0.4),
        "leaf_pine": leaf_material("MAT_TreeNeedlePine",
                                   [(0.035, 0.08, 0.035), (0.05, 0.11, 0.045), (0.075, 0.14, 0.055)],
                                   rough=0.5, trans=0.1),
        "leaf_broad": leaf_material("MAT_TreeLeafBroad",
                                    [(0.09, 0.19, 0.045), (0.14, 0.25, 0.06), (0.21, 0.31, 0.08)]),
        "leaf_hedge": leaf_material("MAT_TreeLeafHedge",
                                    [(0.03, 0.075, 0.025), (0.05, 0.11, 0.035), (0.075, 0.14, 0.045)],
                                    rough=0.45, trans=0.08, spec=0.4),
        "hedge_core": plain_material("MAT_TreeHedgeCore", (0.015, 0.03, 0.01), 0.9),
        "leaf_broad2": leaf_material("MAT_TreeLeafBroad2",
                                     [(0.13, 0.22, 0.05), (0.20, 0.30, 0.07), (0.28, 0.35, 0.10)]),
    }


def make_willow(seed, height=10.0):
    """柳：幹（高さ約2.5〜3m）から4〜6本の大枝が弓なりに斜め上へ。大枝・中枝の上側から
    細い枝が出て、いったん外へ張ったのち真下へ垂れ、地上1〜2mまで届く。葉は細長い披針形。"""
    M = _mats()
    rng = random.Random(seed)
    g = Geo()
    trunk_h = rng.uniform(2.4, 3.2)
    # 幹：わずかに傾けて曲げる
    tpts = []
    lean = deviate(UP, math.radians(rng.uniform(3, 9)), rng)
    for i in range(7):
        t = i / 6
        tpts.append(lean * (trunk_h * t) + Vector((math.sin(t * 2.5) * 0.12, 0, 0)))
    g.tube(tpts, [0.36 * (1 - 0.35 * i / 6) + (0.12 if i == 0 else 0) for i in range(7)], 10, 0)
    top = tpts[-1]
    sp = [
        dict(seg=0.5, wobble=0.06, up=0.03, taper=0.7, sides=8),                 # 大枝
        dict(n=(3, 4), at=(0.3, 0.95), angle=40, angle_var=12, len=0.55, rad=0.55, seg=0.4,
             wobble=0.08, up=0.02, taper=0.8, sides=5, tip_leaves=False),        # 中枝
    ]
    ends = []
    nl = rng.randint(4, 6)
    for k in range(nl):
        az = 2 * math.pi * k / nl + rng.uniform(-0.3, 0.3)
        d = Vector((math.cos(az) * 0.75, math.sin(az) * 0.75, 1.0)).normalized()
        grow_branch(g, rng, top, d, rng.uniform(height - trunk_h - 2.5, height - trunk_h - 1.0),
                    0.2, sp, 0, ends)
    # 垂れる枝：中枝・大枝の上半分から、外へ張って垂れ下がる細い枝
    n_leaf = 0
    strands = 0
    for pts, dirs, lv in ends:
        for i in range(1, len(pts)):
            for _ in range(rng.randint(5, 7)):
                p = pts[i - 1].lerp(pts[i], rng.random())
                if p.z < trunk_h + 1.0:
                    continue
                out = Vector((p.x, p.y, 0))
                out = out.normalized() if out.length > 1e-3 else deviate(UP, 1.5, rng)
                d = (out * 0.8 + UP * rng.uniform(0.2, 0.6)
                     + Vector((rng.gauss(0, 0.3), rng.gauss(0, 0.3), 0))).normalized()
                bottom = rng.uniform(0.9, 2.2)
                spts = [p.copy()]
                step = 0.2
                while spts[-1].z > bottom and len(spts) < 80:
                    d = (d - UP * 0.22).normalized()
                    d.z = max(d.z, -0.995)
                    d = (d + Vector((rng.gauss(0, 0.04), rng.gauss(0, 0.04), 0))).normalized()
                    spts.append(spts[-1] + d * step)
                if len(spts) < 4:
                    continue
                g.tube(spts, [0.012 * (1 - 0.6 * j / len(spts)) for j in range(len(spts))], 3, 0)
                strands += 1
                # 葉：枝に沿って互い違いに、斜め下へ
                total = (len(spts) - 1) * step
                cnt = int(total / 0.055)
                for j in range(cnt):
                    t = j / max(cnt - 1, 1)
                    fi = t * (len(spts) - 1)
                    a = min(int(fi), len(spts) - 2)
                    q = spts[a].lerp(spts[a + 1], fi - a)
                    sd = (spts[a + 1] - spts[a]).normalized()
                    side = deviate(sd, math.radians(90), rng, azimuth=j * 2.4)
                    ld = (sd * 0.75 + side * 0.55).normalized()
                    nrm = side.cross(sd) + UP * 0.3
                    sc = rng.uniform(0.8, 1.15)
                    g.leaf(q, ld, nrm, 0.18 * sc, 0.036 * sc, SHAPE_LANCE, 1, 0.1)
                    n_leaf += 1
    me = g.to_mesh("TreeProto_Willow_%d" % seed, [M["bark_willow"], M["leaf_willow"]])
    return me, dict(leaves=n_leaf, strands=strands)


def make_plum(seed):
    """梅：根元から低く2〜3本に分かれ、古枝はジグザグに折れながら横へ広がる。
    枝の上からまっすぐ上に伸びる若い枝（徒長枝）が目立つ。葉は小さな卵形でまばら。高さ約4m。"""
    M = _mats()
    rng = random.Random(seed)
    g = Geo()
    sp = [
        dict(seg=0.25, wobble=0.22, up=0.02, taper=0.55, sides=9, kink=0.25),
        dict(n=(3, 4), at=(0.35, 1.0), angle=48, angle_var=15, len=0.75, rad=0.6, seg=0.22, wobble=0.2,
             up=0.0, taper=0.7, sides=6, kink=0.3),
        dict(n=(3, 5), at=(0.2, 1.0), angle=50, angle_var=15, len=0.6, rad=0.55, seg=0.18, wobble=0.15,
             up=0.05, taper=0.8, sides=4, kink=0.2),
        dict(n=(2, 4), at=(0.2, 1.0), angle=45, angle_var=15, len=0.5, rad=0.6, seg=0.12, wobble=0.1,
             up=0.1, taper=0.8, sides=3),
    ]
    ends = []
    for k in range(rng.randint(2, 3)):
        d = deviate(UP, math.radians(rng.uniform(15, 30)), rng, azimuth=k * 2.3 + rng.uniform(0, 1))
        grow_branch(g, rng, Vector((0, 0, 0)), d, rng.uniform(2.4, 3.0), 0.18, sp, 0, ends)
    # 徒長枝：古枝の上から、ほぼ垂直に細くまっすぐ
    shoots = []
    for pts, dirs, lv in list(ends):
        if lv < 1:
            continue
        for _ in range(0):
            p = pts[rng.randrange(len(pts))]
            L = rng.uniform(0.8, 1.5)
            d = deviate(UP, math.radians(rng.uniform(0, 12)), rng)
            spts = [p + d * (L * i / 5) for i in range(6)]
            g.tube(spts, [0.012 * (1 - 0.6 * i / 5) for i in range(6)], 4, 0)
            shoots.append((spts, [d] * 6, 3))
    n = leaves_along(g, rng, ends + shoots,
                     dict(per_m=60, size=(0.09, 0.055), shape=SHAPE_OVATE, spread=0.07, droop=0.35,
                          follow=0.3, up=0.9, from_t=0.1), 1)
    me = g.to_mesh("TreeProto_Plum_%d" % seed, [M["bark_plum"], M["leaf_plum"]])
    return me, dict(leaves=n)


def make_tachibana(seed):
    """橘：根元近くで4〜5本の幹に分かれる株立ち。細かい枝が多く、楕円形の艶のある濃緑の葉が
    密に付いて、丸い樹冠になる。実（径約3cm）が葉の間に見える。高さ約3.5m。"""
    M = _mats()
    rng = random.Random(seed)
    g = Geo()
    sp = [
        dict(seg=0.25, wobble=0.1, up=0.05, taper=0.6, sides=7),
        dict(n=(5, 6), at=(0.2, 1.0), angle=45, angle_var=12, len=0.75, rad=0.6, seg=0.2, wobble=0.12,
             up=0.04, taper=0.7, sides=5),
        dict(n=(4, 6), at=(0.2, 1.0), angle=48, angle_var=12, len=0.55, rad=0.6, seg=0.15, wobble=0.12,
             up=0.06, taper=0.8, sides=3),
    ]
    ends = []
    for k in range(rng.randint(4, 5)):
        d = deviate(UP, math.radians(rng.uniform(12, 30)), rng, azimuth=k * 1.4 + rng.uniform(0, 0.5))
        p0 = Vector((rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), 0))
        grow_branch(g, rng, p0, d, rng.uniform(1.3, 1.7), 0.075, sp, 0, ends)
    n = leaves_along(g, rng, ends,
                     dict(per_m=110, size=(0.11, 0.055), shape=SHAPE_ELLIPSE, spread=0.09, droop=0.15,
                          follow=0.35, up=1.0, from_t=0.0, fold=0.25), 1)
    # 実：樹冠の外側寄りの末端枝のそばに
    nf = 0
    for pts, dirs, lv in ends:
        if rng.random() < 0.35:
            p = pts[-1] + Vector((rng.gauss(0, 0.05), rng.gauss(0, 0.05), -0.06))
            g.sphere(p, 0.022, 2)
            nf += 1
    me = g.to_mesh("TreeProto_Tachibana_%d" % seed, [M["bark_plum"], M["leaf_tachi"], M["fruit"]])
    return me, dict(leaves=n, fruits=nf)


def make_pine(seed, height=8.0):
    """松（クロマツ）：根元から傾いて曲がる幹。幹の上半分から、ほぼ水平に張る枝が段をなし、
    枝先が少し上を向く。葉は枝先ごとに平たい塊になり、上面に針葉の束が密に立つ（庭の松の姿）。"""
    M = _mats()
    rng = random.Random(seed)
    g = Geo()
    # 幹：傾き＋S字
    lean_az = rng.uniform(0, 2 * math.pi)
    lean = math.radians(rng.uniform(14, 28))
    tpts = []
    n = 12
    for i in range(n + 1):
        t = i / n
        off = math.sin(t * math.pi * 1.3) * 0.5 * math.sin(lean) * height * 0.25
        x = (t * height * math.sin(lean) * 0.6 + off)
        tpts.append(Vector((x * math.cos(lean_az), x * math.sin(lean_az), t * height * 0.92)))
    trad = [0.28 * (1 - 0.75 * i / n) + (0.08 if i == 0 else 0) for i in range(n + 1)]
    g.tube(tpts, trad, 10, 0)
    sp = [
        dict(seg=0.35, wobble=0.12, up=-0.02, taper=0.7, sides=6),
        dict(n=(3, 4), at=(0.3, 1.0), angle=40, angle_var=15, len=0.55, rad=0.6, seg=0.3,
             wobble=0.12, up=0.08, taper=0.8, sides=4, flat=0.6, tip_leaves=False),
    ]
    ends = []
    # 段になった枝（幹の 35%〜95%）
    nb = rng.randint(9, 12)
    for k in range(nb):
        t = 0.35 + 0.6 * k / (nb - 1)
        fi = t * n
        i = min(int(fi), n - 1)
        p = tpts[i].lerp(tpts[i + 1], fi - i)
        az = k * 2.39996 + rng.uniform(-0.3, 0.3)
        d = Vector((math.cos(az), math.sin(az), rng.uniform(-0.15, 0.2))).normalized()
        L = (height * 0.5) * (1.1 - 0.75 * t) * rng.uniform(0.8, 1.2)
        grow_branch(g, rng, p, d, L, trad[i] * 0.45, sp, 0, ends)
    ends.append((tpts[-3:], [UP] * 3, 1))
    # 葉の塊：末端枝の先に平たい楕円の塊。上面に針葉の束を上向きに
    nn = 0
    pads = 0
    for pts, dirs, lv in ends:
        tip = pts[-1]
        rx = rng.uniform(0.7, 1.15)
        rz = rx * 0.38
        cnt = int(rx * rx * 900)
        for _ in range(cnt):
            a = rng.uniform(0, 2 * math.pi)
            rr = math.sqrt(rng.random()) * rx
            hz = (1 - (rr / rx) ** 2) ** 0.5 * rz
            p = tip + Vector((math.cos(a) * rr, math.sin(a) * rr, rng.uniform(-0.6, 1.0) * hz))
            d = (UP * 0.8 + Vector((math.cos(a), math.sin(a), 0)) * (rr / rx) * 0.8
                 + Vector((rng.gauss(0, 0.25), rng.gauss(0, 0.25), 0))).normalized()
            nrm = deviate(d, math.radians(90), rng)
            g.leaf(p, d, nrm, rng.uniform(0.14, 0.22), 0.022, SHAPE_NEEDLE, 1, 0.0)
            nn += 1
        pads += 1
    me = g.to_mesh("TreeProto_Pine_%d" % seed, [M["bark_pine"], M["leaf_pine"]])
    return me, dict(needles=nn, pads=pads)


def make_broadleaf(seed, height=10.0, leafmat="leaf_broad"):
    """落葉広葉樹（ケヤキ・エノキ風の模式）：幹は2.5〜3.5mで何本もの太い枝に分かれ、斜め上へ
    扇形に広がる。細かい枝の先に卵形の葉が房になって付き、外周が丸くまとまる。"""
    M = _mats()
    rng = random.Random(seed)
    g = Geo()
    th = rng.uniform(1.8, 2.6)
    bx, by = rng.gauss(0, 0.08), rng.gauss(0, 0.08)
    tpts = [Vector((bx * math.sin(i / 5 * 2.0), by * math.sin(i / 5 * 2.0), th * i / 5)) for i in range(6)]
    g.tube(tpts, [0.32 * (1 - 0.3 * i / 5) + (0.1 if i == 0 else 0) for i in range(6)], 10, 0)
    top = tpts[-1]
    sp = [
        dict(seg=0.5, wobble=0.07, up=0.05, taper=0.65, sides=7),
        dict(n=(4, 5), at=(0.25, 1.0), angle=38, angle_var=10, len=0.6, rad=0.6, seg=0.35, wobble=0.1,
             up=0.02, taper=0.7, sides=5),
        dict(n=(5, 6), at=(0.2, 1.0), angle=45, angle_var=12, len=0.5, rad=0.6, seg=0.25, wobble=0.12,
             up=0.0, taper=0.8, sides=3),
    ]
    ends = []
    nl = rng.randint(6, 8)
    for k in range(nl):
        az = 2 * math.pi * k / nl + rng.uniform(-0.3, 0.3)
        ang = math.radians(rng.uniform(28, 50))
        d = Vector((math.cos(az) * math.sin(ang), math.sin(az) * math.sin(ang), math.cos(ang)))
        grow_branch(g, rng, top, d, rng.uniform(height - th - 2.5, height - th - 1.0), 0.18, sp, 0, ends)
    n = leaves_along(g, rng, ends,
                     dict(per_m=80, size=(0.2, 0.1), shape=SHAPE_OVATE, spread=0.25, droop=0.25,
                          follow=0.35, up=1.0, from_t=0.2, only_last=False), 1)
    me = g.to_mesh("TreeProto_Broad_%d" % seed, [M["bark_zelkova"], M[leafmat]])
    return me, dict(leaves=n)


def make_hedge(seed, length=10.0, width=1.2, height=1.05):
    """生垣（長さ10mの一区画）：中は暗い芯、表面に小さな葉を密に。上面と側面を少し波打たせる。"""
    M = _mats()
    rng = random.Random(seed)
    g = Geo()
    hw, hl = width / 2 * 0.85, length / 2
    hz = height * 0.92
    g.poly([(-hl, -hw, 0.05), (hl, -hw, 0.05), (hl, -hw, hz), (-hl, -hw, hz)], 2)
    g.poly([(hl, hw, 0.05), (-hl, hw, 0.05), (-hl, hw, hz), (hl, hw, hz)], 2)
    g.poly([(-hl, -hw, hz), (hl, -hw, hz), (hl, hw, hz), (-hl, hw, hz)], 2)
    n = 0
    area = length * (2 * height + width)
    for _ in range(int(area * 420)):
        u = rng.random() * (2 * height + width)
        x = rng.uniform(-hl, hl)
        wav = 0.06 * math.sin(x * 2.1 + seed) + 0.04 * math.sin(x * 5.3)
        if u < height:                       # 南の側面
            p = Vector((x, -width / 2 - wav, u * (1 + wav)))
            nrm = Vector((0, -1, 0.3))
        elif u < 2 * height:                 # 北の側面
            p = Vector((x, width / 2 + wav, (u - height) * (1 + wav)))
            nrm = Vector((0, 1, 0.3))
        else:                                # 上面
            p = Vector((x, u - 2 * height - width / 2, height + wav))
            nrm = UP.copy()
        p += Vector((rng.gauss(0, 0.04), rng.gauss(0, 0.04), rng.gauss(0, 0.04)))
        nrm = (nrm + Vector((rng.gauss(0, 0.5), rng.gauss(0, 0.5), rng.gauss(0, 0.5)))).normalized()
        d = deviate(nrm, math.radians(90), rng)
        sc = rng.uniform(0.8, 1.2)
        g.leaf(p, d, nrm, 0.07 * sc, 0.038 * sc, SHAPE_ELLIPSE, 1, 0.2)
        n += 1
    me = g.to_mesh("TreeProto_Hedge_%d" % seed, [M["bark"], M["leaf_hedge"], M["hedge_core"]])
    return me, dict(leaves=n)


# ---------------------------------------------------------------- 原型コレクションと配置
_protos = {}


def proto(kind, variant, parent_col_name="COL_92_TreeProtos"):
    """樹種 kind の原型（variant 番号）を作るか、作ってあれば返す。返すのはコレクション。"""
    key = (kind, variant)
    if key in _protos:
        return _protos[key]
    root = bpy.data.collections.get(parent_col_name)
    if root is None:
        root = bpy.data.collections.new(parent_col_name)
        root.use_fake_user = True
    cname = "PROTO_%s_%d" % (kind, variant)
    old = bpy.data.collections.get(cname)
    if old is not None:
        for ob in list(old.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.collections.remove(old)
    col = bpy.data.collections.new(cname)
    root.children.link(col)
    seed = 1000 + variant * 17
    if kind == "willow":
        me, info = make_willow(seed)
    elif kind == "plum":
        me, info = make_plum(seed)
    elif kind == "tachibana":
        me, info = make_tachibana(seed)
    elif kind == "pine":
        me, info = make_pine(seed, height=7.5 + variant * 0.7)
    elif kind == "hedge":
        me, info = make_hedge(seed)
    elif kind == "broadleaf":
        me, info = make_broadleaf(seed, height=9.0 + variant * 0.8,
                                  leafmat="leaf_broad2" if variant % 2 else "leaf_broad")
    else:
        raise ValueError(kind)
    ob = bpy.data.objects.new(cname + "_Mesh", me)
    col.objects.link(ob)
    info["verts"] = len(me.vertices)
    print("TREE_PROTO", cname, info, flush=True)
    _protos[key] = col
    return col


def place(kind, variant, name, loc, rot_z, scale, col):
    """原型のインスタンス（Empty）を置く。"""
    pc = proto(kind, variant)
    em = bpy.data.objects.new(name, None)
    em.instance_type = "COLLECTION"
    em.instance_collection = pc
    em.location = loc
    em.rotation_euler = (0, 0, rot_z)
    em.scale = (scale, scale, scale)
    em.empty_display_size = 2.0
    col.objects.link(em)
    return em
