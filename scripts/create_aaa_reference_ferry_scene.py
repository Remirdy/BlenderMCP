from __future__ import annotations

import math
import os
from pathlib import Path

import bpy
from mathutils import Vector


WORKSPACE = Path(os.environ.get("REMIRDY_WORKSPACE", str(Path.home() / "RemirdyWorkspace")))
REFERENCE = Path("/Users/emirhan/Desktop/aaa.jpg")
BLEND_PATH = WORKSPACE / "outputs" / "blends" / "kucuk_marti_reference_model.blend"
RENDER_PATH = WORKSPACE / "outputs" / "renders" / "kucuk_marti_reference_model.png"


def dirs() -> None:
    for folder in ("blends", "renders", "exports", "thumbnails"):
        (WORKSPACE / "outputs" / folder).mkdir(parents=True, exist_ok=True)


def clear() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.images):
        for item in list(datablocks):
            if item.users == 0:
                datablocks.remove(item)


def material(name: str, color, alpha: float = 1.0, roughness: float = 0.85, emission: float = 0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, alpha)
    mat.use_nodes = True
    mat.blend_method = "BLEND" if alpha < 1 else "OPAQUE"
    mat.show_transparent_back = False
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, alpha)
        bsdf.inputs["Roughness"].default_value = roughness
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*color, 1)
    return mat


def cube(name, loc, scale, mat, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    obj.color = mat.diffuse_color
    if bevel:
        mod = obj.modifiers.new("soft_rounded_storybook_edges", "BEVEL")
        mod.width = bevel
        mod.segments = 8
        obj.modifiers.new("soft_normals", "WEIGHTED_NORMAL")
    return obj


def sphere(name, loc, scale, mat, segments=32):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=16, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    obj.color = mat.diffuse_color
    bpy.ops.object.shade_smooth()
    return obj


def cyl(name, loc, radius, depth, mat, vertices=32, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    obj.color = mat.diffuse_color
    bpy.ops.object.shade_smooth()
    return obj


def cone(name, loc, radius, depth, mat, vertices=32, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius, radius2=0, depth=depth, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    obj.color = mat.diffuse_color
    bpy.ops.object.shade_smooth()
    return obj


def torus(name, loc, major, minor, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, location=loc, rotation=rot, major_segments=64, minor_segments=12)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    obj.color = mat.diffuse_color
    bpy.ops.object.shade_smooth()
    return obj


def curve(name, pts, mat, width=0.025):
    c = bpy.data.curves.new(name, "CURVE")
    c.dimensions = "3D"
    c.resolution_u = 4
    c.bevel_depth = width
    c.bevel_resolution = 4
    s = c.splines.new("POLY")
    s.points.add(len(pts) - 1)
    for p, co in zip(s.points, pts):
        p.co = (*co, 1)
    obj = bpy.data.objects.new(name, c)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    obj.color = mat.diffuse_color
    return obj


def plane(name, loc, scale, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    obj.color = mat.diffuse_color
    return obj


def image_reference_plane(mat):
    if not REFERENCE.exists():
        return None
    img = bpy.data.images.load(str(REFERENCE), check_existing=True)
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf:
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = 0.22
    obj = plane("AAA_Reference_Ghost_Backdrop", (0, 5.25, 2.4), (3.2, 5.7, 1), mat, rot=(math.radians(90), 0, 0))
    obj.hide_render = True
    obj.display_type = "TEXTURED"
    return obj


def make_water(m):
    water = plane("Painted_Bosphorus_Water_Layer", (0, 0.1, -0.08), (6.8, 6.6, 1), m["water"], rot=(0, 0, 0))
    for i, y in enumerate([-2.8, -2.25, -1.65, -1.05, -0.35, 0.35]):
        curve(f"Watercolor_Ripple_{i+1}", [(-3.0, y, 0.04), (-1.5, y + 0.12, 0.05), (0.1, y - 0.05, 0.04), (2.8, y + 0.08, 0.05)], m["foam"], 0.012)
    for i, x in enumerate([-2.4, -1.2, 0.2, 1.55, 2.55]):
        curve(f"Warm_Sun_Reflection_{i+1}", [(x, -0.6, 0.055), (x + 0.25, -1.25, 0.055), (x - 0.12, -2.3, 0.055)], m["gold"], 0.01)
    return water


def make_skyline(m):
    base_y = 2.65
    for i, x in enumerate([-3.0, -2.55, -2.05, -1.55, -1.1, -0.55, 0.05, 0.62, 1.15, 1.75, 2.35, 2.85]):
        h = [0.65, 0.85, 0.55, 0.75, 0.5, 0.95, 0.62, 0.72, 0.52, 0.82, 0.68, 0.75][i]
        cube(f"Misty_Istanbul_House_{i+1}", (x, base_y, 0.24), (0.36, 0.16, h), m["city"], 0.025)
        cube(f"Misty_Istanbul_Roof_{i+1}", (x, base_y - 0.02, 0.24 + h * 0.55), (0.42, 0.17, 0.08), m["roof"], 0.015)

    dome = sphere("Large_Blue_Mosque_Dome", (-2.45, 2.78, 1.23), (0.55, 0.28, 0.28), m["mosque"])
    dome.scale.z = 0.55
    cube("Large_Blue_Mosque_Base", (-2.45, 2.78, 0.75), (1.45, 0.22, 0.75), m["mosque"], 0.04)
    for x in [-3.15, -2.82, -2.05, -1.72]:
        cyl(f"Blue_Mosque_Minaret_{x}", (x, 2.74, 1.28), 0.035, 1.7, m["mosque"], 16)
        cone(f"Blue_Mosque_Minaret_Cap_{x}", (x, 2.74, 2.18), 0.08, 0.23, m["mosque"], 16)

    tower = cyl("Galata_Tower_Background", (2.35, 2.78, 1.18), 0.2, 1.35, m["city"], 22)
    cone("Galata_Tower_Roof", (2.35, 2.78, 1.96), 0.28, 0.45, m["roof"], 22)


def make_ferry(m):
    hull = sphere("Kucuk_Marti_Turquoise_Rounded_Hull", (0.15, -0.92, 0.72), (1.58, 0.42, 0.38), m["hull"], 48)
    hull.rotation_euler[1] = math.radians(-3)
    cube("Kucuk_Marti_Lower_Cabin", (0.05, -0.94, 1.02), (2.45, 0.5, 0.62), m["cream"], 0.12)
    cube("Kucuk_Marti_Upper_Cabin", (-0.08, -0.95, 1.55), (1.55, 0.46, 0.5), m["cream"], 0.1)
    cube("Kucuk_Marti_Red_Upper_Roof", (-0.08, -0.95, 1.86), (1.75, 0.52, 0.12), m["orange_roof"], 0.06)
    cube("Kucuk_Marti_Back_Open_Deck", (-1.18, -0.95, 1.38), (0.85, 0.48, 0.2), m["deck"], 0.08)
    bow = cone("Kucuk_Marti_Proud_Bow", (1.42, -0.94, 1.0), 0.42, 0.72, m["cream"], 32, rot=(0, math.radians(90), 0))
    bow.scale.y = 0.5

    for i, x in enumerate([-0.78, -0.36, 0.06, 0.48, 0.9]):
        cube(f"Kucuk_Marti_Lower_Window_{i+1}", (x, -1.205, 1.06), (0.26, 0.035, 0.24), m["window"], 0.035)
    for i, x in enumerate([-0.56, -0.18, 0.2, 0.58]):
        cube(f"Kucuk_Marti_Upper_Window_{i+1}", (x, -1.205, 1.57), (0.22, 0.035, 0.22), m["window"], 0.032)

    eye_l = sphere("Kucuk_Marti_Left_Wonder_Eye", (0.78, -1.225, 1.35), (0.075, 0.018, 0.09), m["eye"], 16)
    eye_r = sphere("Kucuk_Marti_Right_Wonder_Eye", (1.04, -1.225, 1.36), (0.075, 0.018, 0.09), m["eye"], 16)
    sphere("Kucuk_Marti_Left_Blush", (0.62, -1.23, 1.2), (0.1, 0.012, 0.055), m["blush"], 16)
    sphere("Kucuk_Marti_Right_Blush", (1.18, -1.23, 1.22), (0.1, 0.012, 0.055), m["blush"], 16)
    curve("Kucuk_Marti_Gentle_Smile", [(0.78, -1.24, 1.18), (0.92, -1.265, 1.14), (1.08, -1.24, 1.19)], m["eye"], 0.011)

    curve("Kucuk_Marti_Red_Body_Stripe", [(-1.08, -1.22, 0.95), (-0.22, -1.25, 1.03), (1.42, -1.21, 1.14)], m["red"], 0.023)
    curve("Kucuk_Marti_Teal_Keel_Line", [(-1.28, -1.21, 0.68), (-0.2, -1.24, 0.62), (1.25, -1.2, 0.75)], m["deep_teal"], 0.02)
    for i, x in enumerate([-0.85, -0.42, 0.02, 0.48, 0.9, 1.25]):
        sphere(f"Kucuk_Marti_Golden_Port_Light_{i+1}", (x, -1.235, 1.02), (0.035, 0.01, 0.035), m["gold"], 12)

    torus("Kucuk_Marti_Life_Ring", (-1.15, -1.22, 1.32), 0.13, 0.025, m["red"], rot=(math.radians(90), 0, 0))
    torus("Kucuk_Marti_Life_Ring_Cream_Insert", (-1.15, -1.225, 1.32), 0.09, 0.012, m["cream"], rot=(math.radians(90), 0, 0))
    cyl("Kucuk_Marti_Chimney", (-0.62, -0.94, 2.03), 0.11, 0.38, m["chimney"], 24)
    mast = cyl("Kucuk_Marti_Flag_Mast", (0.45, -0.94, 2.0), 0.025, 0.72, m["wood"], 12)
    mast.rotation_euler[1] = math.radians(-10)
    cube("Kucuk_Marti_Turkish_Flag", (0.58, -0.955, 2.32), (0.32, 0.025, 0.18), m["red"], 0.01)
    torus("Kucuk_Marti_Flag_Crescent", (0.53, -0.972, 2.32), 0.036, 0.006, m["cream"], rot=(math.radians(90), 0, 0))

    for x in [-1.25, -0.65, -0.05, 0.55, 1.15]:
        cyl(f"Kucuk_Marti_Railing_Post_{x}", (x, -1.23, 1.25), 0.015, 0.28, m["wood"], 8)
    curve("Kucuk_Marti_Front_Railing", [(-1.34, -1.23, 1.38), (-0.25, -1.25, 1.42), (1.22, -1.22, 1.35)], m["wood"], 0.01)
    curve("Kucuk_Marti_Foamy_Wake", [(-1.7, -0.95, 0.2), (-0.75, -1.42, 0.22), (0.75, -1.42, 0.22), (1.75, -0.98, 0.2)], m["foam"], 0.035)


def make_pier(m):
    cube("Foreground_Wooden_Pier", (-2.1, -2.65, 0.25), (1.85, 0.9, 0.16), m["wood"], 0.04)
    for i, x in enumerate([-2.9, -2.3, -1.7, -1.25]):
        cyl(f"Foreground_Pier_Post_{i+1}", (x, -2.65, -0.35), 0.065, 1.1, m["post"], 12)
    curve("Foreground_Pier_Rope", [(-2.95, -3.08, 0.7), (-2.25, -3.15, 0.55), (-1.42, -3.08, 0.68)], m["rope"], 0.018)
    torus("Foreground_Pier_Life_Ring", (-2.75, -3.1, 0.42), 0.16, 0.035, m["red"], rot=(math.radians(90), 0, 0))
    torus("Foreground_Pier_Rope_Coil", (-1.72, -3.02, 0.38), 0.22, 0.025, m["rope"], rot=(math.radians(90), 0, 0))
    cyl("Foreground_Warm_Lantern_Post", (-3.08, -3.08, 0.55), 0.025, 0.88, m["post"], 8)
    cube("Foreground_Warm_Lantern_Glass", (-3.08, -3.08, 1.1), (0.18, 0.08, 0.22), m["lantern"], 0.025)


def make_seagull(name, loc, scale, m, wing_span=1.0, warm=False):
    body_mat = m["gull_warm"] if warm else m["gull"]
    wing_mat = m["gull_wing_warm"] if warm else m["gull_wing"]
    sphere(f"{name}_Body", loc, (0.11 * scale, 0.04 * scale, 0.055 * scale), body_mat, 16)
    cone(f"{name}_Beak", (loc[0] + 0.13 * scale, loc[1] - 0.01, loc[2]), 0.028 * scale, 0.09 * scale, m["gold"], 12, rot=(0, math.radians(90), 0))
    curve(f"{name}_Left_Wing", [(loc[0] - 0.02 * scale, loc[1], loc[2]), (loc[0] - 0.38 * wing_span, loc[1], loc[2] + 0.22 * scale), (loc[0] - 0.82 * wing_span, loc[1], loc[2] + 0.06 * scale)], wing_mat, 0.025 * scale)
    curve(f"{name}_Right_Wing", [(loc[0] + 0.02 * scale, loc[1], loc[2]), (loc[0] + 0.38 * wing_span, loc[1], loc[2] + 0.22 * scale), (loc[0] + 0.82 * wing_span, loc[1], loc[2] + 0.06 * scale)], wing_mat, 0.025 * scale)


def make_birds(m):
    make_seagull("Hero_Seagull_Right", (1.65, -0.12, 3.72), 1.18, m, 0.88, warm=True)
    make_seagull("Hero_Seagull_Front", (1.05, -0.12, 2.75), 1.0, m, 0.72, warm=True)
    make_seagull("Distant_Seagull_Left", (-1.65, 0.05, 3.28), 0.62, m, 0.46)
    make_seagull("Distant_Seagull_Top", (-0.55, 0.08, 4.2), 0.5, m, 0.38)
    make_seagull("Distant_Seagull_Small_Right", (2.45, 0.08, 2.85), 0.46, m, 0.33)


def make_mist_and_clouds(m):
    for i, (x, z, sx) in enumerate([(-2.2, 2.45, 1.1), (-0.7, 2.75, 1.35), (1.05, 2.62, 1.25), (2.35, 2.35, 1.05)]):
        sphere(f"Peach_Morning_Cloud_{i+1}", (x, 3.05, z), (sx, 0.12, 0.28), m["cloud"], 24)
    for i, (x, z, sx) in enumerate([(-2.5, 0.82, 1.25), (-0.7, 0.92, 1.8), (1.35, 0.85, 1.55)]):
        sphere(f"Harbor_Mist_Bank_{i+1}", (x, 1.8, z), (sx, 0.08, 0.16), m["mist"], 24)


def setup():
    bpy.ops.object.light_add(type="SUN", location=(4, -4, 7), rotation=(math.radians(43), 0, math.radians(35)))
    sun = bpy.context.object
    sun.name = "Warm_Istanbul_Morning_Sun"
    sun.data.energy = 2.3
    sun.data.angle = math.radians(6)
    bpy.ops.object.light_add(type="AREA", location=(-3.5, -4.5, 4.5))
    area = bpy.context.object
    area.name = "Soft_Picturebook_Fill"
    area.data.energy = 500
    area.data.size = 6

    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None)
    if bg:
        bg.inputs["Color"].default_value = (0.78, 0.88, 0.96, 1)
        bg.inputs["Strength"].default_value = 0.75

    bpy.ops.object.camera_add(location=(0, -8.7, 2.75))
    cam = bpy.context.object
    cam.name = "Camera_AAA_Reference_Portrait"
    target = Vector((0.0, -0.8, 1.55))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 5.4
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = 7.5
    cam.data.dof.aperture_fstop = 5.6
    bpy.context.scene.camera = cam

    scene = bpy.context.scene
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1920
    scene.render.image_settings.file_format = "PNG"
    engines = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 96
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = 0.05


def collections():
    groups = {
        "Reference": ("AAA_Reference",),
        "Kucuk_Marti_Ferry": ("Kucuk_Marti",),
        "Foreground_Pier": ("Foreground",),
        "Istanbul_Background": ("Misty", "Large_Blue", "Blue_Mosque", "Galata"),
        "Seagulls": ("Hero_Seagull", "Distant_Seagull"),
        "Atmosphere": ("Peach", "Harbor_Mist", "Watercolor", "Warm_Sun", "Soft_Picturebook"),
    }
    cols = {}
    for name in groups:
        cols[name] = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(cols[name])
    for obj in list(bpy.context.scene.objects):
        for name, prefixes in groups.items():
            if obj.name.startswith(prefixes):
                for current in list(obj.users_collection):
                    current.objects.unlink(obj)
                cols[name].objects.link(obj)
                break


def main():
    dirs()
    clear()
    m = {
        "water": material("M_Bosphorus_Water_Painted", (0.23, 0.63, 0.73), 1),
        "foam": material("M_Foamy_Watercolor_White", (0.9, 0.96, 0.95), 0.82),
        "gold": material("M_Warm_Golden_Light", (1.0, 0.72, 0.26), 1, emission=0.2),
        "hull": material("M_Kucuk_Marti_Turquoise_Hull", (0.02, 0.48, 0.55), 1),
        "deep_teal": material("M_Deep_Teal_Line", (0.02, 0.24, 0.31), 1),
        "cream": material("M_Warm_Ferry_Cream", (0.95, 0.87, 0.67), 1),
        "deck": material("M_Soft_Green_Upper_Deck", (0.42, 0.73, 0.67), 1),
        "red": material("M_Turkish_Red_Accent", (0.78, 0.12, 0.1), 1),
        "orange_roof": material("M_Orange_Red_Roof", (0.9, 0.38, 0.16), 1),
        "window": material("M_Rounded_Blue_Windows", (0.35, 0.62, 0.72), 1),
        "eye": material("M_Friendly_Dark_Eyes", (0.12, 0.1, 0.08), 1),
        "blush": material("M_Soft_Ferry_Blush", (0.96, 0.43, 0.36), 0.9),
        "chimney": material("M_Soft_Chimney", (0.38, 0.34, 0.31), 1),
        "wood": material("M_Pier_Warm_Wood", (0.55, 0.37, 0.2), 1),
        "post": material("M_Pier_Teal_Posts", (0.12, 0.42, 0.48), 1),
        "rope": material("M_Coil_Rope", (0.74, 0.62, 0.42), 1),
        "lantern": material("M_Lantern_Glow", (1.0, 0.76, 0.34), 0.92, emission=0.6),
        "city": material("M_Misty_Istanbul_City", (0.66, 0.58, 0.58), 0.72),
        "mosque": material("M_Misty_Mosque_Stone", (0.72, 0.68, 0.66), 0.82),
        "roof": material("M_Red_Tile_Roofs", (0.72, 0.3, 0.22), 0.75),
        "gull": material("M_Seagull_White", (0.95, 0.93, 0.86), 1),
        "gull_warm": material("M_Seagull_Warm_Sunlit", (1.0, 0.88, 0.72), 1),
        "gull_wing": material("M_Seagull_Gray_Wing", (0.78, 0.77, 0.74), 1),
        "gull_wing_warm": material("M_Seagull_Peach_Wing", (0.96, 0.64, 0.42), 1),
        "cloud": material("M_Peach_Morning_Clouds", (0.95, 0.68, 0.54), 0.45),
        "mist": material("M_Low_Harbor_Mist", (0.82, 0.86, 0.88), 0.3),
        "reference": material("M_AAA_Reference_Texture", (1, 1, 1), 0.22),
    }
    image_reference_plane(m["reference"])
    make_water(m)
    make_skyline(m)
    make_mist_and_clouds(m)
    make_birds(m)
    make_ferry(m)
    make_pier(m)
    setup()
    collections()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    bpy.context.scene.render.filepath = str(RENDER_PATH)
    bpy.ops.render.render(write_still=True)
    print(f"BLEND={BLEND_PATH}")
    print(f"RENDER={RENDER_PATH}")


if __name__ == "__main__":
    main()
