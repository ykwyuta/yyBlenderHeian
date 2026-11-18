"""フェーズ6適用：v5モデルのマテリアルと照明を作り替え、v6として保存する。
build_chodoin_detailed.py の make_mat / setup_sky と同じパラメータ。
（緑釉瓦と白壁は描画確認後に調整した最終値を反映済み。調整の経緯は
07_building-parts.md §8 を参照）"""
import bpy
from mathutils import Vector

PARAMS = {
    "MAT_Vermilion":    dict(color=(0.60, 0.10, 0.05), rough=0.55, color2=(0.48, 0.07, 0.035), scale=0.6, bump=0.05),
    "MAT_WhiteWall":    dict(color=(0.93, 0.91, 0.85), rough=0.95, color2=(0.88, 0.86, 0.79), scale=0.22, bump=0.05),
    "MAT_RoofTile":     dict(color=(0.24, 0.26, 0.30), rough=0.8, color2=(0.15, 0.16, 0.19), scale=0.9, bump=0.35),
    "MAT_RoofGreenGlaze": dict(color=(0.06, 0.22, 0.17), rough=0.55, color2=(0.04, 0.15, 0.12), scale=0.9, bump=0.2),
    "MAT_Stone":        dict(color=(0.56, 0.54, 0.50), rough=0.95, color2=(0.40, 0.39, 0.36), scale=0.7, bump=0.4),
    "MAT_WoodDark":     dict(color=(0.32, 0.21, 0.12), rough=0.8, color2=(0.20, 0.12, 0.06), scale=1.1, bump=0.08),
    "MAT_Gold":         dict(color=(0.83, 0.62, 0.18), rough=0.32, metallic=1.0),
    "MAT_SandGround":   dict(color=(0.85, 0.80, 0.68), rough=1.0, color2=(0.72, 0.66, 0.53), scale=0.05, bump=0.04),
    "MAT_EarthGround":  dict(color=(0.74, 0.69, 0.57), rough=1.0, color2=(0.58, 0.53, 0.42), scale=0.05, bump=0.04),
    "MAT_PineGreen":    dict(color=(0.15, 0.30, 0.14), rough=1.0, color2=(0.08, 0.19, 0.08), scale=1.4, bump=0.0),
    "MAT_TrunkBrown":   dict(color=(0.34, 0.23, 0.14), rough=1.0, color2=(0.22, 0.14, 0.08), scale=1.2, bump=0.0),
    "MAT_RoadGravel":   dict(color=(0.79, 0.76, 0.69), rough=1.0, color2=(0.62, 0.59, 0.52), scale=1.6, bump=0.15),
}


def rebuild_mat(mat, p):
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    color = p["color"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = p["rough"]
    if p.get("metallic"):
        bsdf.inputs["Metallic"].default_value = p["metallic"]
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    if p.get("color2") is not None and p.get("scale"):
        coord = nt.nodes.new("ShaderNodeTexCoord")
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = p["scale"]
        noise.inputs["Detail"].default_value = 2.5
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.25
        ramp.color_ramp.elements[0].color = (*p["color2"], 1.0)
        ramp.color_ramp.elements[1].position = 0.75
        ramp.color_ramp.elements[1].color = (*color, 1.0)
        nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        if p.get("bump"):
            bnode = nt.nodes.new("ShaderNodeBump")
            bnode.inputs["Strength"].default_value = p["bump"]
            bnode.inputs["Distance"].default_value = 0.12
            nt.links.new(noise.outputs["Fac"], bnode.inputs["Height"])
            nt.links.new(bnode.outputs["Normal"], bsdf.inputs["Normal"])


def setup_sky(world):
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 1.1
    mix = nt.nodes.new("ShaderNodeMixRGB")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    rng = nt.nodes.new("ShaderNodeMapRange")
    rng.inputs["From Min"].default_value = 0.45
    rng.inputs["From Max"].default_value = 0.8
    rng.inputs["To Min"].default_value = 0.0
    rng.inputs["To Max"].default_value = 1.0
    rng.clamp = True
    mix.inputs[1].default_value = (0.90, 0.89, 0.84, 1.0)
    mix.inputs[2].default_value = (0.30, 0.48, 0.74, 1.0)
    nt.links.new(coord.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], rng.inputs["Value"])
    nt.links.new(rng.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(mix.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


for name, p in PARAMS.items():
    m = bpy.data.materials.get(name)
    if m is None:
        print("MISSING_MAT", name)
        continue
    rebuild_mat(m, p)
print("MATERIALS_DONE")

scene = bpy.context.scene
sun = bpy.data.objects.get("Sun")
if sun:
    sun.data.energy = 3.2
    sun.data.color = (1.0, 0.93, 0.82)
if scene.world is None:
    scene.world = bpy.data.worlds.new("World")
setup_sky(scene.world)
scene.view_settings.view_transform = "Filmic"
scene.view_settings.look = "Medium High Contrast"
scene.view_settings.exposure = 0.1
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.use_denoising = False

bpy.ops.wm.save_as_mainfile(filepath="/home/hatch/workspace/heiankyo-blender/heian_daidairi_detail_v6.blend")
print("SAVED_V6")


def setup_cam(loc, target, ortho=None, lens=35):
    cam_data = bpy.data.cameras.new("P6Cam")
    cam_data.clip_start = 0.5
    cam_data.clip_end = 5000.0
    if ortho:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho
    else:
        cam_data.lens = lens
    cam = bpy.data.objects.new("P6Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam


def render(path, rx, ry, samples):
    scene.cycles.samples = samples
    scene.render.resolution_x, scene.render.resolution_y = rx, ry
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


OUT = "/home/hatch/workspace/heiankyo-blender/output/view_v6"
setup_cam((0, 697, 1800), (0, 697, 0), ortho=1500)
render(OUT + "_top.png", 1000, 1200, 16)
print("TOP_DONE")
setup_cam((620, -260, 300), (0, 650, 0), lens=35)
render(OUT + "_hero.png", 1280, 720, 48)
print("HERO_DONE")
setup_cam((0, -90, 4), (0, 565, 13), lens=30)
render(OUT + "_axis.png", 1280, 720, 48)
print("AXIS_DONE")
setup_cam((62, 478, 30), (0, 568, 15), lens=38)
render(OUT + "_daigokuden.png", 1280, 720, 48)
print("DAIGOKUDEN_DONE")
