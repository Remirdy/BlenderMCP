"""Blender operations for generating high-fidelity 3D parallax hybrid scenes from layered visual art."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import bpy
import bmesh
from mathutils import Vector

from . import helpers as H
from . import material_ops as M
from . import render_ops as R
from .export_ops import workspace_output
from .image_to_3d_ai import create_ai_image_to_3d


def _reconstruct_layer_with_ai(layer_name: str, image_path: str, location: tuple[float, float, float], collection, target_height: float = 1.5, yaw_deg: float = 0.0) -> list[bpy.types.Object]:
    """Use local TripoSR to reconstruct a beautiful 3D mesh from the sliced PSD layer and place it in the scene."""
    print(f"AI Reconstruction starting for layer: {layer_name} from {image_path}...", flush=True)

    # Define output GLB path in workspace
    glb_dir = Path("/Users/emirhan/RemirdyWorkspace/outputs/ai_models")
    glb_dir.mkdir(parents=True, exist_ok=True)
    glb_path = glb_dir / f"{layer_name}.glb"

    # Local command for TripoSR
    local_cmd = "bash /Users/emirhan/Desktop/Blender_MCP/remirdy-blender-studio-mcp/scripts/run_triposr_to_glb.sh \"{image}\" \"{output}\""

    params = {
        "provider": "local_command",
        "local_command": local_cmd,
        "target_height": target_height,
        "auto_upright": True,
        "wait_seconds": 600,
    }

    try:
        # Before importing, note the existing objects to track the new imports
        before_objs = set(bpy.data.objects)

        # Call the image-to-3d integration
        res = create_ai_image_to_3d(image_path, str(glb_path), params)
        print(f"AI Reconstruction finished successfully! Result: {res}", flush=True)

        # Get the imported objects
        imported_objs = [obj for obj in bpy.data.objects if obj not in before_objs]

        # Place and rotate them
        for obj in imported_objs:
            obj.location.x += location[0]
            obj.location.y += location[1]
            obj.location.z += location[2]

            # Apply custom yaw rotation
            if yaw_deg != 0.0:
                obj.rotation_mode = "XYZ"
                obj.rotation_euler.rotate_axis("Z", math.radians(yaw_deg))

            H.link_to_collection(obj, collection)

        return imported_objs
    except Exception as e:
        print(f"AI Reconstruction failed for {layer_name}: {e}. Falling back to high-fidelity procedural 3D model.", flush=True)
        return []


def _create_material(name: str, color: tuple[float, float, float, float], metallic: float = 0.0, roughness: float = 0.5, emission_strength: float = 0.0, emission_color=None) -> bpy.types.Material:
    mat = H.make_material(name, color, metallic=metallic, roughness=roughness, emission_strength=emission_strength, emission_color=emission_color)
    mat.diffuse_color = color
    return mat


def _create_marble_pavement_material() -> bpy.types.Material:
    """Create a gorgeous procedural tiled white marble material with subtle gray veins and high gloss."""
    mat = bpy.data.materials.new("M_Pavement")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Material Output
    output = nodes.new(type="ShaderNodeOutputMaterial")

    # Principled BSDF
    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.15
    bsdf.inputs["Metallic"].default_value = 0.0

    # Brick Texture for tile grid
    brick = nodes.new(type="ShaderNodeTexBrick")
    brick.inputs["Color1"].default_value = (0.96, 0.96, 0.96, 1.0)
    brick.inputs["Color2"].default_value = (0.92, 0.92, 0.92, 1.0)
    brick.inputs["Mortar"].default_value = (0.6, 0.6, 0.6, 1.0)
    brick.inputs["Scale"].default_value = 1.8
    brick.inputs["Mortar Size"].default_value = 0.015

    # Noise Texture for subtle marble veins
    noise = nodes.new(type="ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 8.0
    noise.inputs["Detail"].default_value = 4.0
    noise.inputs["Roughness"].default_value = 0.5

    # Mix node to blend tile colors with gray marble veins
    mix = nodes.new(type="ShaderNodeMix")
    mix.data_type = 'RGBA'
    mix.blend_type = 'MIX'
    mix.inputs["Factor"].default_value = 0.12
    mix.inputs[7].default_value = (0.65, 0.65, 0.65, 1.0) # Gray vein color

    # Links
    links.new(brick.outputs["Color"], mix.inputs[6])
    links.new(noise.outputs["Color"], mix.inputs[0])
    links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    mat.diffuse_color = (0.95, 0.95, 0.95, 1.0)
    return mat


def _create_vespa(location: tuple[float, float, float], collection, yaw_deg: float = 0.0) -> list[bpy.types.Object]:
    """Procedurally build a beautiful light blue Vespa scooter with high-fidelity details."""
    created = []

    # Materials
    vespa_blue = _create_material("M_Vespa_Blue", (0.42, 0.68, 0.78, 1.0), metallic=0.3, roughness=0.25)
    chrome = _create_material("M_Vespa_Chrome", (0.92, 0.92, 0.92, 1.0), metallic=0.9, roughness=0.1)
    black_rubber = _create_material("M_Vespa_Rubber", (0.1, 0.1, 0.1, 1.0), roughness=0.8)
    leather_seat = _create_material("M_Vespa_Leather", (0.12, 0.1, 0.08, 1.0), roughness=0.6)
    headlight_yellow = _create_material("M_Vespa_Light", (1.0, 0.92, 0.65, 1.0), emission_strength=1.5)

    bx, by, bz = location
    yaw = math.radians(yaw_deg)
    cos_y = math.cos(yaw)
    sin_y = math.sin(yaw)

    def get_rot_pos(ox: float, oy: float, oz: float) -> tuple[float, float, float]:
        # Rotate offset around Z axis by yaw
        rx = bx + (ox * cos_y - oy * sin_y)
        ry = by + (ox * sin_y + oy * cos_y)
        rz = bz + oz
        return rx, ry, rz

    # 1. Wheels (Front and Rear)
    for i, offset_y in enumerate((-0.6, 0.6)):
        w_x, w_y, w_z = get_rot_pos(0.0, offset_y, 0.3)
        bpy.ops.mesh.primitive_torus_add(
            location=(w_x, w_y, w_z),
            rotation=(0, math.radians(90), yaw),
            major_radius=0.22,
            minor_radius=0.08
        )
        wheel = bpy.context.object
        wheel.name = f"Vespa_Wheel_{i}"
        wheel.data.materials.append(black_rubber)
        H.link_to_collection(wheel, collection)
        created.append(wheel)

        # Chrome wheel hubs
        hub = H.add_cylinder(f"Vespa_Hub_{i}", radius=0.1, depth=0.1, location=get_rot_pos(0.0, offset_y, 0.3), verts=12, collection=collection, mat=chrome)
        hub.rotation_euler = (0, math.radians(90), yaw)
        created.append(hub)

    # 2. Main Frame Body
    body = H.add_box("Vespa_Body", size=(0.35, 1.2, 0.4), location=get_rot_pos(0.0, 0.0, 0.35), collection=collection, mat=vespa_blue)
    body.rotation_euler = (0, 0, yaw)
    created.append(body)

    # Curved rear engine covers
    engine_cover = H.add_sphere("Vespa_Engine_Cover", radius=0.24, location=get_rot_pos(0.0, -0.35, 0.4), collection=collection, mat=vespa_blue)
    engine_cover.scale = (0.9, 1.4, 0.8)
    engine_cover.rotation_euler = (0, 0, yaw)
    created.append(engine_cover)

    # 3. Front Steering Column & Shield
    shield = H.add_box("Vespa_Shield", size=(0.4, 0.1, 0.65), location=get_rot_pos(0.0, 0.45, 0.65), collection=collection, mat=vespa_blue)
    shield.rotation_euler = (math.radians(-15), 0, yaw)
    created.append(shield)

    # Mudguard (Front fender)
    fender = H.add_sphere("Vespa_Fender", radius=0.18, location=get_rot_pos(0.0, 0.6, 0.42), collection=collection, mat=vespa_blue)
    fender.scale = (0.8, 1.1, 0.7)
    fender.rotation_euler = (0, 0, yaw)
    created.append(fender)

    # Steering rod (Chrome)
    rod = H.add_cylinder("Vespa_Steer_Rod", radius=0.03, depth=0.7, location=get_rot_pos(0.0, 0.45, 0.65), verts=8, collection=collection, mat=chrome)
    rod.rotation_euler = (math.radians(-15), 0, yaw)
    created.append(rod)

    # Handlebars
    bars = H.add_cylinder("Vespa_Handlebars", radius=0.025, depth=0.6, location=get_rot_pos(0.0, 0.32, 0.98), verts=8, collection=collection, mat=chrome)
    bars.rotation_euler = (0, math.radians(90), yaw)
    created.append(bars)

    # Black handles
    for side in (-1, 1):
        hx, hy, hz = get_rot_pos(side * 0.26, 0.32, 0.98)
        handle = H.add_cylinder(f"Vespa_Handle_{side}", radius=0.03, depth=0.1, location=(hx, hy, hz), verts=8, collection=collection, mat=black_rubber)
        handle.rotation_euler = (0, math.radians(90), yaw)
        created.append(handle)

    # 4. Circular Front Headlight
    light = H.add_cylinder("Vespa_Headlight", radius=0.07, depth=0.1, location=get_rot_pos(0.0, 0.35, 1.02), verts=12, collection=collection, mat=chrome)
    light.rotation_euler = (math.radians(75), 0, yaw)
    created.append(light)

    bulb = H.add_sphere("Vespa_Bulb", radius=0.06, location=get_rot_pos(0.0, 0.4, 1.03), collection=collection, mat=headlight_yellow)
    bulb.rotation_euler = (0, 0, yaw)
    created.append(bulb)

    # 5. Black Leather Seat
    seat = H.add_box("Vespa_Seat", size=(0.26, 0.7, 0.08), location=get_rot_pos(0.0, -0.05, 0.62), collection=collection, mat=leather_seat)
    seat.rotation_euler = (math.radians(-8), 0, yaw)
    created.append(seat)

    return created


def _create_balustrade(collection) -> list[bpy.types.Object]:
    """Procedurally build a beautiful classic Italian coastal stone balustrade aligned exactly like the art."""
    created = []
    stone_mat = _create_material("M_Balustrade_Stone", (0.78, 0.75, 0.72, 1.0), roughness=0.7)

    # Spans X from -10.0 to 10.0 at Y = -2.8
    y_pos = -2.8
    z_pos = 0.0

    # 1. Main Base Wall
    base = H.add_box("Balustrade_Base", size=(20.0, 0.35, 0.18), location=(0.0, y_pos, z_pos), collection=collection, mat=stone_mat)
    created.append(base)

    # 2. Main Top Handrail
    handrail = H.add_box("Balustrade_Handrail", size=(20.0, 0.4, 0.12), location=(0.0, y_pos, z_pos + 0.86), collection=collection, mat=stone_mat)
    created.append(handrail)

    # 3. Anchor Pillars (Large stone blocks) located exactly at specific gaps in the concept art!
    posts = (-9.2, -5.4, -2.2, 1.2, 5.0, 7.6, 9.4)
    for i, x in enumerate(posts):
        pillar = H.add_box(f"Balustrade_Post_{i}", size=(0.5, 0.5, 0.94), location=(x, y_pos, z_pos), collection=collection, mat=stone_mat)
        created.append(pillar)

    # 4. Spacing balusters (classical decorative columns) between the anchor posts
    baluster_counter = 0
    for x_idx in range(-95, 96, 5):
        x = x_idx * 0.1
        # Skip if outside the span or too close to any post
        if x < -9.4 or x > 9.4:
            continue
        if any(abs(x - p) < 0.42 for p in posts):
            continue

        # Simple procedural baluster column
        col_base = H.add_cylinder(f"Baluster_Base_{baluster_counter}", radius=0.08, depth=0.1, location=(x, y_pos, z_pos + 0.18), verts=8, collection=collection, mat=stone_mat)
        created.append(col_base)

        col_mid = H.add_sphere(f"Baluster_Mid_{baluster_counter}", radius=0.07, location=(x, y_pos, z_pos + 0.45), collection=collection, mat=stone_mat)
        col_mid.scale = (1.0, 1.0, 2.2)
        created.append(col_mid)

        col_top = H.add_cylinder(f"Baluster_Top_{baluster_counter}", radius=0.08, depth=0.1, location=(x, y_pos, z_pos + 0.78), verts=8, collection=collection, mat=stone_mat)
        created.append(col_top)

        baluster_counter += 1

    return created


def _create_potted_plant(location: tuple[float, float, float], collection) -> list[bpy.types.Object]:
    """Procedurally build a beautiful terracotta flower pot with a clean conical cypress tree."""
    created = []

    # Materials
    terracotta = _create_material("M_Pot_Terracotta", (0.76, 0.42, 0.28, 1.0), roughness=0.7)
    soil = _create_material("M_Pot_Soil", (0.18, 0.12, 0.08, 1.0), roughness=0.9)
    cypress_green = _create_material("M_Cypress_Foliage", (0.12, 0.35, 0.15, 1.0), roughness=0.8)
    trunk_mat = _create_material("M_Cypress_Trunk", (0.35, 0.22, 0.12, 1.0), roughness=0.9)

    px, py, pz = location

    # 1. Terracotta Pot with slight taper (cone with radius1 and radius2)
    mesh = bpy.data.meshes.new("Terracotta_Pot")
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=12,
        radius1=0.28, radius2=0.22, depth=0.48
    )
    bm.to_mesh(mesh)
    bm.free()
    pot = bpy.data.objects.new("Terracotta_Pot", mesh)
    bpy.context.scene.collection.objects.link(pot)
    pot.location = (px, py, pz + 0.24)
    H._finish(pot, "Terracotta_Pot", collection, terracotta)
    created.append(pot)

    # Soil layer inside the pot
    soil_mesh = H.add_cylinder("Pot_Soil", radius=0.25, depth=0.05, location=(px, py, pz + 0.44), verts=12, collection=collection, mat=soil)
    created.append(soil_mesh)

    # 2. Conical Cypress Tree
    trunk = H.add_cylinder("Cypress_Trunk", radius=0.04, depth=0.3, location=(px, py, pz + 0.46), verts=8, collection=collection, mat=trunk_mat)
    created.append(trunk)

    # Cypress foliage cone stack
    cone1 = H.add_cone("Cypress_Foliage_Base", radius=0.24, depth=0.8, location=(px, py, pz + 0.7), verts=12, collection=collection, mat=cypress_green)
    cone1.scale = (1.0, 1.0, 1.2)
    created.append(cone1)

    cone2 = H.add_cone("Cypress_Foliage_Mid", radius=0.18, depth=0.6, location=(px, py, pz + 1.2), verts=12, collection=collection, mat=cypress_green)
    cone2.scale = (1.0, 1.0, 1.2)
    created.append(cone2)

    cone3 = H.add_cone("Cypress_Foliage_Top", radius=0.12, depth=0.4, location=(px, py, pz + 1.6), verts=12, collection=collection, mat=cypress_green)
    cone3.scale = (1.0, 1.0, 1.2)
    created.append(cone3)

    return created


def _create_sleeping_cat(name: str, location: tuple[float, float, float], collection) -> list[bpy.types.Object]:
    """Procedurally build a beautiful sleeping cat curled up."""
    created = []
    cat_mat = _create_material("M_Cat_Brown", (0.58, 0.42, 0.28, 1.0), roughness=0.8)
    cx, cy, cz = location

    # Body sphere (flattened)
    body = H.add_sphere(f"{name}_Body", radius=0.12, location=(cx, cy, cz + 0.06), collection=collection, mat=cat_mat)
    body.scale = (1.4, 1.0, 0.6)
    created.append(body)

    # Head sphere
    head = H.add_sphere(f"{name}_Head", radius=0.08, location=(cx + 0.08, cy + 0.04, cz + 0.09), collection=collection, mat=cat_mat)
    head.scale = (1.0, 1.0, 0.9)
    created.append(head)

    # Tail (curve/cylinder)
    tail = H.add_cylinder(f"{name}_Tail", radius=0.025, depth=0.24, location=(cx - 0.12, cy - 0.05, cz + 0.05), verts=6, collection=collection, mat=cat_mat)
    tail.rotation_euler = (0, math.radians(65), math.radians(-30))
    created.append(tail)

    return created


def _create_bench_set(location: tuple[float, float, float], collection) -> list[bpy.types.Object]:
    """Procedurally build the wooden park bench, draped blue jersey, open newspaper, and sleeping cat."""
    created = []

    # Materials
    wood = _create_material("M_Bench_Wood", (0.42, 0.28, 0.18, 1.0), roughness=0.6)
    metal = _create_material("M_Bench_Metal", (0.1, 0.12, 0.1, 1.0), metallic=0.5, roughness=0.4)
    jersey_blue = _create_material("M_Jersey_Blue", (0.05, 0.32, 0.72, 1.0), roughness=0.6)
    white_trim = _create_material("M_Jersey_White", (0.95, 0.95, 0.95, 1.0), roughness=0.6)
    paper = _create_material("M_Newspaper", (0.85, 0.85, 0.82, 1.0), roughness=0.9)

    bx, by, bz = location

    # 1. Wooden Bench
    # Legs (Metal)
    for offset_x in (-0.8, 0.8):
        leg = H.add_box(f"Bench_Leg_{offset_x}", size=(0.06, 0.55, 0.44), location=(bx + offset_x, by, bz), collection=collection, mat=metal)
        created.append(leg)

        back_support = H.add_box(f"Bench_BackSupport_{offset_x}", size=(0.04, 0.06, 0.44), location=(bx + offset_x, by - 0.24, bz + 0.35), collection=collection, mat=metal)
        back_support.rotation_euler = (math.radians(-10), 0, 0)
        created.append(back_support)

    # Seat Planks
    for offset_y in (-0.18, -0.06, 0.06, 0.18):
        plank = H.add_box(f"Bench_Plank_{offset_y}", size=(1.8, 0.09, 0.03), location=(bx, by + offset_y, bz + 0.42), collection=collection, mat=wood)
        created.append(plank)

    # Backrest Planks
    for offset_z in (0.54, 0.68):
        bplank = H.add_box(f"Bench_BackPlank_{offset_z}", size=(1.8, 0.03, 0.09), location=(bx, by - 0.22, bz + offset_z), collection=collection, mat=wood)
        bplank.rotation_euler = (math.radians(-10), 0, 0)
        created.append(bplank)

    # 2. Sleeping Cat on the Bench (left side)
    cat_objs = _create_sleeping_cat("Bench_Cat", (bx - 0.45, by - 0.05, bz + 0.44), collection)
    created.extend(cat_objs)

    # 3. Procedural Italian Blue Jersey draped on the seat
    torso = H.add_box("Jersey_Torso", size=(0.32, 0.28, 0.06), location=(bx + 0.05, by - 0.08, bz + 0.48), collection=collection, mat=jersey_blue)
    torso.rotation_euler = (math.radians(-8), 0, math.radians(15))
    created.append(torso)

    sleeve_l = H.add_box("Jersey_Sleeve_L", size=(0.1, 0.14, 0.05), location=(bx - 0.12, by - 0.05, bz + 0.46), collection=collection, mat=jersey_blue)
    sleeve_l.rotation_euler = (math.radians(-8), math.radians(20), math.radians(15))
    created.append(sleeve_l)

    sleeve_r = H.add_box("Jersey_Sleeve_R", size=(0.1, 0.14, 0.05), location=(bx + 0.22, by - 0.1, bz + 0.49), collection=collection, mat=jersey_blue)
    sleeve_r.rotation_euler = (math.radians(-8), math.radians(-20), math.radians(15))
    created.append(sleeve_r)

    collar = H.add_box("Jersey_Collar", size=(0.08, 0.04, 0.01), location=(bx + 0.05, by - 0.06, bz + 0.52), collection=collection, mat=white_trim)
    collar.rotation_euler = (math.radians(-8), 0, math.radians(15))
    created.append(collar)

    # 4. Open Newspaper on the Bench
    news = H.add_box("Bench_Newspaper", size=(0.34, 0.28, 0.02), location=(bx + 0.45, by - 0.05, bz + 0.45), collection=collection, mat=paper)
    news.rotation_euler = (math.radians(-8), 0, math.radians(-10))
    created.append(news)

    return created


def _create_cafe_set(location: tuple[float, float, float], collection) -> list[bpy.types.Object]:
    """Procedurally build the round café table, stools, wine bottle, glasses, and coffee cups."""
    created = []

    # Materials
    wood_top = _create_material("M_Cafe_Wood", (0.5, 0.35, 0.22, 1.0), roughness=0.5)
    metal = _create_material("M_Cafe_Metal", (0.1, 0.1, 0.1, 1.0), metallic=0.6, roughness=0.3)
    red_cushion = _create_material("M_Stool_Cushion", (0.7, 0.15, 0.15, 1.0), roughness=0.5)
    green_glass = _create_material("M_Wine_Bottle", (0.05, 0.28, 0.12, 0.75), roughness=0.15)
    clear_glass = _create_material("M_Wine_Glass", (0.9, 0.95, 1.0, 0.25), roughness=0.05)
    clear_glass.blend_method = "BLEND"

    tx, ty, tz = location

    # 1. Round Café Table
    top = H.add_cylinder("Cafe_Table_Top", radius=0.5, depth=0.04, location=(tx, ty, tz + 0.76), verts=16, collection=collection, mat=wood_top)
    created.append(top)

    leg = H.add_cylinder("Cafe_Table_Leg", radius=0.035, depth=0.76, location=(tx, ty, tz), verts=8, collection=collection, mat=metal)
    created.append(leg)

    base = H.add_cylinder("Cafe_Table_Base", radius=0.22, depth=0.04, location=(tx, ty, tz), verts=12, collection=collection, mat=metal)
    created.append(base)

    # 2. Café Stools (Two stools on either side)
    for offset_x in (-0.7, 0.7):
        sx = tx + offset_x
        cushion = H.add_cylinder(f"Stool_Cushion_{int(offset_x*10)}", radius=0.18, depth=0.06, location=(sx, ty, tz + 0.44), verts=12, collection=collection, mat=red_cushion)
        created.append(cushion)

        leg_base = H.add_cylinder(f"Stool_Base_{int(offset_x*10)}", radius=0.14, depth=0.44, location=(sx, ty, tz), verts=8, collection=collection, mat=metal)
        created.append(leg_base)

    # 3. Green Wine Bottle on the Table
    bottle = H.add_cylinder("Wine_Bottle", radius=0.045, depth=0.22, location=(tx - 0.1, ty + 0.05, tz + 0.78), verts=8, collection=collection, mat=green_glass)
    created.append(bottle)

    neck = H.add_cylinder("Wine_Bottle_Neck", radius=0.015, depth=0.08, location=(tx - 0.1, ty + 0.05, tz + 0.98), verts=8, collection=collection, mat=green_glass)
    created.append(neck)

    # 4. Wine Glasses
    for i, offset_x in enumerate((-0.18, 0.05)):
        glass = H.add_cylinder(f"Wine_Glass_{i}", radius=0.025, depth=0.08, location=(tx + offset_x, ty - 0.05, tz + 0.78), verts=8, collection=collection, mat=clear_glass)
        created.append(glass)

    # 5. Ceramic Coffee cups & liquid
    ceramic = _create_material("M_Coffee_Cup", (0.95, 0.95, 0.95, 1.0), roughness=0.2)
    coffee_brown = _create_material("M_Coffee_Liquid", (0.24, 0.15, 0.08, 1.0), roughness=0.3)
    for i, (ox, oy) in enumerate(((0.14, 0.12), (-0.12, -0.15))):
        cup = H.add_cylinder(f"Coffee_Cup_{i}", radius=0.035, depth=0.05, location=(tx + ox, ty + oy, tz + 0.78), verts=8, collection=collection, mat=ceramic)
        created.append(cup)

        liquid = H.add_cylinder(f"Coffee_Liquid_{i}", radius=0.03, depth=0.01, location=(tx + ox, ty + oy, tz + 0.81), verts=8, collection=collection, mat=coffee_brown)
        created.append(liquid)

    return created


def _create_chalkboard(location: tuple[float, float, float], collection, yaw_deg: float = 0.0) -> list[bpy.types.Object]:
    """Procedurally build a beautiful wooden A-frame chalkboard sign rotated naturally."""
    created = []
    wood = _create_material("M_Board_Wood", (0.35, 0.22, 0.12, 1.0), roughness=0.6)
    chalkboard = _create_material("M_Board_Slate", (0.08, 0.08, 0.08, 1.0), roughness=0.9)

    bx, by, bz = location
    yaw = math.radians(yaw_deg)
    cos_y = math.cos(yaw)
    sin_y = math.sin(yaw)

    def get_rot_pos(ox: float, oy: float, oz: float) -> tuple[float, float, float]:
        rx = bx + (ox * cos_y - oy * sin_y)
        ry = by + (ox * sin_y + oy * cos_y)
        rz = bz + oz
        return rx, ry, rz

    # Wooden frames (Front & Back panels)
    for i, rot_y in enumerate((-10, 10)):
        panel_y = (0.08 if i == 0 else -0.08)
        px, py, pz = get_rot_pos(0.0, panel_y, 0.45)

        panel = H.add_box(f"Chalkboard_Frame_{i}", size=(0.55, 0.04, 0.9), location=(bx, by, bz), collection=collection, mat=wood)
        panel.location = (px, py, pz)
        panel.rotation_euler = (math.radians(rot_y), 0, yaw)
        created.append(panel)

        # Black board insert
        slate_y = (0.1 if i == 0 else -0.1)
        sx, sy, sz = get_rot_pos(0.0, slate_y, 0.5)
        slate = H.add_box(f"Chalkboard_Slate_{i}", size=(0.47, 0.01, 0.74), location=(bx, by, bz), collection=collection, mat=chalkboard)
        slate.location = (sx, sy, sz)
        slate.rotation_euler = (math.radians(rot_y), 0, yaw)
        created.append(slate)

    return created


def _create_statue_crate(location: tuple[float, float, float], collection) -> list[bpy.types.Object]:
    """Procedurally build three classical white marble bust statues sitting side-by-side on a low wooden crate shelf."""
    created = []

    marble = _create_material("M_Statue_Marble", (0.94, 0.94, 0.92, 1.0), roughness=0.18)
    crate_wood = _create_material("M_Crate_Wood", (0.58, 0.46, 0.34, 1.0), roughness=0.7)

    bx, by, bz = location

    # 1. Wooden low shelf crate
    crate = H.add_box("Statue_Crate", size=(0.95, 0.45, 0.16), location=(bx, by, bz), collection=collection, mat=crate_wood)
    created.append(crate)

    # 2. Three White Marble Busts
    bust_xs = (bx - 0.28, bx, bx + 0.28)
    for i, sx in enumerate(bust_xs):
        sy = by
        sz = bz + 0.16

        # Base/pedestal
        base = H.add_cylinder(f"Bust_Base_{i}", radius=0.07, depth=0.06, location=(sx, sy, sz), verts=8, collection=collection, mat=marble)
        created.append(base)

        # Chest shoulders block
        chest = H.add_box(f"Bust_Chest_{i}", size=(0.18, 0.1, 0.1), location=(sx, sy, sz + 0.06), collection=collection, mat=marble)
        created.append(chest)

        # Head sphere
        head = H.add_sphere(f"Bust_Head_{i}", radius=0.07, location=(sx, sy, sz + 0.18), collection=collection, mat=marble)
        head.scale = (1.0, 1.1, 1.25)
        created.append(head)

        # Hair structure/top details
        hair = H.add_sphere(f"Bust_Hair_{i}", radius=0.05, location=(sx, sy + 0.02, sz + 0.24), collection=collection, mat=marble)
        created.append(hair)

    return created


def _create_leaning_tower(location: tuple[float, float, float], collection) -> list[bpy.types.Object]:
    """Procedurally build a beautiful Leaning Tower of Pisa tilted landmark model."""
    created = []
    marble = _create_material("M_Pisa_Marble", (0.88, 0.85, 0.8, 1.0), roughness=0.6)
    dark_trim = _create_material("M_Pisa_Dark", (0.3, 0.3, 0.3, 1.0), roughness=0.7)

    tx, ty, tz = location

    # Tilted root base
    bpy.ops.mesh.primitive_cylinder_add(radius=1.2, depth=0.3, location=(tx, ty, tz + 0.15))
    base = bpy.context.object
    base.name = "Pisa_Base"
    base.data.materials.append(marble)
    H.link_to_collection(base, collection)
    created.append(base)

    # Reconstruct 6 tiers of arches!
    tier_count = 6
    for tier in range(tier_count):
        tz_tier = tz + 0.3 + (tier * 0.75)
        radius = 1.0 - (tier * 0.03)

        ring = H.add_cylinder(f"Pisa_Tier_{tier}", radius=radius, depth=0.68, location=(tx, ty, tz_tier), verts=16, collection=collection, mat=marble)
        created.append(ring)

        trim = H.add_cylinder(f"Pisa_Trim_{tier}", radius=radius + 0.05, depth=0.07, location=(tx, ty, tz_tier + 0.34), verts=16, collection=collection, mat=dark_trim)
        created.append(trim)

    # Top belfry
    belfry = H.add_cylinder("Pisa_Belfry", radius=0.75, depth=0.6, location=(tx, ty, tz + 0.3 + (tier_count * 0.75)), verts=12, collection=collection, mat=marble)
    created.append(belfry)

    # Tilt all elements by 5.5 degrees backward/sideward!
    for obj in created:
        obj.rotation_mode = "XYZ"
        obj.rotation_euler.rotate_axis("X", math.radians(5.5))
        obj.rotation_euler.rotate_axis("Y", math.radians(2.0))

    return created


def _create_st_peters_dome(location: tuple[float, float, float], collection) -> list[bpy.types.Object]:
    """Procedurally build a beautiful St. Peter's Basilica style dome landmark."""
    created = []
    marble = _create_material("M_Dome_Marble", (0.86, 0.84, 0.81, 1.0), roughness=0.5)
    dome_lead = _create_material("M_Dome_Roof", (0.6, 0.62, 0.65, 1.0), roughness=0.4)
    gold = _create_material("M_Dome_Gold", (0.95, 0.78, 0.18, 1.0), metallic=0.9, roughness=0.1)

    dx, dy, dz = location

    # 1. Colonnade wall cylinder base
    base = H.add_cylinder("Dome_Colonnade_Base", radius=1.0, depth=0.6, location=(dx, dy, dz), verts=16, collection=collection, mat=marble)
    created.append(base)

    # Small columns ring
    for i in range(12):
        angle = math.radians(i * 30)
        cx = dx + math.cos(angle) * 0.95
        cy = dy + math.sin(angle) * 0.95
        col = H.add_cylinder(f"Dome_Col_{i}", radius=0.04, depth=0.56, location=(cx, cy, dz + 0.02), verts=6, collection=collection, mat=marble)
        created.append(col)

    # Top trim ring
    trim = H.add_cylinder("Dome_Colonnade_Trim", radius=1.02, depth=0.08, location=(dx, dy, dz + 0.6), verts=16, collection=collection, mat=marble)
    created.append(trim)

    # 2. Dome Roof (hemisphere)
    dome = H.add_sphere("Dome_Roof", radius=0.88, location=(dx, dy, dz + 0.68), collection=collection, mat=dome_lead)
    dome.scale = (1.0, 1.0, 1.1)
    created.append(dome)

    # 3. Lantern Cap
    lantern_base = H.add_cylinder("Dome_Lantern_Base", radius=0.18, depth=0.18, location=(dx, dy, dz + 1.45), verts=8, collection=collection, mat=marble)
    created.append(lantern_base)

    lantern_dome = H.add_sphere("Dome_Lantern_Cap", radius=0.15, location=(dx, dy, dz + 1.63), collection=collection, mat=dome_lead)
    created.append(lantern_dome)

    # 4. Gold peak cross
    cross_vert = H.add_cylinder("Dome_Cross_V", radius=0.015, depth=0.18, location=(dx, dy, dz + 1.74), verts=6, collection=collection, mat=gold)
    created.append(cross_vert)

    cross_horiz = H.add_cylinder("Dome_Cross_H", radius=0.012, depth=0.1, location=(dx, dy, dz + 1.82), verts=6, collection=collection, mat=gold)
    cross_horiz.rotation_euler = (0, math.radians(90), 0)
    created.append(cross_horiz)

    return created


def _create_colosseum(location: tuple[float, float, float], collection) -> list[bpy.types.Object]:
    """Procedurally build a beautiful arched Roman Colosseum wall landmark segment."""
    created = []
    stone = _create_material("M_Colosseum_Stone", (0.76, 0.7, 0.65, 1.0), roughness=0.8)

    cx, cy, cz = location

    # Create arched curved ruins segment
    arc_segments = 6
    radius = 4.5
    for s in range(arc_segments):
        angle = math.radians(110 + s * 14)
        ax = cx + math.cos(angle) * radius
        ay = cy + math.sin(angle) * radius

        # Double tiered arches
        for tier in (0, 1):
            h_offset = tier * 0.9
            block = H.add_box(f"Colosseum_Block_{s}_{tier}", size=(0.7, 0.35, 0.8), location=(ax, ay, cz + h_offset), collection=collection, mat=stone)
            block.rotation_euler = (0, 0, angle + math.radians(90))
            created.append(block)

    return created


def _create_cliffside_town(collection) -> list[bpy.types.Object]:
    """Procedurally build highly detailed colorful stacked Mediterranean houses climbing up the cliffs."""
    created = []

    # House wall materials
    terracotta_orange = _create_material("M_House_Orange", (0.85, 0.42, 0.22, 1.0), roughness=0.6)
    terracotta_red = _create_material("M_House_Red", (0.74, 0.22, 0.18, 1.0), roughness=0.6)
    pastel_yellow = _create_material("M_House_Yellow", (0.92, 0.78, 0.38, 1.0), roughness=0.7)
    pastel_pink = _create_material("M_House_Pink", (0.88, 0.58, 0.58, 1.0), roughness=0.7)
    pastel_cream = _create_material("M_House_Cream", (0.94, 0.9, 0.84, 1.0), roughness=0.7)

    roof_clay = _create_material("M_House_Roof", (0.58, 0.24, 0.18, 1.0), roughness=0.5)
    window_glass = _create_material("M_House_Glass", (0.1, 0.1, 0.15, 1.0), roughness=0.2)

    house_mats = (terracotta_orange, terracotta_red, pastel_yellow, pastel_pink, pastel_cream)

    # Stack houses climbing the hillside cliffs on the right
    house_slots = [
        # Ground level houses
        (3.2, 2.5, 0.4, 1.2, 0.9, 0.9, 0),
        (4.4, 2.2, 0.7, 1.0, 1.1, 1.0, 1),
        (5.5, 2.6, 1.1, 0.9, 0.9, 1.2, 2),
        # Mid-level vertical stacks
        (3.8, 3.4, 1.5, 1.1, 0.9, 1.1, 3),
        (4.9, 3.2, 2.0, 1.2, 1.0, 0.9, 4),
        (6.0, 3.6, 2.4, 0.8, 0.8, 1.3, 0),
        # High cliffside luxury villas
        (4.2, 4.4, 2.8, 1.0, 1.1, 0.95, 2),
        (5.4, 4.2, 3.3, 1.1, 0.9, 1.15, 1)
    ]

    for idx, (hx, hy, hz, sx, sy, sz, mat_idx) in enumerate(house_slots):
        wall_mat = house_mats[mat_idx]

        # 1. House main block
        house = H.add_box(f"Cliff_House_{idx}", size=(sx, sy, sz), location=(hx, hy, hz), collection=collection, mat=wall_mat)
        created.append(house)

        # 2. Gable Roof
        bpy.ops.mesh.primitive_cone_add(radius1=max(sx, sy) * 0.72, radius2=0.0, depth=0.35, location=(hx, hy, hz + sz + 0.1))
        roof = bpy.context.object
        roof.name = f"Cliff_House_Roof_{idx}"
        roof.rotation_euler = (0, 0, math.radians(45))
        roof.scale = (sx * 0.9, sy * 0.9, 1.0)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        roof.data.materials.append(roof_clay)
        H.link_to_collection(roof, collection)
        created.append(roof)

        # 3. Glass windows
        win_size = 0.14
        win_y = hy - sy/2.0 - 0.01
        for wx in (-sx * 0.25, sx * 0.25):
            for wz in (sz * 0.3, sz * 0.7):
                window = H.add_box(f"House_Win_{idx}_{wx:.1f}", size=(win_size, 0.02, win_size), location=(hx + wx, win_y, hz + wz), collection=collection, mat=window_glass)
                created.append(window)

    return created


def _create_sailboats(collection) -> list[bpy.types.Object]:
    """Procedurally build multiple elegant sailboats floating across the sea."""
    created = []
    hull_wood = _create_material("M_Boat_Hull", (0.9, 0.88, 0.85, 1.0), roughness=0.4)
    mast_wood = _create_material("M_Boat_Mast", (0.42, 0.28, 0.15, 1.0), roughness=0.7)
    sail_cloth = _create_material("M_Boat_Sail", (0.95, 0.95, 0.95, 1.0), roughness=0.8)

    boat_coords = [
        (-4.2, 0.5, 0.15, 0.8),
        (-6.0, 2.5, 0.25, 0.6),
        (-2.2, 3.2, 0.3, 0.5),
        (-5.0, -1.2, -0.05, 1.1)
    ]

    for idx, (bx, by, bz, scale) in enumerate(boat_coords):
        # 1. Boat Hull
        bpy.ops.mesh.primitive_cylinder_add(radius=0.18 * scale, depth=0.8 * scale, location=(bx, by, bz))
        hull = bpy.context.object
        hull.name = f"Sailboat_Hull_{idx}"
        hull.rotation_euler = (math.radians(90), 0, math.radians(65))
        hull.scale = (1.8, 1.0, 0.5)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        hull.data.materials.append(hull_wood)
        H.link_to_collection(hull, collection)
        created.append(hull)

        # 2. Mast
        mast = H.add_cylinder(f"Sailboat_Mast_{idx}", radius=0.015 * scale, depth=0.9 * scale, location=(bx, by, bz + 0.45 * scale), verts=6, collection=collection, mat=mast_wood)
        created.append(mast)

        # 3. Cone Sail
        bpy.ops.mesh.primitive_cone_add(radius1=0.22 * scale, radius2=0.0, depth=0.72 * scale, location=(bx + 0.05 * scale, by - 0.05 * scale, bz + 0.55 * scale))
        sail = bpy.context.object
        sail.name = f"Sailboat_Sail_{idx}"
        sail.rotation_euler = (0, 0, math.radians(25))
        sail.scale = (0.2, 1.8, 1.0)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        sail.data.materials.append(sail_cloth)
        H.link_to_collection(sail, collection)
        created.append(sail)

    return created


def op_create_layered_depth_scene(params: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct an ultra-premium high-fidelity 3D replica of the Italian Coastal scene in Blender.

    Generates beautiful balustrades, light blue Vespa, park bench set, statues, café sets,
    chalkboard menus, stacked colorful cliff houses, Pisa/Colosseum/Dome monuments,
    and highly-polished white marble tile walkways.
    """
    if params.get("clear_scene", True):
        for obj in list(bpy.context.scene.objects):
            bpy.data.objects.remove(obj, do_unlink=True)

    layers = params.get("layers", [])
    spacing = float(params.get("spacing", 3.2))

    # Collections
    parallax_coll = H.get_or_create_collection("Parallax_Planes")
    env_coll = H.get_or_create_collection("Environment")
    arch_coll = H.get_or_create_collection("Architecture")
    props_coll = H.get_or_create_collection("Props")

    created_objects = []

    has_sky = bool(params.get("has_sky", True))
    has_water = bool(params.get("has_water", True))

    # Check for empty markers inside the layers list
    for layer in layers:
        name_upper = layer.get("name", "").upper()
        if "SKY_EMPTY" in name_upper or "SKY" in name_upper and "EMPTY" in name_upper:
            has_sky = False
        if "SEA_EMPTY" in name_upper or "SEA" in name_upper and "EMPTY" in name_upper:
            has_water = False

    is_multi_layer = len(layers) > 2

    if is_multi_layer:
        print("Spawning individual transparent layer planes from PSB/PSD...")

        W = float(params.get("width") or 1920)
        H_val = float(params.get("height") or 1080)
        scale_factor = 20.0 / W  # Match 20m walkway span width

        for layer in layers:
            path_str = layer.get("path", "")
            if not path_str or not Path(path_str).exists():
                continue

            name = layer.get("name", "Layer")
            name_upper = name.upper()

            # Skip empty layer planes
            if "SKY_EMPTY" in name_upper or "SEA_EMPTY" in name_upper:
                print(f"Skipping empty plane generation for: {name}")
                continue

            left = float(layer.get("left") or 0)
            top = float(layer.get("top") or 0)
            width = float(layer.get("width") or W)
            height = float(layer.get("height") or H_val)
            dominant_color = layer.get("dominant_color", [0.6, 0.6, 0.6])

            # Compute centers relative to PSD center
            x_center = (left + width / 2.0) - W / 2.0
            z_center = H_val / 2.0 - (top + height / 2.0)

            # Convert to Blender coords
            plane_x = x_center * scale_factor
            plane_z = z_center * scale_factor
            plane_width = width * scale_factor
            plane_height = height * scale_factor

            # Stagger depth based on layer semantic roles
            if "CITY" in name_upper or "CLIFF" in name_upper or "GROUND" in name_upper:
                y_pos = spacing * 1.5
            elif "BALUSTRADE" in name_upper:
                y_pos = -2.8
            else:  # foreground scooter/bench/cafe
                y_pos = -2.1  # slightly in front of balustrade posts

            try:
                img = bpy.data.images.load(path_str, check_existing=True)
                mat = bpy.data.materials.new(f"M_Layer_{name}")
                mat.use_nodes = True
                bsdf = mat.node_tree.nodes.get("Principled BSDF")
                if bsdf is None:
                    bsdf = next((node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
                if bsdf is None:
                    bsdf = mat.node_tree.nodes.new(type="ShaderNodeBsdfPrincipled")

                tex = mat.node_tree.nodes.new(type="ShaderNodeTexImage")
                tex.image = img
                mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
                mat.node_tree.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])

                mat.blend_method = "BLEND"
                if hasattr(mat, "shadow_method"):
                    try:
                        mat.shadow_method = "NONE"
                    except AttributeError:
                        pass
                mat.diffuse_color = (*dominant_color[:3], 1.0)
            except Exception as e:
                print(f"Failed to create material for layer {name}: {e}")
                mat = H.make_material(f"M_Layer_{name}", (*dominant_color[:3], 1.0))

            bpy.ops.mesh.primitive_plane_add(
                location=(plane_x, y_pos, plane_z),
                rotation=(math.radians(90), 0.0, 0.0)
            )
            plane_obj = bpy.context.object
            plane_obj.name = f"Parallax_{name}"
            plane_obj.dimensions = (plane_width, 0.01, plane_height)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            plane_obj.data.materials.append(mat)
            H.link_to_collection(plane_obj, parallax_coll)
            created_objects.append(plane_obj.name)
    else:
        # Fallback to single backing reference plane
        for layer in layers:
            path_str = layer.get("path", "")
            if not path_str or not Path(path_str).exists():
                continue

            name = layer.get("Concept_Art", "Concept_Art")
            width = float(layer.get("width") or 1920)
            height = float(layer.get("height") or 1080)

            aspect = height / width
            plane_width = 24.0
            plane_height = plane_width * aspect

            try:
                img = bpy.data.images.load(path_str, check_existing=True)
                mat = bpy.data.materials.new("M_Concept_Reference")
                mat.use_nodes = True
                bsdf = mat.node_tree.nodes.get("Principled BSDF")
                if bsdf is None:
                    bsdf = next((node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
                if bsdf is None:
                    bsdf = mat.node_tree.nodes.new(type="ShaderNodeBsdfPrincipled")

                tex = mat.node_tree.nodes.new(type="ShaderNodeTexImage")
                tex.image = img
                mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
                mat.blend_method = "OPAQUE"
                mat.diffuse_color = (0.7, 0.7, 0.7, 1.0)
            except Exception as e:
                print(f"Failed to load concept plane: {e}")
                mat = H.make_material("M_Concept_Art", (0.7, 0.7, 0.7, 1.0))

            bpy.ops.mesh.primitive_plane_add(
                location=(0.0, spacing * 2.8, -0.8 + plane_height / 2.0),
                rotation=(math.radians(90), 0.0, 0.0)
            )
            plane_obj = bpy.context.object
            plane_obj.name = f"Concept_Art_Plane_{name}"
            plane_obj.dimensions = (plane_width, 0.01, plane_height)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            plane_obj.data.materials.append(mat)
            H.link_to_collection(plane_obj, parallax_coll)
            created_objects.append(plane_obj.name)

    # 2. Build 100% Precise Premium Italian Coastal 3D Environment!
    if params.get("spawn_3d_props", True):
        print("Reconstructing exact 3D Italian Coastal assets...")

        # Collect actual layer image file paths to run AI Image-to-3D reconstructions!
        layer_images = {}
        for layer in layers:
            name_upper = layer.get("name", "").upper()
            path_str = layer.get("path", "")
            if path_str and Path(path_str).exists():
                if "SCOOTER" in name_upper or "VESPA" in name_upper:
                    layer_images["vespa"] = path_str
                elif "POTTED" in name_upper or "PLANT" in name_upper:
                    layer_images["cypress"] = path_str
                elif "BENCH" in name_upper:
                    layer_images["bench"] = path_str
                elif "CAFE" in name_upper or "TABLE" in name_upper:
                    layer_images["cafe"] = path_str
                elif "BLACKBOARD" in name_upper or "SIGN" in name_upper:
                    layer_images["chalkboard"] = path_str
                elif "BUSTS" in name_upper or "STATUE" in name_upper:
                    layer_images["busts"] = path_str

        use_ai = bool(params.get("use_ai_reconstruction", False))

        # A. Polished White Marble Tiled Pavement Walkway
        walk_mat = _create_marble_pavement_material()
        walkway = H.add_box("walkway_pavement", size=(20.0, 3.2, 0.2), location=(0.0, -2.0, -0.2), collection=env_coll, mat=walk_mat)
        created_objects.append(walkway.name)

        # B. Classical Stone Balustrade railing
        print("Building classical balustrade railing...")
        balustrade = _create_balustrade(env_coll)
        created_objects.extend([obj.name for obj in balustrade])

        # C. 3D Light Blue Vespa (Parked on far left, X = -7.3, angled 30 degrees)
        vespa = []
        if use_ai and "vespa" in layer_images:
            vespa = _reconstruct_layer_with_ai("vespa", layer_images["vespa"], (-7.3, -2.0, 0.0), props_coll, target_height=1.2, yaw_deg=30.0)
        if not vespa:
            print("Building high-fidelity light blue Vespa...")
            vespa = _create_vespa((-7.3, -2.0, 0.0), props_coll, yaw_deg=30.0)
        created_objects.extend([obj.name for obj in vespa])

        # D. 3D Potted Cypress plant (X = -3.8)
        cypress_pot = []
        if use_ai and "cypress" in layer_images:
            cypress_pot = _reconstruct_layer_with_ai("cypress", layer_images["cypress"], (-3.8, -2.2, 0.0), props_coll, target_height=1.8, yaw_deg=0.0)
        if not cypress_pot:
            print("Building terracotta potted cypress...")
            cypress_pot = _create_potted_plant((-3.8, -2.2, 0.0), props_coll)
        created_objects.extend([obj.name for obj in cypress_pot])

        # E. 3D Sleeping floor cat next to the bench (X = -2.2)
        print("Building floor sleeping cat...")
        floor_cat = _create_sleeping_cat("Floor_Cat", (-2.2, -1.8, 0.0), props_coll)
        created_objects.extend([obj.name for obj in floor_cat])

        # F. 3D Wooden Bench, draped jersey, newspaper, and seat sleeping cat (X = -0.6)
        bench_set = []
        if use_ai and "bench" in layer_images:
            bench_set = _reconstruct_layer_with_ai("bench", layer_images["bench"], (-0.6, -2.2, 0.0), props_coll, target_height=1.1, yaw_deg=0.0)
        if not bench_set:
            print("Building park bench and draped blue jersey set...")
            bench_set = _create_bench_set((-0.6, -2.2, 0.0), props_coll)
        created_objects.extend([obj.name for obj in bench_set])

        # G. 3D Round Café table, two stools, wine and coffee set (X = 3.1)
        cafe_set = []
        if use_ai and "cafe" in layer_images:
            cafe_set = _reconstruct_layer_with_ai("cafe", layer_images["cafe"], (3.1, -2.2, 0.0), props_coll, target_height=1.1, yaw_deg=0.0)
        if not cafe_set:
            print("Building round café bistro set...")
            cafe_set = _create_cafe_set((3.1, -2.2, 0.0), props_coll)
        created_objects.extend([obj.name for obj in cafe_set])

        # H. 3D Wooden Easel Chalkboard sign (X = 6.2, angled -15 degrees)
        chalkboard = []
        if use_ai and "chalkboard" in layer_images:
            chalkboard = _reconstruct_layer_with_ai("chalkboard", layer_images["chalkboard"], (6.2, -2.2, 0.0), props_coll, target_height=1.1, yaw_deg=-15.0)
        if not chalkboard:
            print("Building slanted chalkboard sign...")
            chalkboard = _create_chalkboard((6.2, -2.2, 0.0), props_coll, yaw_deg=-15.0)
        created_objects.extend([obj.name for obj in chalkboard])

        # I. 3D Statue wooden crate with three white marble busts side-by-side (X = 8.5)
        statue_crate = []
        if use_ai and "busts" in layer_images:
            statue_crate = _reconstruct_layer_with_ai("busts", layer_images["busts"], (8.5, -2.2, 0.0), props_coll, target_height=0.75, yaw_deg=0.0)
        if not statue_crate:
            print("Building marble busts crate shelf...")
            statue_crate = _create_statue_crate((8.5, -2.2, 0.0), props_coll)
        created_objects.extend([obj.name for obj in statue_crate])

        # J. Stacked colorful Mediterranean Cliffside houses on right
        print("Building colorful Mediterranean cliff houses...")
        houses = _create_cliffside_town(arch_coll)
        created_objects.extend([obj.name for obj in houses])

        # K. Background Landmark Monuments (Colosseum, St. Peter's Dome, Pisa)
        print("Building Colosseum segment...")
        colosseum = _create_colosseum((3.4, 5.2, 3.8), arch_coll)
        created_objects.extend([obj.name for obj in colosseum])

        print("Building St. Peter's Basilica Dome...")
        dome_basilica = _create_st_peters_dome((4.8, 5.0, 4.8), arch_coll)
        created_objects.extend([obj.name for obj in dome_basilica])

        print("Building Leaning Tower of Pisa...")
        pisa = _create_leaning_tower((6.2, 4.8, 5.8), arch_coll)
        created_objects.extend([obj.name for obj in pisa])

        # L. Displaced Cliffs/Hills terrain
        print("Building displaced hillside cliffs...")
        terrain_mat = _create_material("M_Cliff_Terrain", (0.55, 0.48, 0.38, 1.0), roughness=0.9)
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=32, y_subdivisions=32, size=30.0, location=(4.0, 4.0, 0.0))
        terrain = bpy.context.object
        terrain.name = "Cliff_Terrain"
        terrain.data.materials.append(terrain_mat)
        H.link_to_collection(terrain, env_coll)
        created_objects.append(terrain.name)

        bm = bmesh.new()
        bm.from_mesh(terrain.data)
        for v in bm.verts:
            # Grid is centered at (4.0, 4.0, 0.0)
            world_x = 4.0 + v.co.x
            world_y = 4.0 + v.co.y

            if world_y < 1.0:
                # Foreground is flat and low (sunken under the terrace)
                v.co.z = -1.0
            else:
                # Midground and background cliffs
                if world_x > -2.0:
                    # Rises steep on the right
                    # Smoothly transition height based on world_y depth
                    y_factor = min((world_y - 1.0) / 4.0, 1.0)
                    v.co.z = ((world_x + 2.0) * 0.72 + (math.cos(world_x * 0.5) * math.sin(world_y * 0.5) * 0.8)) * y_factor - 1.0 * (1.0 - y_factor)
                else:
                    v.co.z = -1.0
        bm.to_mesh(terrain.data)
        bm.free()

        bpy.ops.object.select_all(action="DESELECT")
        terrain.select_set(True)
        bpy.context.view_layer.objects.active = terrain
        bpy.ops.object.shade_smooth()

        # M. Sailboats (bypassed if empty water sea is flagged)
        if has_water:
            print("Building floating sailboats...")
            boats = _create_sailboats(env_coll)
            created_objects.extend([obj.name for obj in boats])

        # N. Sea Water (bypassed if empty water sea is flagged)
        if has_water:
            print("Building azure sea surface...")
            water_mat = _create_material("M_Sea_Water", (0.05, 0.42, 0.65, 0.82), roughness=0.15)
            water_mat.blend_method = "BLEND"
            bpy.ops.mesh.primitive_plane_add(location=(-3.0, 2.0, -0.4))
            sea = bpy.context.object
            sea.name = "Sea_Water"
            sea.dimensions = (25.0, 25.0, 1.0)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            sea.data.materials.append(water_mat)
            H.link_to_collection(sea, env_coll)
            created_objects.append(sea.name)

    # 3. Setup Camera & Ambient / Key Lighting
    if has_sky:
        print("Setting up warm sunset sun and atmospheric key lighting...")
        bpy.ops.object.light_add(type="SUN", location=(-8.0, -12.0, 14.0))
        sun = bpy.context.object
        sun.name = "Sunset_Sun"
        sun.data.energy = 4.2
        sun.data.color = (1.0, 0.8, 0.55)
        H.link_to_collection(sun, H.get_or_create_collection("Lighting"))

        bpy.context.scene.world.use_nodes = True
        bg_node = bpy.context.scene.world.node_tree.nodes.get("Background")
        if bg_node:
            bg_node.inputs["Color"].default_value = (0.95, 0.72, 0.48, 1.0)
            bg_node.inputs["Strength"].default_value = 0.8
    else:
        print("Sky is empty. Setting up neutral ambient key lighting...")
        bpy.ops.object.light_add(type="SUN", location=(-5.0, -10.0, 12.0))
        sun = bpy.context.object
        sun.name = "Inspired_Sun"
        sun.data.energy = 3.5
        sun.data.color = (1.0, 1.0, 1.0)
        H.link_to_collection(sun, H.get_or_create_collection("Lighting"))

        bpy.context.scene.world.use_nodes = True
        bg_node = bpy.context.scene.world.node_tree.nodes.get("Background")
        if bg_node:
            bg_node.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
            bg_node.inputs["Strength"].default_value = 0.0

    # Camera setup (Positioned perfectly looking down the beautiful walkway center)
    bpy.ops.object.camera_add(location=(0.0, -6.6, 1.45))
    cam = bpy.context.object
    cam.name = "Cinematic_Coastal_Camera"
    cam.data.lens = 35

    direction = Vector((0.0, -1.0, 0.8)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    H.link_to_collection(cam, H.get_or_create_collection("Cameras"))

    bpy.context.scene.render.resolution_x = 1920
    bpy.context.scene.render.resolution_y = 1080

    # Save the blend file safely
    blend_path = str(Path(workspace_output("blends", "inspired_depth_scene.blend")).resolve())
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    # Trigger preview render
    preview_path = str(Path(workspace_output("renders", "inspired_scene_preview.png")).resolve())
    bpy.context.scene.render.filepath = preview_path
    try:
        bpy.ops.render.render(write_still=True)
    except Exception as e:
        print(f"Failed to render preview: {e}")

    return {
        "ok": True,
        "created_objects": [obj for obj in created_objects],
        "object_count": len(created_objects),
        "blend_path": blend_path,
        "preview_path": preview_path,
    }
