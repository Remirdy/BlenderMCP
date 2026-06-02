from __future__ import annotations

import math
import os
from pathlib import Path

import bpy
from mathutils import Vector


WORKSPACE = Path(os.environ.get("REMIRDY_WORKSPACE", str(Path.home() / "RemirdyWorkspace")))
BLEND_PATH = WORKSPACE / "outputs" / "blends" / "storybook_ferry_istanbul.blend"
RENDER_PATH = WORKSPACE / "outputs" / "renders" / "storybook_ferry_istanbul.png"


def ensure_dirs() -> None:
    for folder in ("blends", "renders", "exports", "thumbnails"):
        (WORKSPACE / "outputs" / folder).mkdir(parents=True, exist_ok=True)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for datablock in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.curves):
        for item in list(datablock):
            if item.users == 0:
                datablock.remove(item)


def mat(name: str, color, roughness: float = 0.7, metallic: float = 0.0, alpha: float = 1.0, emission: float = 0.0):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (color[0], color[1], color[2], alpha)
    material.use_nodes = True
    material.blend_method = "BLEND" if alpha < 1 else "OPAQUE"
    material.show_transparent_back = False
    bsdf = next((node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], alpha)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission
        for key in ("Emission Color", "Emission"):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = (color[0], color[1], color[2], 1)
                break
    return material


def add_cube(name, loc, scale, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        obj.data.materials.append(material)
        obj.color = material.diffuse_color
    return obj


def add_uv_sphere(name, loc, scale, material, segments=32, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    if material:
        obj.data.materials.append(material)
        obj.color = material.diffuse_color
    bpy.ops.object.shade_smooth()
    return obj


def add_cylinder(name, loc, radius, depth, material, vertices=32, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    if material:
        obj.data.materials.append(material)
        obj.color = material.diffuse_color
    bpy.ops.object.shade_smooth()
    return obj


def add_cone(name, loc, radius1, depth, material, vertices=32, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius1, radius2=0, depth=depth, location=loc, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    if material:
        obj.data.materials.append(material)
        obj.color = material.diffuse_color
    bpy.ops.object.shade_smooth()
    return obj


def add_torus(name, loc, major_radius, minor_radius, material, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius,
        minor_radius=minor_radius,
        major_segments=48,
        minor_segments=10,
        location=loc,
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    if material:
        obj.data.materials.append(material)
        obj.color = material.diffuse_color
    bpy.ops.object.shade_smooth()
    return obj


def bevel(obj, amount: float, segments: int = 3) -> None:
    mod = obj.modifiers.new("soft_storybook_edges", "BEVEL")
    mod.width = amount
    mod.segments = segments
    mod.affect = "EDGES"
    obj.modifiers.new("weighted_gouache_normals", "WEIGHTED_NORMAL")


def make_curve(name, points, material, bevel_depth=0.025, resolution=3):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = resolution
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = 3
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points):
        point.co = (co[0], co[1], co[2], 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    if material:
        obj.data.materials.append(material)
        obj.color = material.diffuse_color
    return obj


def create_water(water_mat):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=96, y_subdivisions=64, size=1, location=(0, 0, 0))
    water = bpy.context.object
    water.name = "Gentle_Blue_Harbor_Water"
    water.scale = (14, 8, 1)
    water.data.materials.append(water_mat)
    water.color = water_mat.diffuse_color
    for vert in water.data.vertices:
        x = vert.co.x * water.scale.x
        y = vert.co.y * water.scale.y
        vert.co.z = 0.045 * math.sin(x * 1.7) + 0.025 * math.cos(y * 2.1)
    water.modifiers.new("soft_water_surface", "WEIGHTED_NORMAL")
    return water


def create_ferry(mats):
    hull = add_uv_sphere("Small_Charming_Ferry_Rounded_Hull", (0, -0.55, 0.48), (1.75, 0.56, 0.42), mats["hull"], 48, 18)
    hull.rotation_euler[0] = math.radians(2)
    deck = add_cube("Ferry_Warm_Lower_Deck", (0, -0.55, 0.78), (3.05, 0.94, 0.23), mats["cream"])
    bevel(deck, 0.16, 8)
    upper_deck = add_cube("Ferry_Open_Upper_Deck", (-0.38, -0.57, 1.16), (1.78, 0.78, 0.2), mats["cream"])
    bevel(upper_deck, 0.1, 5)
    cabin = add_cube("Ferry_Soft_Cabin", (0.34, -0.58, 1.18), (1.62, 0.72, 0.8), mats["cream"])
    bevel(cabin, 0.11, 6)
    roof = add_cube("Ferry_Red_Roof", (0.18, -0.58, 1.63), (1.95, 0.86, 0.16), mats["roof"])
    bevel(roof, 0.08, 5)
    bow = add_cone("Ferry_Gentle_Bow", (1.62, -0.55, 0.79), 0.52, 0.82, mats["cream"], 32, rotation=(0, math.radians(90), 0))
    bow.scale.y = 0.55
    stern = add_cube("Ferry_Rounded_Stern", (-1.55, -0.55, 0.74), (0.4, 0.85, 0.3), mats["cream"])
    bevel(stern, 0.15, 6)

    for i, x in enumerate((-0.62, -0.18, 0.28, 0.74)):
        win = add_cube(f"Ferry_Cabin_Window_{i+1}", (x, -0.965, 1.22), (0.29, 0.035, 0.3), mats["window"])
        bevel(win, 0.035, 4)
    for i, x in enumerate((-0.9, -0.52, -0.14, 0.24, 0.62)):
        port = add_uv_sphere(f"Ferry_Lower_Round_Window_{i+1}", (x, -0.985, 0.83), (0.065, 0.018, 0.065), mats["window"], 16, 8)
        port.rotation_euler[1] = math.radians(-12)
    eye_l = add_uv_sphere("Ferry_Subtle_Left_Eye_Window", (0.92, -0.995, 1.1), (0.11, 0.02, 0.11), mats["eye"], 16, 8)
    eye_r = add_uv_sphere("Ferry_Subtle_Right_Eye_Window", (1.22, -0.995, 1.11), (0.11, 0.02, 0.11), mats["eye"], 16, 8)
    eye_l.rotation_euler[1] = math.radians(-12)
    eye_r.rotation_euler[1] = math.radians(-12)
    add_uv_sphere("Ferry_Soft_Left_Blush", (0.72, -1.0, 0.94), (0.09, 0.012, 0.055), mats["blush"], 16, 8)
    add_uv_sphere("Ferry_Soft_Right_Blush", (1.4, -1.0, 0.95), (0.09, 0.012, 0.055), mats["blush"], 16, 8)
    make_curve(
        "Ferry_Tiny_Wonder_Smile",
        [(0.93, -1.015, 0.9), (1.08, -1.045, 0.86), (1.27, -1.015, 0.91)],
        mats["smile"],
        bevel_depth=0.016,
    )

    chimney = add_cylinder("Ferry_Little_Chimney", (-0.72, -0.58, 1.7), 0.11, 0.45, mats["chimney"], 24)
    chimney.rotation_euler[0] = math.radians(2)
    mast = add_cylinder("Ferry_Delicate_Mast", (0.94, -0.57, 1.68), 0.025, 0.86, mats["wood"], 12)
    mast.rotation_euler[1] = math.radians(-8)
    flag = add_cube("Ferry_Tiny_Turkish_Red_Flag", (1.08, -0.59, 2.16), (0.34, 0.025, 0.18), mats["roof"])
    bevel(flag, 0.015, 2)
    crescent = add_torus("Ferry_Flag_Tiny_Crescent_Hint", (1.04, -0.607, 2.16), 0.038, 0.007, mats["cream"], rotation=(math.radians(90), 0, 0))
    crescent.scale.x = 0.75

    for x in (-1.05, -0.35, 0.35, 1.05):
        post = add_cylinder(f"Ferry_Railing_Post_{x:.1f}", (x, -1.02, 0.98), 0.018, 0.28, mats["wood"], 10)
        post.rotation_euler[0] = math.radians(1)
    make_curve("Ferry_Front_Railing", [(-1.15, -1.02, 1.13), (-0.2, -1.02, 1.16), (1.25, -1.02, 1.11)], mats["wood"], 0.012)
    make_curve("Ferry_Red_Lower_Sweep_Stripe", [(-1.35, -1.01, 0.7), (-0.2, -1.04, 0.77), (1.48, -1.0, 0.86)], mats["roof"], 0.025)
    make_curve("Ferry_Red_Upper_Sweep_Stripe", [(-1.25, -1.015, 1.0), (0.0, -1.04, 1.04), (1.24, -1.0, 1.1)], mats["roof"], 0.014)
    for i, x in enumerate((-0.88, -0.42, 0.05, 0.52, 0.98)):
        add_uv_sphere(f"Ferry_Warm_Little_Running_Light_{i+1}", (x, -1.01, 0.98), (0.035, 0.012, 0.035), mats["gold"], 12, 6)
    ring = add_torus("Ferry_Side_Life_Ring", (-1.08, -1.01, 1.04), 0.12, 0.025, mats["roof"], rotation=(math.radians(90), 0, 0))
    add_torus("Ferry_Side_Life_Ring_Inner_Cream", (-1.08, -1.012, 1.04), 0.09, 0.012, mats["cream"], rotation=(math.radians(90), 0, 0))

    wake = make_curve(
        "Soft_Wake_Around_Dreaming_Ferry",
        [(-2.0, -0.5, 0.08), (-1.2, -0.92, 0.09), (0.6, -1.08, 0.1), (2.15, -0.77, 0.08)],
        mats["foam"],
        bevel_depth=0.035,
    )
    return [hull, deck, cabin, roof, bow, stern, chimney, mast, flag, wake]


def create_seagull(name, loc, scale, mats, tilt=0.0):
    body = add_uv_sphere(f"{name}_Body", loc, (0.09 * scale, 0.045 * scale, 0.035 * scale), mats["gull_body"], 16, 8)
    body.rotation_euler = (math.radians(tilt), 0, math.radians(10))
    left = make_curve(
        f"{name}_Left_Wing",
        [(loc[0] - 0.02 * scale, loc[1], loc[2]), (loc[0] - 0.28 * scale, loc[1] + 0.02 * scale, loc[2] + 0.11 * scale), (loc[0] - 0.58 * scale, loc[1], loc[2] + 0.02 * scale)],
        mats["gull_wing"],
        bevel_depth=0.018 * scale,
    )
    right = make_curve(
        f"{name}_Right_Wing",
        [(loc[0] + 0.02 * scale, loc[1], loc[2]), (loc[0] + 0.28 * scale, loc[1] + 0.02 * scale, loc[2] + 0.11 * scale), (loc[0] + 0.58 * scale, loc[1], loc[2] + 0.02 * scale)],
        mats["gull_wing"],
        bevel_depth=0.018 * scale,
    )
    beak = add_cone(f"{name}_Tiny_Beak", (loc[0] + 0.1 * scale, loc[1] - 0.015 * scale, loc[2]), 0.025 * scale, 0.08 * scale, mats["gold"], 12, rotation=(0, math.radians(90), 0))
    return [body, left, right, beak]


def create_pier(mats):
    pier = add_cube("Small_Morning_Pier", (-2.95, -2.75, 0.22), (2.35, 0.95, 0.18), mats["wood"])
    bevel(pier, 0.04, 3)
    for i, x in enumerate((-4.95, -4.15, -3.35, -2.75)):
        post = add_cylinder(f"Pier_Post_{i+1}", (x + 0.95, -2.75, -0.42), 0.075, 1.2, mats["wood"], 12)
        post.rotation_euler[0] = math.radians(1)
    make_curve("Pier_Rope_Front", [(-4.0, -3.23, 0.65), (-3.1, -3.27, 0.54), (-2.2, -3.23, 0.65)], mats["rope"], 0.018)
    make_curve("Pier_Rope_Back", [(-4.0, -2.29, 0.62), (-3.1, -2.25, 0.52), (-2.2, -2.29, 0.62)], mats["rope"], 0.018)
    add_torus("Pier_Small_Life_Ring", (-3.65, -3.24, 0.38), 0.16, 0.035, mats["roof"], rotation=(math.radians(90), 0, 0))
    add_cylinder("Pier_Coil_Rope_1", (-2.75, -3.08, 0.36), 0.18, 0.035, mats["rope"], 28, rotation=(math.radians(90), 0, 0))
    add_cylinder("Pier_Coil_Rope_2", (-2.75, -3.08, 0.39), 0.11, 0.035, mats["wood"], 28, rotation=(math.radians(90), 0, 0))


def create_city_silhouette(mats):
    xs = [-5.5, -4.9, -4.25, -3.55, -2.9, -2.15, -1.25, -0.35, 0.55, 1.35, 2.15, 3.0, 3.85, 4.6, 5.35]
    heights = [1.25, 1.7, 1.1, 2.35, 1.3, 1.9, 1.15, 1.6, 2.25, 1.25, 1.75, 1.15, 2.1, 1.4, 1.65]
    for i, (x, h) in enumerate(zip(xs, heights)):
        block = add_cube(f"Distant_Elegant_City_Block_{i+1}", (x, 4.15, 0.02), (0.46, 0.2, h), mats["silhouette"])
        bevel(block, 0.035, 2)
        if i in (3, 8, 12):
            dome = add_uv_sphere(f"Distant_Soft_Dome_{i+1}", (x, 4.13, h + 0.14), (0.32, 0.32, 0.18), mats["silhouette"], 24, 8)
            dome.scale.z = 0.55
        if i in (2, 7, 11, 14):
            minaret = add_cylinder(f"Distant_Slender_Minaret_{i+1}", (x + 0.34, 4.12, h * 0.78), 0.035, h * 1.45, mats["silhouette"], 12)
            add_cone(f"Distant_Minaret_Cap_{i+1}", (x + 0.34, 4.12, h * 1.5), 0.065, 0.18, mats["silhouette"], 12)
    make_curve("Distant_Galata_Bridge_Hint", [(-1.8, 3.95, 0.55), (-0.2, 3.95, 0.75), (1.5, 3.95, 0.55)], mats["silhouette"], 0.018)
    tower = add_cylinder("Distant_Galata_Tower_Hint", (4.45, 3.92, 1.2), 0.22, 1.75, mats["silhouette"], 18)
    add_cone("Distant_Galata_Tower_Roof_Hint", (4.45, 3.92, 2.12), 0.32, 0.48, mats["silhouette"], 18)
    add_uv_sphere("Distant_Large_Mosque_Dome", (-4.15, 3.9, 1.22), (0.75, 0.42, 0.36), mats["silhouette"], 32, 10)
    for x in (-4.92, -3.32):
        add_cylinder(f"Distant_Large_Mosque_Minaret_{x}", (x, 3.88, 1.35), 0.04, 2.4, mats["silhouette"], 12)
        add_cone(f"Distant_Large_Mosque_Minaret_Cap_{x}", (x, 3.88, 2.62), 0.09, 0.25, mats["silhouette"], 12)


def create_mist(mats):
    for i, (x, y, z, sx, sy) in enumerate([
        (-4.5, 2.35, 0.62, 2.0, 0.15),
        (-1.2, 2.85, 0.72, 2.5, 0.14),
        (2.2, 2.45, 0.64, 2.3, 0.15),
        (4.5, 1.9, 0.53, 1.6, 0.12),
    ]):
        cloud = add_uv_sphere(f"Soft_Morning_Mist_Layer_{i+1}", (x, y, z), (sx, sy, 0.13), mats["mist"], 32, 8)
        cloud.rotation_euler[2] = math.radians(i * 7 - 12)


def create_soft_clouds(mats):
    for i, (x, y, z, sx, sy, color_key) in enumerate([
        (-3.5, 3.2, 3.1, 1.25, 0.18, "cloud_pink"),
        (-1.65, 3.15, 3.28, 1.55, 0.16, "cloud_peach"),
        (2.2, 3.25, 3.38, 1.7, 0.18, "cloud_gold"),
    ]):
        cloud = add_uv_sphere(f"Soft_Watercolor_Cloud_{i+1}", (x, y, z), (sx, sy, 0.3), mats[color_key], 32, 8)
        cloud.rotation_euler[2] = math.radians(-8 + i * 8)


def create_sun_and_dream(mats):
    sun = add_uv_sphere("Warm_Morning_Sun_Disk", (4.75, 4.05, 3.9), (0.5, 0.05, 0.5), mats["sun"], 32, 16)
    sun.rotation_euler[0] = math.radians(90)
    make_curve(
        "Ferry_Dream_Arc_Toward_Seagulls",
        [(-0.2, -0.72, 1.55), (0.72, -0.1, 2.45), (1.7, 0.35, 2.95), (2.65, 0.38, 3.05)],
        mats["dream"],
        bevel_depth=0.018,
    )
    for i, co in enumerate([(0.15, -0.55, 1.62), (0.55, -0.28, 1.98), (1.0, -0.04, 2.3)]):
        add_uv_sphere(f"Dream_Bubble_{i+1}", co, (0.055 + i * 0.018, 0.055 + i * 0.018, 0.055 + i * 0.018), mats["dream"], 16, 8)


def setup_camera_and_light(mats):
    bpy.ops.object.light_add(type="SUN", location=(3.5, -3.8, 6.5), rotation=(math.radians(47), 0, math.radians(38)))
    sun = bpy.context.object
    sun.name = "Soft_Warm_Morning_Sunlight"
    sun.data.energy = 2.0
    sun.data.angle = math.radians(6)

    bpy.ops.object.light_add(type="AREA", location=(-3.5, -4.0, 4.0))
    fill = bpy.context.object
    fill.name = "Large_Soft_Picturebook_Fill"
    fill.data.energy = 450
    fill.data.size = 7

    world = bpy.context.scene.world or bpy.data.worlds.new("Storybook_World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.72, 0.82, 0.94, 1)
        bg.inputs["Strength"].default_value = 0.75

    bpy.ops.object.camera_add(location=(0.0, -10.25, 3.42), rotation=(math.radians(68), 0, 0))
    cam = bpy.context.object
    cam.name = "Camera_Storybook_Harbor_Composition"
    target = Vector((0.18, -0.42, 1.18))
    direction = target - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 36
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = (cam.location - target).length
    cam.data.dof.aperture_fstop = 4.2
    bpy.context.scene.camera = cam


def organize_collections() -> None:
    names = {
        "Environment": ("Gentle_Blue_Harbor_Water", "Soft_Morning_Mist", "Warm_Morning_Sun"),
        "Hero_Ferry": ("Ferry", "Soft_Wake"),
        "Seagulls": ("Seagull",),
        "Pier": ("Pier",),
        "Istanbul_Silhouette": ("Distant",),
        "Lighting": ("Soft_Warm", "Large_Soft"),
        "Cameras": ("Camera_",),
    }
    collections = {name: bpy.data.collections.new(name) for name in names}
    for collection in collections.values():
        bpy.context.scene.collection.children.link(collection)
    for obj in list(bpy.context.scene.objects):
        for coll_name, prefixes in names.items():
            if obj.name.startswith(prefixes):
                for current in list(obj.users_collection):
                    current.objects.unlink(obj)
                collections[coll_name].objects.link(obj)
                break


def configure_render() -> None:
    scene = bpy.context.scene
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1920
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = 0.15
    scene.view_settings.gamma = 1.0
    engines = {item.identifier for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    if "BLENDER_EEVEE_NEXT" in engines:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    else:
        scene.render.engine = "BLENDER_EEVEE"
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 96
        if hasattr(scene.eevee, "use_gtao"):
            scene.eevee.use_gtao = True


def main() -> None:
    ensure_dirs()
    clear_scene()

    mats = {
        "water": mat("M_Watercolor_Gentle_Blue_Water", (0.16, 0.45, 0.66), 0.35, alpha=1.0),
        "hull": mat("M_Ferry_Deep_Teal_Hull", (0.03, 0.46, 0.55), 0.58),
        "cream": mat("M_Ferry_Warm_Cream_Gouache", (0.96, 0.88, 0.69), 0.86),
        "roof": mat("M_Ferry_Soft_Red_Roof", (0.75, 0.18, 0.12), 0.74),
        "window": mat("M_Ferry_Misty_Blue_Windows", (0.34, 0.62, 0.78), 0.22, alpha=1.0),
        "eye": mat("M_Ferry_Subtle_Friendly_Eyes", (0.11, 0.16, 0.18), 0.5),
        "smile": mat("M_Ferry_Tiny_Smile", (0.16, 0.14, 0.12), 0.6),
        "chimney": mat("M_Chimney_Warm_Charcoal", (0.22, 0.18, 0.16), 0.7),
        "wood": mat("M_Soft_Wood_Pier", (0.48, 0.31, 0.18), 0.8),
        "rope": mat("M_Pier_Rope", (0.76, 0.64, 0.45), 0.9),
        "foam": mat("M_Watercolor_Foam", (0.88, 0.96, 0.96), 0.45, alpha=1.0),
        "gull_body": mat("M_Seagull_Warm_White", (0.96, 0.94, 0.88), 0.68),
        "gull_wing": mat("M_Seagull_Soft_Gray_Wings", (0.82, 0.83, 0.8), 0.8),
        "gold": mat("M_Morning_Gold", (0.96, 0.68, 0.26), 0.5, emission=0.12),
        "silhouette": mat("M_Distant_Istanbul_Misty_Silhouette", (0.52, 0.48, 0.54), 0.92, alpha=0.9),
        "mist": mat("M_Soft_Morning_Mist", (0.82, 0.88, 0.9), 0.3, alpha=0.12),
        "sun": mat("M_Warm_Sun_Glow", (1.0, 0.66, 0.28), 0.35, alpha=1.0),
        "dream": mat("M_Translucent_Dream_Of_Flying", (1.0, 0.78, 0.36), 0.4, alpha=1.0),
        "blush": mat("M_Ferry_Warm_Blush", (0.98, 0.48, 0.38), 0.75, alpha=0.95),
        "cloud_pink": mat("M_Cloud_Soft_Pink", (0.9, 0.62, 0.66), 0.9, alpha=0.55),
        "cloud_peach": mat("M_Cloud_Peach_Mist", (0.96, 0.72, 0.5), 0.9, alpha=0.5),
        "cloud_gold": mat("M_Cloud_Morning_Gold", (0.96, 0.78, 0.48), 0.9, alpha=0.45),
    }

    create_water(mats["water"])
    create_city_silhouette(mats)
    create_pier(mats)
    create_ferry(mats)
    create_mist(mats)
    create_soft_clouds(mats)
    create_sun_and_dream(mats)
    for i, (loc, scale, tilt) in enumerate([
        ((1.9, -0.2, 3.0), 1.2, 5),
        ((2.9, 0.28, 3.55), 0.95, -8),
        ((3.8, 0.65, 2.95), 0.8, 4),
        ((-1.55, 0.0, 2.75), 0.72, -4),
        ((0.25, 0.82, 3.8), 0.65, 7),
        ((-2.45, 0.55, 3.35), 0.52, 2),
    ]):
        create_seagull(f"Seagull_{i+1}_Flying_Dream", loc, scale, mats, tilt)

    setup_camera_and_light(mats)
    organize_collections()
    configure_render()

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    bpy.context.scene.render.filepath = str(RENDER_PATH)
    bpy.ops.render.render(write_still=True)
    print(f"BLEND={BLEND_PATH}")
    print(f"RENDER={RENDER_PATH}")


if __name__ == "__main__":
    main()
