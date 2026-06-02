"""Create an API-free MPFB runway animation for the README.

Run with Blender:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/create_mpfb_runway_animation.py
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)
MP4_PATH = OUT_DIR / "mpfb_runway_defile.mp4"
PNG_PATH = OUT_DIR / "mpfb_runway_defile_preview.png"
FRAMES_DIR = OUT_DIR / "mpfb_runway_frames"
BLEND_PATH = OUT_DIR / "mpfb_runway_defile.blend"

FRAMES = 96
FPS = 24
PREVIEW_ONLY = os.environ.get("RUNWAY_PREVIEW_ONLY") == "1"


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for datablock in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.lights):
        for item in list(datablock):
            if item.users == 0:
                datablock.remove(item)


def mat(name: str, color, roughness=0.35, metallic=0.0, emission=None, strength=0.0):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if emission:
            bsdf.inputs["Emission Color"].default_value = emission
            bsdf.inputs["Emission Strength"].default_value = strength
    return material


def look_at(obj, target) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def cube(name, location, scale, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        obj.data.materials.append(material)
    bevel = obj.modifiers.new(f"{name}_soft_edges", "BEVEL")
    bevel.width = min(scale) * 0.18
    bevel.segments = 3
    obj.modifiers.new(f"{name}_weighted_normals", "WEIGHTED_NORMAL")
    return obj


def panel(name, verts, material, parent=None):
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(verts, [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    solid = obj.modifiers.new(f"{name}_cloth_thickness", "SOLIDIFY")
    solid.thickness = 0.012
    solid.offset = 0
    obj.modifiers.new(f"{name}_cloth_normals", "WEIGHTED_NORMAL")
    if parent:
        obj.parent = parent
    return obj


def curve_line(name, points, material, bevel=0.01, parent=None):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 16
    curve.bevel_depth = bevel
    curve.bevel_resolution = 3
    spl = curve.splines.new("POLY")
    spl.points.add(len(points) - 1)
    for point, co in zip(spl.points, points):
        point.co = (co[0], co[1], co[2], 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    if parent:
        obj.parent = parent
    return obj


def local_cube(name, location, scale, material, parent):
    obj = cube(name, (0, 0, 0), scale, material)
    obj.parent = parent
    obj.location = location
    return obj


def bounds(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (
        min(c.x for c in corners),
        max(c.x for c in corners),
        min(c.y for c in corners),
        max(c.y for c in corners),
        min(c.z for c in corners),
        max(c.z for c in corners),
    )


def create_stage():
    runway = mat("Runway wet black lacquer", (0.006, 0.007, 0.009, 1), 0.18, 0.25)
    edge = mat("Runway champagne edge light", (1.0, 0.78, 0.38, 1), 0.24, 0.5, (1.0, 0.62, 0.18, 1), 0.6)
    floor = mat("Soft charcoal studio floor", (0.02, 0.021, 0.024, 1), 0.44)
    audience = mat("Audience silhouette satin black", (0.001, 0.001, 0.001, 1), 0.5)
    lightmat = mat("Linear runway light", (0.82, 0.75, 0.58, 1), 0.2, 0.0, (0.9, 0.72, 0.36, 1), 1.8)

    cube("Studio_Floor", (0, 0, -0.08), (8.0, 10.5, 0.12), floor)
    cube("Gloss_Runway", (0, 0.15, 0.005), (1.55, 8.2, 0.08), runway)
    cube("Runway_Left_Edge", (-0.88, 0.15, 0.08), (0.035, 8.1, 0.035), edge)
    cube("Runway_Right_Edge", (0.88, 0.15, 0.08), (0.035, 8.1, 0.035), edge)
    cube("Backstage_Wall", (0, 4.35, 1.35), (4.8, 0.12, 2.7), floor)

    for side in (-1, 1):
        for i in range(12):
            y = -3.4 + i * 0.58
            h = 0.75 + (i % 3) * 0.08
            body = cube(f"Audience_{side}_{i}_body", (side * 2.0, y, 0.34), (0.22, 0.22, h), audience)
            body.rotation_euler.z = side * 0.1
            bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.13, location=(side * 2.0, y, h + 0.27))
            head = bpy.context.object
            head.name = f"Audience_{side}_{i}_head"
            head.scale.x = 0.78
            head.data.materials.append(audience)
        cube(f"Audience_Bench_{side}", (side * 2.02, -0.15, 0.15), (0.45, 7.5, 0.18), audience)
        cube(f"Runway_Light_Strip_{side}", (side * 1.12, 0.15, 0.12), (0.04, 7.6, 0.03), lightmat)


def create_lighting():
    bpy.context.scene.world = bpy.data.worlds.new("Runway_World") if not bpy.context.scene.world else bpy.context.scene.world
    bpy.context.scene.world.color = (0.012, 0.012, 0.016)
    for x in (-2.2, 0, 2.2):
        bpy.ops.object.light_add(type="AREA", location=(x, -1.0, 4.5))
        light = bpy.context.object
        light.name = f"Softbox_{x:g}"
        light.data.energy = 450
        light.data.size = 3.0
        look_at(light, (0, 0.6, 1.0))
    for x in (-1.4, 1.4):
        bpy.ops.object.light_add(type="SPOT", location=(x, -3.0, 3.0))
        light = bpy.context.object
        light.name = f"Runway_Followspot_{x:g}"
        light.data.energy = 850
        light.data.spot_size = 0.55
        light.data.spot_blend = 0.65
        look_at(light, (0, -0.6, 1.1))


def create_human(name, location, outfit_color, accent_color, moving=False):
    before = set(bpy.data.objects)
    bpy.ops.mpfb.create_human()
    human = bpy.context.object if bpy.context.object and bpy.context.object.type == "MESH" else None
    if human is None:
        new_meshes = [obj for obj in bpy.data.objects if obj not in before and obj.type == "MESH"]
        human = new_meshes[0]
    human.name = f"{name}_MPFB_Body"
    human.location = location
    human.rotation_euler.z = 0

    bpy.ops.object.select_all(action="DESELECT")
    human.select_set(True)
    bpy.context.view_layer.objects.active = human
    rig = None
    if hasattr(bpy.ops, "mpfb") and hasattr(bpy.ops.mpfb, "add_standard_rig") and bpy.ops.mpfb.add_standard_rig.poll():
        bpy.ops.mpfb.add_standard_rig()
        candidates = [obj for obj in bpy.data.objects if obj not in before and obj.type == "ARMATURE"]
        if candidates:
            rig = candidates[-1]
            rig.name = f"{name}_Rig"

    group = bpy.data.objects.new(f"{name}_Runway_Group", None)
    bpy.context.collection.objects.link(group)
    group.location = location
    human.parent = group
    human.location = (0, 0, 0)
    if rig:
        rig.parent = group
        rig.location = (0, 0, 0)

    bpy.context.view_layer.update()
    min_x, max_x, min_y, max_y, min_z, max_z = bounds(human)
    height = max(max_z - min_z, 1.6)
    width = max(max_x - min_x, 0.38)
    coat = mat(f"{name}_structured_black_wool", outfit_color, 0.32, 0.05)
    silk = mat(f"{name}_silk_inner_panel", (0.75, 0.68, 0.56, 1), 0.28, 0.0)
    accent = mat(f"{name}_metal_trim", accent_color, 0.2, 0.65, accent_color, 0.3)

    sx = width * 0.75
    hx = width * 0.5
    fy = -0.055
    by = 0.065
    shoulder = height * 0.74
    waist = height * 0.49
    hem = height * 0.08

    clothing = [
        panel(f"{name}_tailored_bodice", [(-sx * 0.55, fy - 0.22, shoulder + 0.03), (sx * 0.55, fy - 0.22, shoulder + 0.03), (sx * 0.42, fy - 0.23, waist - 0.03), (-sx * 0.42, fy - 0.23, waist - 0.03)], coat, group),
        panel(f"{name}_front_left_coat", [(-sx, fy, shoulder), (-0.04, fy, shoulder - 0.05), (-0.08, fy, hem), (-hx, fy, hem)], coat, group),
        panel(f"{name}_front_right_coat", [(0.04, fy, shoulder - 0.05), (sx, fy, shoulder), (hx, fy, hem), (0.08, fy, hem)], coat, group),
        panel(f"{name}_back_coat", [(-sx, by, shoulder), (sx, by, shoulder), (hx, by, hem), (-hx, by, hem)], coat, group),
        panel(f"{name}_champagne_dress", [(-sx * 0.34, fy - 0.02, shoulder - 0.22), (sx * 0.34, fy - 0.02, shoulder - 0.22), (hx * 0.54, fy - 0.025, hem + 0.12), (-hx * 0.54, fy - 0.025, hem + 0.12)], silk, group),
    ]
    panel(
        f"{name}_structured_evening_gown",
        [(-sx * 0.40, fy - 0.30, height * 0.86), (sx * 0.40, fy - 0.30, height * 0.86),
         (sx * 0.76, fy - 0.28, hem + 0.04), (-sx * 0.76, fy - 0.28, hem + 0.04)],
        coat,
        group,
    )
    panel(
        f"{name}_high_collar_insert",
        [(-sx * 0.32, fy - 0.34, height * 0.88), (sx * 0.32, fy - 0.34, height * 0.88),
         (sx * 0.46, fy - 0.33, shoulder - 0.02), (-sx * 0.46, fy - 0.33, shoulder - 0.02)],
        coat,
        group,
    )
    local_cube(f"{name}_belt", (0, fy - 0.028, waist), (width * 0.82, 0.025, 0.035), accent, group)
    for i, x in enumerate((-0.18, -0.09, 0.0, 0.09, 0.18)):
        curve_line(f"{name}_vertical_trim_{i}", [(x, fy - 0.04, waist + 0.22), (x * 0.75, fy - 0.042, hem + 0.1)], accent, 0.0045, group)
    for side in (-1, 1):
        local_cube(f"{name}_shoulder_{side}", (side * sx * 0.82, fy - 0.03, shoulder - 0.01), (0.2, 0.22, 0.075), coat, group)
        sleeve = local_cube(f"{name}_couture_sleeve_{side}", (side * sx * 1.45, fy - 0.035, shoulder - 0.16), (sx * 1.35, 0.17, 0.105), coat, group)
        sleeve.rotation_euler.y = math.radians(side * 4)
        local_cube(f"{name}_boot_{side}", (side * width * 0.22, fy - 0.015, 0.08), (0.13, 0.18, 0.16), coat, group)


    if moving:
        group.location = (location[0], 3.1, location[2])
        group.keyframe_insert(data_path="location", frame=1)
        group.location = (location[0], -2.35, location[2])
        group.keyframe_insert(data_path="location", frame=FRAMES)
        for f, zrot, x in ((1, -0.045, -0.02), (24, 0.045, 0.02), (48, -0.035, -0.015), (72, 0.035, 0.015), (96, 0.0, 0.0)):
            group.rotation_euler.z = zrot
            group.location.x = location[0] + x
            group.keyframe_insert(data_path="rotation_euler", frame=f)
            group.keyframe_insert(data_path="location", frame=f)
        action = group.animation_data.action if group.animation_data else None
        fcurves = getattr(action, "fcurves", []) if action else []
        for fc in fcurves:
            for key in fc.keyframe_points:
                key.interpolation = "SINE"
    else:
        group.rotation_euler.z = math.radians(8 if location[0] < 0 else -8)

    return group


def create_camera():
    bpy.ops.object.camera_add(location=(0, -6.9, 1.6), rotation=(0, 0, 0))
    cam = bpy.context.object
    cam.name = "Editorial_Runway_Camera"
    cam.data.lens = 34
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = 4.0
    bpy.context.scene.camera = cam
    for frame, loc, target in (
        (1, (0, -6.9, 1.6), (0, 2.0, 1.05)),
        (48, (0.28, -6.1, 1.5), (0, 0.4, 1.12)),
        (96, (-0.18, -5.4, 1.42), (0, -1.75, 1.1)),
    ):
        bpy.context.scene.frame_set(frame)
        cam.location = loc
        look_at(cam, target)
        cam.keyframe_insert(data_path="location", frame=frame)
        cam.keyframe_insert(data_path="rotation_euler", frame=frame)
    return cam


def setup_render():
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = FRAMES
    scene.frame_set(1)
    scene.render.fps = FPS
    scene.render.resolution_x = 720
    scene.render.resolution_y = 404
    scene.render.film_transparent = False
    scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in {item.identifier for item in scene.render.bl_rna.properties["engine"].enum_items} else "BLENDER_WORKBENCH"
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 48
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = -0.15
    scene.view_settings.gamma = 1.0
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    if not PREVIEW_ONLY:
        for old_frame in FRAMES_DIR.glob("frame_*.png"):
            old_frame.unlink()
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(FRAMES_DIR / "frame_")


def main():
    if not hasattr(bpy.ops, "mpfb"):
        raise RuntimeError("MPFB is not enabled in Blender. Install the blender.org MPFB extension first.")
    clear_scene()
    create_stage()
    create_lighting()
    center = create_human("Lead_Model", (0, 3.1, 0.08), (0.008, 0.01, 0.014, 1), (0.95, 0.67, 0.28, 1), moving=True)
    create_human("Left_Model", (-1.1, 1.25, 0.08), (0.055, 0.04, 0.065, 1), (0.58, 0.78, 0.95, 1))
    create_human("Right_Model", (1.1, 0.35, 0.08), (0.045, 0.058, 0.05, 1), (0.95, 0.82, 0.5, 1))
    cam = create_camera()
    cam.data.dof.focus_object = center
    setup_render()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    bpy.context.scene.frame_set(48)
    bpy.ops.render.render(write_still=True)
    bpy.data.images["Render Result"].save_render(str(PNG_PATH))
    print(f"Preview: {PNG_PATH}")
    if not PREVIEW_ONLY:
        bpy.ops.render.render(animation=True)
        print(f"Frames: {FRAMES_DIR}")


if __name__ == "__main__":
    main()
