"""Create the README hero render for Remirdy Blender Studio MCP.

Run with:
    /Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/create_readme_hero_scene.py
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_IMAGE = ROOT / "docs" / "assets" / "remirdy_mcp_readme_hero.png"
OUTPUT_BLEND = Path.home() / "RemirdyWorkspace" / "outputs" / "blends" / "remirdy_mcp_readme_hero.blend"


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def material(name: str, color: tuple[float, float, float, float], roughness: float = 0.5, metallic: float = 0.0, emission: tuple[float, float, float, float] | None = None, strength: float = 0.0) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = next((node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = color
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        if emission:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = emission
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = strength
    return mat


def cube(name: str, location: tuple[float, float, float], scale: tuple[float, float, float], mat: bpy.types.Material, bevel: float = 0.0) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new("soft bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 8
        obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    return obj


def cylinder(name: str, location: tuple[float, float, float], radius: float, depth: float, mat: bpy.types.Material, vertices: int = 48) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    return obj


def text(name: str, body: str, location: tuple[float, float, float], size: float, mat: bpy.types.Material, rotation: tuple[float, float, float] = (math.radians(72), 0, math.radians(0)), align: str = "CENTER") -> bpy.types.Object:
    bpy.ops.object.text_add(location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.body = body
    obj.data.align_x = align
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.extrude = 0.006
    obj.data.materials.append(mat)
    return obj


def line(name: str, points: list[tuple[float, float, float]], mat: bpy.types.Material, bevel_depth: float = 0.025) -> bpy.types.Object:
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = 4
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, coords in zip(spline.points, points):
        point.co = (coords[0], coords[1], coords[2], 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def build_panel(name: str, label: str, location: tuple[float, float, float], width: float, height: float, mat_panel: bpy.types.Material, mat_glow: bpy.types.Material, mat_text: bpy.types.Material) -> bpy.types.Object:
    panel = cube(name, location, (width, 0.16, height), mat_panel, bevel=0.08)
    panel.rotation_euler.x = math.radians(0)
    cube(f"{name}_glow_strip", (location[0], location[1] - 0.09, location[2] + height * 0.42), (width * 0.82, 0.035, 0.045), mat_glow, bevel=0.02)
    text(f"{name}_label", label, (location[0], location[1] - 0.13, location[2] + height * 0.12), 0.18, mat_text, rotation=(math.radians(90), 0, 0))
    return panel


def create_node_card(name: str, label: str, location: tuple[float, float, float], mat: bpy.types.Material, glow: bpy.types.Material, text_mat: bpy.types.Material) -> bpy.types.Object:
    card = cube(name, location, (1.15, 0.08, 0.46), mat, bevel=0.055)
    cube(f"{name}_port", (location[0] - 0.5, location[1] - 0.055, location[2]), (0.08, 0.035, 0.22), glow, bevel=0.02)
    text(f"{name}_text", label, (location[0] + 0.05, location[1] - 0.075, location[2]), 0.105, text_mat, rotation=(math.radians(90), 0, 0))
    return card


def add_scene_assets(mats: dict[str, bpy.types.Material]) -> None:
    # Main showcase table and viewport.
    cube("isometric_showcase_base", (0, 0, 0), (7.7, 4.7, 0.22), mats["charcoal"], bevel=0.12)
    cube("glowing_blender_viewport", (0, -0.03, 0.23), (5.4, 3.05, 0.09), mats["glass"], bevel=0.08)
    cube("viewport_inner_grid", (0, -0.055, 0.31), (4.75, 2.46, 0.025), mats["blue_glow"], bevel=0.025)

    # Mini scene generated inside the viewport.
    cube("mini_architecture_block", (-1.75, -0.42, 0.66), (0.76, 0.56, 0.82), mats["clay"], bevel=0.045)
    cube("mini_tower", (-2.18, -0.04, 0.86), (0.38, 0.38, 1.2), mats["warm_white"], bevel=0.04)
    cylinder("product_turntable", (0.05, -0.48, 0.48), 0.42, 0.2, mats["metal"])
    cylinder("product_asset", (0.05, -0.48, 0.9), 0.22, 0.62, mats["orange"], vertices=64)
    cube("game_blockout", (1.35, -0.58, 0.58), (0.92, 0.5, 0.54), mats["green"], bevel=0.04)
    cube("node_design_preview", (1.9, 0.08, 0.7), (0.68, 0.44, 0.86), mats["purple"], bevel=0.04)

    # Character mannequin.
    cylinder("character_body", (-0.85, 0.55, 0.74), 0.2, 0.68, mats["warm_white"], vertices=32)
    cylinder("character_head", (-0.85, 0.55, 1.21), 0.18, 0.22, mats["warm_white"], vertices=32)
    line("character_arm_l", [(-0.99, 0.55, 0.93), (-1.27, 0.43, 0.7)], mats["warm_white"], bevel_depth=0.035)
    line("character_arm_r", [(-0.71, 0.55, 0.93), (-0.44, 0.43, 0.7)], mats["warm_white"], bevel_depth=0.035)

    # Node cards on the viewport.
    create_node_card("tool_scene_card", "scene tools", (-1.95, 1.12, 0.62), mats["panel"], mats["blue_glow"], mats["text"])
    create_node_card("tool_asset_card", "asset tools", (-0.62, 1.12, 0.62), mats["panel"], mats["orange_glow"], mats["text"])
    create_node_card("tool_render_card", "render tools", (0.72, 1.12, 0.62), mats["panel"], mats["green_glow"], mats["text"])
    create_node_card("tool_export_card", "export GLB", (2.05, 1.12, 0.62), mats["panel"], mats["purple_glow"], mats["text"])

    # Back panels showing the local MCP architecture.
    build_panel("mcp_server_panel", "MCP SERVER", (-3.35, 1.45, 1.45), 1.55, 1.25, mats["panel"], mats["blue_glow"], mats["text"])
    build_panel("bridge_panel", "BLENDER BRIDGE", (0, 1.7, 1.75), 1.95, 1.38, mats["panel"], mats["orange_glow"], mats["text"])
    build_panel("blender_panel", "BPy OPS", (3.35, 1.45, 1.45), 1.55, 1.25, mats["panel"], mats["green_glow"], mats["text"])

    line("mcp_to_bridge", [(-2.55, 1.35, 1.46), (-1.45, 1.58, 1.72), (-0.95, 1.65, 1.72)], mats["blue_glow"], bevel_depth=0.035)
    line("bridge_to_blender", [(0.95, 1.65, 1.72), (1.45, 1.58, 1.72), (2.55, 1.35, 1.46)], mats["green_glow"], bevel_depth=0.035)
    line("bridge_to_viewport", [(0, 1.55, 1.15), (0, 0.72, 0.72), (0, 0.22, 0.42)], mats["orange_glow"], bevel_depth=0.028)

    text("hero_title", "Remirdy Blender Studio MCP", (0, -1.92, 0.55), 0.28, mats["text"], rotation=(math.radians(72), 0, 0))
    text("hero_caption", "Natural-language scene generation, render, and GLB export", (0, -2.22, 0.38), 0.12, mats["muted_text"], rotation=(math.radians(72), 0, 0))


def setup_world_and_camera() -> None:
    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.cycles.samples = 128
    bpy.context.scene.cycles.use_denoising = True
    bpy.context.scene.view_settings.view_transform = "Filmic"
    bpy.context.scene.view_settings.look = "Medium High Contrast"
    bpy.context.scene.view_settings.exposure = -0.35
    bpy.context.scene.view_settings.gamma = 1
    bpy.context.scene.render.resolution_x = 1600
    bpy.context.scene.render.resolution_y = 900
    bpy.context.scene.render.film_transparent = False

    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.025, 0.027, 0.032)

    bpy.ops.object.light_add(type="AREA", location=(-3.5, -4.5, 6.2))
    key = bpy.context.object
    key.name = "large_warm_key_light"
    key.data.energy = 420
    key.data.size = 5.2

    bpy.ops.object.light_add(type="AREA", location=(3.8, 2.4, 4.5))
    rim = bpy.context.object
    rim.name = "cool_rim_light"
    rim.data.energy = 260
    rim.data.size = 3.2
    rim.data.color = (0.5, 0.68, 1.0)

    bpy.ops.object.camera_add(location=(5.2, -6.5, 4.9), rotation=(math.radians(60), 0, math.radians(42)))
    cam = bpy.context.object
    bpy.context.scene.camera = cam
    direction = Vector((0.12, 0.02, 0.9)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 8.0


def main() -> None:
    OUTPUT_IMAGE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_BLEND.parent.mkdir(parents=True, exist_ok=True)
    clear_scene()

    mats = {
        "charcoal": material("charcoal anodized surface", (0.035, 0.039, 0.046, 1), roughness=0.56),
        "panel": material("smoked glass panels", (0.075, 0.085, 0.105, 1), roughness=0.28, metallic=0.05),
        "glass": material("dark glossy viewport glass", (0.02, 0.025, 0.032, 1), roughness=0.18, metallic=0.0),
        "metal": material("brushed graphite metal", (0.36, 0.35, 0.33, 1), roughness=0.38, metallic=0.8),
        "clay": material("warm clay architecture", (0.74, 0.48, 0.34, 1), roughness=0.62),
        "warm_white": material("warm studio white", (0.82, 0.78, 0.68, 1), roughness=0.45),
        "orange": material("copper product accent", (1.0, 0.48, 0.18, 1), roughness=0.35, metallic=0.35),
        "green": material("sage game blockout", (0.35, 0.67, 0.48, 1), roughness=0.55),
        "purple": material("violet node prototype", (0.45, 0.34, 0.72, 1), roughness=0.48),
        "text": material("soft readable text", (0.92, 0.94, 0.96, 1), roughness=0.4, emission=(0.8, 0.9, 1.0, 1), strength=0.18),
        "muted_text": material("muted caption text", (0.56, 0.62, 0.68, 1), roughness=0.4, emission=(0.38, 0.45, 0.52, 1), strength=0.08),
        "blue_glow": material("mcp blue glow", (0.1, 0.36, 1.0, 1), emission=(0.08, 0.36, 1.0, 1), strength=3.8),
        "orange_glow": material("bridge amber glow", (1.0, 0.42, 0.12, 1), emission=(1.0, 0.36, 0.08, 1), strength=3.2),
        "green_glow": material("ops green glow", (0.15, 0.9, 0.48, 1), emission=(0.1, 0.9, 0.42, 1), strength=3.0),
        "purple_glow": material("export violet glow", (0.55, 0.36, 1.0, 1), emission=(0.55, 0.32, 1.0, 1), strength=3.2),
    }

    add_scene_assets(mats)
    setup_world_and_camera()

    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_BLEND))
    bpy.context.scene.render.filepath = str(OUTPUT_IMAGE)
    bpy.ops.render.render(write_still=True)
    print(f"README hero render written to {OUTPUT_IMAGE}")
    print(f"Blend file written to {OUTPUT_BLEND}")


if __name__ == "__main__":
    main()
