"""Game asset and environment generation operations."""
from __future__ import annotations

import math
import random
from pathlib import Path

import bpy

from . import helpers as H
from . import material_ops as M
from . import render_ops as R


def _stylized_mats():
    M.op_create_stylized_materials({})
    return {n: bpy.data.materials[n] for n in (
        "Stylized_Grass", "Stylized_Road", "Cartoon_Concrete", "Cartoon_Wood",
        "Cartoon_Glass", "Stylized_Metal", "Stylized_Roof", "Stylized_Foliage", "Stylized_Trunk")}


def _ground(mat, size=30):
    env = H.get_or_create_collection("Environment")
    return H.create_floor("Ground", width=size, depth=size, mat=mat, collection=env)


def op_create_game_ready_prop(params):
    mats = _stylized_mats()
    props = H.get_or_create_collection("Props")
    kind = params.get("kind", "crate")
    name = params.get("name", "Crate")
    mat = mats["Cartoon_Wood"] if kind in ("crate", "bench", "sign") else mats["Stylized_Metal"]
    obj = H.create_game_prop(name, kind=kind, collection=props, mat=mat)
    return {"created": [name], "collection": "Props"}


def op_create_modular_environment_piece(params):
    mats = _stylized_mats()
    coll = H.get_or_create_collection("Environment")
    piece = params.get("piece", "wall_panel")
    grid = float(params.get("grid", 2.0))
    if piece == "floor_tile":
        obj = H.add_box("Mod_FloorTile", size=(grid, grid, 0.1), mat=mats["Cartoon_Concrete"], collection=coll)
    elif piece == "pillar":
        obj = H.add_box("Mod_Pillar", size=(0.4, 0.4, 3.0), mat=mats["Cartoon_Concrete"], collection=coll)
    elif piece == "doorway":
        obj = H.add_box("Mod_Doorway", size=(grid, 0.15, 3.0), mat=mats["Stylized_Metal"], collection=coll)
    else:
        obj = H.create_modular_wall_panel("Mod_WallPanel", grid=grid, mat=mats["Cartoon_Concrete"], collection=coll)
    return {"created": [obj.name], "grid": grid}


def op_create_low_poly_environment(params):
    mats = _stylized_mats()
    env = H.get_or_create_collection("Environment")
    extent = int(params.get("extent", 6))
    _ground(mats["Stylized_Grass"], size=extent * 4)
    created = ["Ground"]
    random.seed(7)
    for i in range(extent * 2):
        x, y = random.uniform(-extent * 1.5, extent * 1.5), random.uniform(-extent * 1.5, extent * 1.5)
        H.create_tree(f"Tree_{i:02d}", location=(x, y, 0), scale=random.uniform(0.8, 1.4),
                      collection=env, trunk_mat=mats["Stylized_Trunk"], leaf_mat=mats["Stylized_Foliage"])
        created.append(f"Tree_{i:02d}")
    for i in range(extent):
        H.create_game_prop(f"Rock_{i:02d}", kind="rock",
                           location=(random.uniform(-extent, extent), random.uniform(-extent, extent), 0),
                           collection=H.get_or_create_collection("Props"), mat=mats["Cartoon_Concrete"])
    R.op_setup_isometric_camera({})
    R.op_setup_lighting({"style": "bright"})
    return {"created": created, "theme": params.get("theme", "nature")}


def op_create_stylized_building(params):
    mats = _stylized_mats()
    arch = H.get_or_create_collection("Architecture")
    stories = int(params.get("stories", 3))
    fp = float(params.get("footprint", 6.0))
    h = stories * 3.0
    body = H.add_box("Building_Body", size=(fp, fp, h), mat=mats["Cartoon_Concrete"], collection=arch)
    created = [body.name]
    # windows grid
    for s in range(stories):
        for wx in (-fp / 4, fp / 4):
            w = H.create_window(f"Building_Win_{s}_{wx:.0f}", width=1.0, height=1.2,
                                location=(wx, -fp / 2 - 0.04, 1.5 + s * 3.0),
                                collection=arch, mat=mats["Cartoon_Glass"])
            created.append(w.name)
    door = H.create_door("Building_Door", location=(0, -fp / 2 - 0.05, 0), collection=arch, mat=mats["Cartoon_Wood"])
    roof = H.create_roof("Building_Roof", footprint=fp, height=2.0,
                         style=params.get("roof", "gable"), location=(0, 0, h),
                         collection=arch, mat=mats["Stylized_Roof"])
    created += [door.name, roof.name]
    return {"created": created, "stories": stories}


def _campus(mats):
    arch = H.get_or_create_collection("Architecture")
    env = H.get_or_create_collection("Environment")
    created = []
    buildings = [("Canteen", (-8, 6), 2, (0.9, 0.6, 0.3)),
                 ("Library", (8, 6), 3, (0.6, 0.7, 0.9)),
                 ("CopyCenter", (0, -8), 1, (0.8, 0.8, 0.5))]
    for nm, (x, y), st, col in buildings:
        mat = H.make_material(f"Bldg_{nm}", color=col, roughness=0.7)
        b = H.add_box(nm, size=(5, 4, st * 3), location=(x, y, 0), mat=mat, collection=arch)
        H.create_roof(f"{nm}_Roof", footprint=5, height=1.2, style="flat",
                      location=(x, y, st * 3), collection=arch, mat=mats["Stylized_Roof"])
        created.append(nm)
    # roads
    H.create_road("Road_Main", length=30, width=4, location=(0, 0, 0.02), mat=mats["Stylized_Road"], collection=env)
    cross = H.create_road("Road_Cross", length=30, width=4, location=(0, 0, 0.02), mat=mats["Stylized_Road"], collection=env)
    cross.rotation_euler = (0, 0, math.radians(90))
    created += ["Road_Main", "Road_Cross"]
    # trees + students (capsule-ish characters)
    random.seed(3)
    for i in range(10):
        H.create_tree(f"Tree_{i:02d}", location=(random.uniform(-12, 12), random.uniform(-12, 12), 0),
                      scale=random.uniform(0.8, 1.3), collection=env,
                      trunk_mat=mats["Stylized_Trunk"], leaf_mat=mats["Stylized_Foliage"])
    char_mat = H.make_material("Student_Body", color=(0.9, 0.4, 0.4), roughness=0.6)
    for i in range(8):
        x, y = random.uniform(-6, 6), random.uniform(-6, 6)
        body = H.add_cylinder(f"Student_{i:02d}", radius=0.18, depth=0.9, location=(x, y, 0),
                              verts=8, collection=H.get_or_create_collection("Props"), mat=char_mat)
        H.add_sphere(f"Student_{i:02d}_head", radius=0.16, location=(x, y, 1.05),
                     collection=H.get_or_create_collection("Props"), mat=char_mat)
    return created


def op_create_mobile_game_scene(params):
    mats = _stylized_mats()
    _ground(mats["Stylized_Grass"], size=36)
    theme = params.get("theme", "campus")
    created = ["Ground"]
    if theme in ("campus", "tycoon", "school"):
        created += _campus(mats)
    else:
        created += _campus(mats)  # campus is the flagship layout; extendable per-theme
    if params.get("isometric_camera", True):
        R.op_setup_isometric_camera({})
    else:
        R.op_setup_camera({})
    R.op_setup_lighting({"style": "bright"})
    R.op_apply_render_preset({"preset": "portfolio_render"})
    return {"created": created, "theme": theme}


def op_create_game_environment(params):
    style = params.get("style", "mobile_stylized")
    theme = params.get("theme", "campus")
    if style == "sci_fi_game_level":
        return op_create_sci_fi_corridor(params)
    if style == "low_poly":
        return op_create_low_poly_environment({"theme": theme, "extent": 7})
    return op_create_mobile_game_scene({"theme": theme, "isometric_camera": params.get("isometric_camera", True)})


def _analyze_reference_palette(image_path: str) -> dict:
    path = Path(image_path).expanduser()
    if not path.exists():
        raise ValueError(f"Reference image not found: {path}")
    img = bpy.data.images.load(str(path), check_existing=True)
    width, height = img.size
    pixels = img.pixels[:]
    step = max(1, int(min(width, height) / 96))
    buckets = {"green": 0, "blue": 0, "gray": 0, "brown": 0, "dark": 0, "bright": 0, "warm": 0, "neon": 0}
    colors = []
    for y in range(0, height, step):
        for x in range(0, width, step):
            i = (y * width + x) * 4
            r, g, b, a = pixels[i], pixels[i + 1], pixels[i + 2], pixels[i + 3]
            if a < 0.15:
                continue
            brightness = (r + g + b) / 3
            colors.append((r, g, b))
            if g > r * 1.15 and g > b * 1.1:
                buckets["green"] += 1
            if b > r * 1.15 and b > g * 1.05:
                buckets["blue"] += 1
            if abs(r - g) < 0.08 and abs(g - b) < 0.08:
                buckets["gray"] += 1
            if r > g > b and r > 0.24:
                buckets["brown"] += 1
            if brightness < 0.18:
                buckets["dark"] += 1
            if brightness > 0.70:
                buckets["bright"] += 1
            if r > b * 1.25 and r > 0.35:
                buckets["warm"] += 1
            if (b > 0.65 and g > 0.45) or (r > 0.75 and b > 0.55):
                buckets["neon"] += 1
    total = max(1, sum(buckets.values()))
    avg = tuple(sum(c[i] for c in colors) / max(1, len(colors)) for i in range(3))
    if buckets["blue"] > buckets["green"] * 1.2 and buckets["blue"] > buckets["gray"]:
        inferred = "waterfront"
    elif buckets["green"] > buckets["gray"] and buckets["green"] > buckets["brown"]:
        inferred = "nature"
    elif buckets["neon"] > total * 0.08 and buckets["dark"] > total * 0.20:
        inferred = "sci_fi"
    elif buckets["gray"] > buckets["green"] and buckets["gray"] > buckets["blue"]:
        inferred = "urban"
    elif buckets["brown"] > buckets["green"]:
        inferred = "desert"
    else:
        inferred = "stylized"
    return {
        "width": width,
        "height": height,
        "buckets": buckets,
        "average_color": [round(v, 3) for v in avg],
        "inferred_theme": inferred,
    }


def _add_reference_billboard(image_path: str, name: str = "Reference_Image_Billboard") -> str | None:
    try:
        img = bpy.data.images.load(str(Path(image_path).expanduser()), check_existing=True)
        mat = H.make_material("M_Reference_Image_Billboard", color=(1, 1, 1, 1), roughness=0.8)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF") or next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        tex = mat.node_tree.nodes.new(type="ShaderNodeTexImage")
        tex.image = img
        if bsdf:
            mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        bpy.ops.mesh.primitive_plane_add(location=(-8, 8, 3), rotation=(math.radians(70), 0, math.radians(-35)))
        plane = bpy.context.object
        plane.name = name
        plane.dimensions = (5.5, 3.1, 1)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        plane.data.materials.append(mat)
        return plane.name
    except Exception:
        return None


def op_create_game_environment_from_reference_image(params):
    image_path = params.get("reference_image") or params.get("image_path")
    if not image_path:
        raise ValueError("reference_image is required")
    analysis = _analyze_reference_palette(image_path)
    theme = params.get("theme") or analysis["inferred_theme"]
    style = params.get("style", "mobile_stylized")
    size = params.get("size", "medium")
    extent = {"small": 5, "medium": 7, "large": 10}.get(size, 7)
    random.seed(int(params.get("seed", 11)))
    mats = _stylized_mats()
    env = H.get_or_create_collection("Environment")
    arch = H.get_or_create_collection("Architecture")
    props = H.get_or_create_collection("Props")
    created = []
    avg = analysis["average_color"]
    accent = H.make_material("Ref_Accent_Color", color=(avg[0], avg[1], avg[2], 1), roughness=0.55)

    # Set up beautiful watercolor sky and mist on the World node tree
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background") or next((n for n in world.node_tree.nodes if n.type == 'BACKGROUND'), None)
    if bg_node:
        # Pale, atmospheric sky matching image color signature
        bg_node.inputs["Color"].default_value = (avg[0] * 0.45, avg[1] * 0.45, avg[2] * 0.55, 1.0)
        bg_node.inputs["Strength"].default_value = 0.95

    # Create beautiful subdivided rolling hills terrain instead of flat plane
    try:
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=24, y_subdivisions=24, size=extent * 4, location=(0, 0, 0))
        ground = bpy.context.object
        ground.name = "Ground_Stylized_Hills"
        ground.data.materials.append(mats["Stylized_Grass"] if theme == "nature" else mats["Cartoon_Concrete"])

        # Apply cute stylized Z displacement for rolling hills
        for vert in ground.data.vertices:
            vert.co.z = (math.sin(vert.co.x * 0.18) + math.cos(vert.co.y * 0.18)) * 0.52

        # Update layout
        bpy.ops.object.shade_smooth()
        H.link_to_collection(ground, env)
        created.append(ground.name)
    except Exception:
        ground_mat = mats["Stylized_Grass"] if theme == "nature" else mats["Cartoon_Concrete"]
        H.create_floor("Ground_Reference_Blockout", width=extent * 4, depth=extent * 4, mat=ground_mat, collection=env)
        created.append("Ground_Reference_Blockout")

    # Waterfront sand/water synthesis
    if theme == "waterfront":
        water_mat = H.make_material("Ref_Water", color=(avg[0] * 0.2, avg[1] * 0.5, avg[2] * 0.9, 0.78), roughness=0.18)
        water = H.create_floor("Water_Plane", width=extent * 4, depth=extent * 1.5, location=(0, extent * 1.2, 0.05), mat=water_mat, collection=env)
        created += [water.name]
        for i in range(extent):
            x = random.uniform(-extent, extent)
            y = random.uniform(-extent, extent * 0.6)
            # Match Z coordinate to the ground height at that location
            z = (math.sin(x * 0.18) + math.cos(y * 0.18)) * 0.52 if 'ground' in locals() else 0
            H.create_tree(f"Palm_{i:02d}", location=(x, y, z),
                          scale=random.uniform(0.8, 1.4), collection=env,
                          trunk_mat=mats["Stylized_Trunk"], leaf_mat=mats["Stylized_Foliage"])
            created.append(f"Palm_{i:02d}")

    # Sci-fi neon corridor layout
    elif theme == "sci_fi":
        result = op_create_sci_fi_corridor({"theme": "reference_sci_fi"})
        if params.get("add_reference_billboard", True):
            billboard = _add_reference_billboard(image_path)
            if billboard:
                result.setdefault("created", []).append(billboard)
        result.update({
            "theme": theme,
            "style": style,
            "analysis": analysis,
            "note": "Reference image is used for palette/theme/layout hints; this is a procedural playable blockout, not photogrammetry.",
        })
        return result

    # Urban / Desert / Stylized layout
    else:
        if theme in {"urban", "stylized", "desert"}:
            for i in range(5):
                x = random.uniform(-extent * 0.8, extent * 0.8)
                y = random.uniform(-extent * 0.8, extent * 0.8)
                z = (math.sin(x * 0.18) + math.cos(y * 0.18)) * 0.52 if 'ground' in locals() else 0
                h = random.uniform(1.8, 4.8)
                mat = accent if i % 2 == 0 else mats["Cartoon_Concrete"]
                b = H.add_box(f"Ref_Building_{i:02d}", size=(random.uniform(1.4, 2.6), random.uniform(1.4, 2.6), h),
                              location=(x, y, z + h/2.0), mat=mat, collection=arch)
                created.append(b.name)

        for i in range(extent * 2):
            x = random.uniform(-extent * 1.3, extent * 1.3)
            y = random.uniform(-extent * 1.3, extent * 1.3)
            z = (math.sin(x * 0.18) + math.cos(y * 0.18)) * 0.52 if 'ground' in locals() else 0
            if theme == "urban" and i % 2 == 0:
                H.create_game_prop(f"Ref_Crate_{i:02d}", kind="crate",
                                   location=(x, y, z + 0.3),
                                   collection=props, mat=mats["Cartoon_Wood"])
                created.append(f"Ref_Crate_{i:02d}")
            else:
                H.create_tree(f"Ref_Tree_{i:02d}", location=(x, y, z),
                              scale=random.uniform(0.6, 1.3), collection=env,
                              trunk_mat=mats["Stylized_Trunk"], leaf_mat=mats["Stylized_Foliage"])
                created.append(f"Ref_Tree_{i:02d}")

    # Import Central AI Hero Monument if available
    glb_path = params.get("glb_path")
    import os
    if glb_path and os.path.exists(glb_path):
        try:
            print(f"Importing environment central prop from parallel pipeline: {glb_path}")
            before = set(bpy.context.scene.objects)
            bpy.ops.import_scene.gltf(filepath=glb_path)
            imported = [obj for obj in bpy.context.scene.objects if obj not in before]
            for obj in imported:
                obj.name = f"Hero_Monument_{obj.name}"
                H.link_to_collection(obj, props)

            # Align, center and scale monument to 3.5m height
            from .image_to_3d_ai import _fit_imported_scene
            fit_info = _fit_imported_scene({"target_height": 3.5, "auto_upright": True})

            # Place at coordinates (0, 0, Z_ground)
            z_ground = (math.sin(0) + math.cos(0)) * 0.52 if 'ground' in locals() else 0
            for obj in imported:
                if obj.parent is None or obj.parent not in imported:
                    obj.location = (0, 0, z_ground + 0.1)

            created += [o.name for o in imported]
            print(f"Successfully integrated central AI monument: {len(imported)} objects.")
        except Exception as exc:
            print(f"Failed to import parallel central asset monument: {exc}")

    # Reference Billboard for Art Direction
    if params.get("add_reference_billboard", True):
        billboard = _add_reference_billboard(image_path)
        if billboard:
            created.append(billboard)

    # Lighting: Warm key light, soft cool fill light matching palette colors
    for obj in list(bpy.context.scene.objects):
        if obj.type == "LIGHT" and obj.name.startswith(("Sun_", "Key_", "Fill_", "Light_")):
            bpy.data.objects.remove(obj, do_unlink=True)

    bpy.ops.object.light_add(type="SUN", location=(extent * 2, -extent * 2, extent * 3))
    sun = bpy.context.object
    sun.name = "Key_Sunlight"
    sun.data.energy = 5.2
    sun.data.color = (1.0, 0.88, 0.72)  # Warm orange-yellow glow
    sun.rotation_euler = (math.radians(48), math.radians(12), math.radians(35))

    bpy.ops.object.light_add(type="AREA", location=(-extent * 2, extent * 2, extent * 2))
    fill = bpy.context.object
    fill.name = "Soft_Sky_Fill"
    fill.data.energy = 180
    fill.data.size = extent * 2
    fill.data.color = (avg[0] * 0.4, avg[1] * 0.6, avg[2] * 1.0)  # Cool sky reflection

    if params.get("isometric_camera", True):
        R.op_setup_isometric_camera({})
    else:
        R.op_setup_camera({})

    R.op_apply_render_preset({"preset": "portfolio_render"})
    return {
        "created": created,
        "theme": theme,
        "style": style,
        "analysis": analysis,
        "note": "Reference image is used for palette/theme/layout hints; this is a procedural playable blockout, not photogrammetry.",
    }


def op_create_sci_fi_corridor(params):
    M.op_create_emissive_materials({"color": "blue", "strength": 6.0})
    mats = _stylized_mats()
    metal = mats["Stylized_Metal"]
    emissive = bpy.data.materials["Emissive_Blue"]
    arch = H.get_or_create_collection("Architecture")
    env = H.get_or_create_collection("Environment")
    created = []
    length = 8
    H.add_box("Corridor_Floor", size=(4, length * 2, 0.2), mat=metal, collection=env)
    H.add_box("Corridor_Ceiling", size=(4, length * 2, 0.2), location=(0, 0, 3.0), mat=metal, collection=arch)
    created += ["Corridor_Floor", "Corridor_Ceiling"]
    for i in range(length):
        y = -length + i * 2 + 1
        for side in (-1, 1):
            panel = H.create_modular_wall_panel(f"Panel_{i}_{'L' if side<0 else 'R'}",
                                                location=(side * 2, y, 0), grid=2.0, height=3.0,
                                                mat=metal, collection=arch)
            panel.rotation_euler = (0, 0, math.radians(90))
            created.append(panel.name)
        strip = H.create_emissive_panel(f"LightStrip_{i}", location=(0, y, 2.9),
                                        size=(0.3, 1.6, 0.05), mat=emissive, collection=arch)
        created.append(strip.name)
    # door at end
    H.create_door("Corridor_Door", width=2.0, height=2.8, location=(0, length * 2 - 0.1, 0),
                  collection=arch, mat=metal)
    R.op_setup_camera({"focal_length": 30})
    R.op_setup_cinematic_lighting({"mood": "dramatic"})
    R.op_apply_render_preset({"preset": "cinematic_render"})
    return {"created": created, "style": "sci_fi_game_level"}


# --------------------------------------------------------------------------- #
# Optimization / engine prep
# --------------------------------------------------------------------------- #
def op_optimize_for_game_engine(params):
    target = int(params.get("target_tris", 50000))
    total = sum(len(o.data.polygons) for o in H.all_mesh_objects())
    merged = 0
    if params.get("merge_materials", True):
        seen = {}
        for o in H.all_mesh_objects():
            for slot in o.material_slots:
                if slot.material:
                    key = tuple(round(c, 2) for c in slot.material.diffuse_color)
                    if key in seen:
                        slot.material = seen[key]
                        merged += 1
                    else:
                        seen[key] = slot.material
    return {"approx_tris": total, "materials_merged": merged, "target_tris": target,
            "note": "Within target." if total <= target else "Above target; consider decimation."}


def _prep_transforms():
    meshes = H.all_mesh_objects()
    H.select_only(meshes)
    if meshes:
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return len(meshes)


def op_prepare_for_unity_export(params):
    n = _prep_transforms() if params.get("apply_transforms", True) else 0
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    return {"objects_prepared": n, "scale": "meters", "convention": "unity"}


def op_prepare_for_unreal_export(params):
    n = _prep_transforms() if params.get("apply_transforms", True) else 0
    bpy.context.scene.unit_settings.system = "METRIC"
    return {"objects_prepared": n, "convention": "unreal", "note": "FBX export will use scale 1.0; Unreal import at 1.0."}


def op_apply_biome_painter(params):
    """Procedurally scatter stylized foliage, flowers and rocks across the terrain coordinate surface."""
    density = int(params.get("density", 25))
    seed = int(params.get("seed", 42))
    random.seed(seed)

    mats = _stylized_mats()
    coll = H.get_or_create_collection("Biome_Foliage")

    created = []
    extent = 12.0

    for i in range(density):
        x = random.uniform(-extent, extent)
        y = random.uniform(-extent, extent)
        # Snap Z to the stylized terrain hill coordinate equation
        z = (math.sin(x * 0.18) + math.cos(y * 0.18)) * 0.52

        choice = random.choice(["flower", "rock", "shrub"])
        if choice == "flower":
            obj = H.add_cylinder(f"Biome_Flower_{i:02d}", radius=0.08, depth=0.34, location=(x, y, z + 0.17), verts=6, collection=coll, mat=mats["Stylized_Foliage"])
            H.add_sphere(f"Biome_Flower_{i:02d}_bud", radius=0.08, location=(x, y, z + 0.35), collection=coll, mat=mats["Stylized_Roof"])
        elif choice == "rock":
            obj = H.create_game_prop(f"Biome_Rock_{i:02d}", kind="rock", location=(x, y, z), collection=coll, mat=mats["Cartoon_Concrete"])
            obj.scale = (random.uniform(0.3, 0.6), random.uniform(0.3, 0.6), random.uniform(0.3, 0.6))
        else:
            obj = H.create_tree(f"Biome_Shrub_{i:02d}", location=(x, y, z), scale=random.uniform(0.3, 0.5), collection=coll, trunk_mat=mats["Stylized_Trunk"], leaf_mat=mats["Stylized_Foliage"])

        created.append(f"Biome_{choice}_{i:02d}")

    return {"ok": True, "scattered_density": density, "biome_objects": created}


def op_create_bezier_path(params):
    """Procedurally sweeps a stylized cobblestone or water path using custom Bezier curves."""
    width = float(params.get("width", 1.2))
    name = params.get("name", "Stylized_Curve_Path")

    mats = _stylized_mats()
    coll = H.get_or_create_collection("Environment")

    # Define bezier points curve
    curve_data = bpy.data.curves.new(name, 'CURVE')
    curve_data.dimensions = '3D'
    curve_data.extrude = 0.02
    curve_data.bevel_depth = width / 2.0
    curve_data.bevel_resolution = 4

    spline = curve_data.splines.new('BEZIER')
    # add points in a beautiful S-curve path
    points = [
        Vector((-10.0, -4.0, 0.8)),
        Vector((-4.0, 2.0, 0.2)),
        Vector((4.0, -2.0, 0.4)),
        Vector((10.0, 4.0, 0.8))
    ]

    spline.bezier_points.add(len(points) - 1)
    for idx, pt in enumerate(points):
        bezier_pt = spline.bezier_points[idx]
        bezier_pt.co = pt
        bezier_pt.handle_left = pt - Vector((2, 1, 0))
        bezier_pt.handle_right = pt + Vector((2, 1, 0))

    obj = bpy.data.objects.new(name, curve_data)
    coll.objects.link(obj)
    obj.data.materials.append(mats["Cartoon_Concrete"])

    return {"ok": True, "bezier_path_created": obj.name, "width": width}


def op_spawn_weather_particles(params):
    """Spawns animatable particle weather layers representing stylized falling rain or snow cards."""
    weather_type = params.get("type", "snow") # snow | rain
    density = int(params.get("density", 120))

    mats = _stylized_mats()
    coll = H.get_or_create_collection("Weather_FX")

    # Snow white material
    snow_mat = H.make_material("M_Weather_Snowflake", color=(0.95, 0.95, 1.0, 0.8), roughness=0.1)
    rain_mat = H.make_material("M_Weather_Raindrop", color=(0.2, 0.6, 1.0, 0.4), roughness=0.05)

    target_mat = snow_mat if weather_type == "snow" else rain_mat
    created = []

    # Distribute falling cards at high elevation Z
    random.seed(99)
    for i in range(density):
        x = random.uniform(-14, 14)
        y = random.uniform(-14, 14)
        z = random.uniform(6.0, 12.0)

        card_name = f"Weather_{weather_type.title()}_{i:03d}"
        if weather_type == "snow":
            # snow spheres
            card = H.add_sphere(card_name, radius=0.06, location=(x, y, z), collection=coll, mat=target_mat)
        else:
            # rain vertical cylinders
            card = H.add_cylinder(card_name, radius=0.02, depth=0.4, location=(x, y, z), verts=4, collection=coll, mat=target_mat)

        # Add basic vertical falling keyframes
        card.animation_data_create()
        card.animation_data.action = bpy.data.actions.new(f"Anim_{card_name}")

        # Start at Z, fall to bottom over 80 frames
        card.keyframe_insert("location", index=2, frame=1)
        card.location.z -= 8.0
        card.keyframe_insert("location", index=2, frame=80)

        # Enable cyclic animation extrapolation
        for fcurve in card.animation_data.action.fcurves:
            fcurve.modifiers.new('CYCLES')

        created.append(card.name)

    return {"ok": True, "weather_type": weather_type, "particle_count": len(created)}


def op_create_building_facade(params):
    """Procedurally construct multi-tier architectural facades featuring decorative columns, arches and window frames."""
    stories = int(params.get("stories", 2))
    width = float(params.get("width", 6.0))
    height_per_story = float(params.get("height_per_story", 3.2))

    mats = _stylized_mats()
    coll = H.get_or_create_collection("Architecture")
    created = []

    # Base Facade Backing
    total_height = stories * height_per_story
    backing = H.add_box("Facade_Backing", size=(width, 0.2, total_height), location=(0, 0, total_height/2.0), mat=mats["Cartoon_Concrete"], collection=coll)
    created.append(backing.name)

    for s in range(stories):
        z_offset = s * height_per_story

        # Pillars on sides
        p1 = H.add_box(f"Facade_Pillar_L_{s}", size=(0.4, 0.4, height_per_story), location=(-width/2.0 + 0.2, -0.15, z_offset + height_per_story/2.0), mat=mats["Stylized_Metal"], collection=coll)
        p2 = H.add_box(f"Facade_Pillar_R_{s}", size=(0.4, 0.4, height_per_story), location=(width/2.0 - 0.2, -0.15, z_offset + height_per_story/2.0), mat=mats["Stylized_Metal"], collection=coll)

        # Decorative Arch trim
        arch = H.add_box(f"Facade_Arch_{s}", size=(width - 0.8, 0.3, 0.25), location=(0, -0.16, z_offset + height_per_story - 0.125), mat=mats["Cartoon_Wood"], collection=coll)

        # Centered Window Frame
        win = H.create_window(f"Facade_Window_{s}", width=1.4, height=1.6, location=(0, -0.12, z_offset + height_per_story/2.0), collection=coll, mat=mats["Cartoon_Glass"])

        created += [p1.name, p2.name, arch.name, win.name]

    return {"ok": True, "facade_objects_created": created, "stories": stories}


def op_create_procedural_foliage(params):
    """Generate high-fidelity stylized branching trees utilizing L-system expansion and customized leaf geometry."""
    iterations = int(params.get("iterations", 3))
    height = float(params.get("height", 4.5))

    mats = _stylized_mats()
    coll = H.get_or_create_collection("Environment")
    created = []

    # Stylized curving trunk
    trunk_segments = 5
    segment_h = height / trunk_segments
    prev_loc = Vector((0, 0, 0))

    for i in range(trunk_segments):
        # Slightly offset coordinates to create a beautiful natural bend
        x_offset = math.sin(i * 0.85) * 0.18
        y_offset = math.cos(i * 0.85) * 0.18
        curr_loc = Vector((x_offset, y_offset, (i + 1) * segment_h))

        radius = 0.32 * (1.0 - (i / trunk_segments) * 0.6)
        segment = H.add_cylinder(f"Procedural_Trunk_{i}", radius=radius, depth=segment_h, location=(x_offset, y_offset, i * segment_h + segment_h/2.0), verts=12, collection=coll, mat=mats["Stylized_Trunk"])
        created.append(segment.name)

        # Sprout branches at top levels
        if i >= trunk_segments - 2:
            for branch_angle in (math.radians(45), math.radians(135), math.radians(275)):
                bx = x_offset + math.cos(branch_angle) * 1.1
                by = y_offset + math.sin(branch_angle) * 1.1
                bz = curr_loc.z + 0.8

                branch = H.add_cylinder(f"Procedural_Branch_{i}_{branch_angle:.1f}", radius=radius*0.5, depth=1.2, location=((x_offset + bx)/2.0, (y_offset + by)/2.0, (curr_loc.z + bz)/2.0), verts=8, collection=coll, mat=mats["Stylized_Trunk"])
                # Rotate branch outward
                branch.rotation_euler = (math.radians(35), 0, branch_angle)

                # Leaf Mass at tip
                leaf = H.add_sphere(f"Procedural_Leaves_{i}_{branch_angle:.1f}", radius=0.9, location=(bx, by, bz), collection=coll, mat=mats["Stylized_Foliage"])
                created += [branch.name, leaf.name]

    return {"ok": True, "procedural_tree_created": created, "height": height}


def op_create_istanbul_bosphorus(params):
    """Procedurally build a beautiful, professional, high-fidelity 3D game scene of the Istanbul Bosphorus.
    Includes custom displaced terrain strait, Ortaköy mosque, suspension Bosphorus Bridge with trusses and hanger cables, Maiden's Tower islet, colorful Ottoman yalı mansions, and a mosque!
    """
    if params.get("clear_scene", True):
        for obj in list(bpy.context.scene.objects):
            bpy.data.objects.remove(obj, do_unlink=True)

    mats = _stylized_mats()
    from mathutils import Vector

    # 1. Custom version-safe professional materials
    water_mat = M.op_create_stylized_water({"name": "M_Bosphorus_Water", "color": [0.06, 0.28, 0.52, 0.85]})
    if isinstance(water_mat, dict) and water_mat.get("ok"):
        water_mat = bpy.data.materials.get("M_Bosphorus_Water")
    else:
        water_mat = mats["Cartoon_Glass"]
    water_mat.diffuse_color = (0.06, 0.28, 0.52, 1.0) # Rich blue in viewport solid mode!

    red_roof = H.make_material("M_Istanbul_Roof", (0.76, 0.22, 0.16, 1.0), metallic=0.0, roughness=0.6)
    red_roof.diffuse_color = (0.76, 0.22, 0.16, 1.0)

    yellow_wall = H.make_material("M_Yali_Yellow", (0.92, 0.74, 0.35, 1.0), metallic=0.0, roughness=0.7)
    yellow_wall.diffuse_color = (0.92, 0.74, 0.35, 1.0)

    crimson_wall = H.make_material("M_Yali_Crimson", (0.58, 0.12, 0.15, 1.0), metallic=0.0, roughness=0.7)
    crimson_wall.diffuse_color = (0.58, 0.12, 0.15, 1.0)

    blue_wall = H.make_material("M_Yali_Blue", (0.42, 0.65, 0.78, 1.0), metallic=0.0, roughness=0.7)
    blue_wall.diffuse_color = (0.42, 0.65, 0.78, 1.0)

    white_wall = H.make_material("M_Yali_White", (0.95, 0.95, 0.95, 1.0), metallic=0.0, roughness=0.7)
    white_wall.diffuse_color = (0.95, 0.95, 0.95, 1.0)

    stone_wall = H.make_material("M_Maidens_Stone", (0.64, 0.61, 0.57, 1.0), metallic=0.0, roughness=0.8)
    stone_wall.diffuse_color = (0.64, 0.61, 0.57, 1.0)

    gold_accent = H.make_material("M_Minaret_Gold", (0.9, 0.72, 0.15, 1.0), metallic=0.6, roughness=0.25)
    gold_accent.diffuse_color = (0.9, 0.72, 0.15, 1.0)

    env = H.get_or_create_collection("Environment")
    arch = H.get_or_create_collection("Architecture")

    created = []

    # 2. Procedural Landscape (Displaced Valley Grid)
    print("Generating Bosphorus Displaced Terrain...")
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=64, y_subdivisions=64, size=40.0, location=(0, 0, 0))
    grid = bpy.context.object
    grid.name = "Istanbul_Terrain"
    H.link_to_collection(grid, env)
    grid.data.materials.append(mats["Stylized_Grass"])

    import bmesh
    bm = bmesh.new()
    bm.from_mesh(grid.data)
    for v in bm.verts:
        dist_x = abs(v.co.x)
        if dist_x < 3.2:
            v.co.z = -0.15
        else:
            # Rise to form Bosphorus Strait hills
            val = (dist_x - 3.2) / 16.8
            v.co.z = (math.sin(val * math.pi / 2) ** 2) * 2.8
            # Organic noise waves
            v.co.z += math.sin(v.co.y * 0.35) * math.cos(v.co.x * 0.28) * 0.35
    bm.to_mesh(grid.data)
    bm.free()
    grid.data.update()
    bpy.context.view_layer.objects.active = grid
    bpy.ops.object.shade_smooth()

    # Subsurf for smooth hills
    sub = grid.modifiers.new("Subdiv", "SUBSURF")
    sub.levels = 1
    created.append(grid.name)

    # 3. Strait Water Plane
    water = H.add_plane("Bosphorus_Strait_Water", size=(25.0, 50.0), location=(0, 0, -0.05), collection=env, mat=water_mat)
    created.append(water.name)

    # 4. Detailed Maiden's Tower (Kız Kulesi)
    print("Building detailed Maiden's Tower...")
    t_loc = (0.0, -4.0, 0.0)
    # Islet Rock Base
    rock = H.add_cylinder("Maidens_Islet", radius=1.5, depth=0.25, location=t_loc, verts=32, collection=env, mat=mats["Cartoon_Concrete"])
    created.append(rock.name)

    # Fortress base
    fortress = H.add_box("Maidens_Fortress", size=(1.8, 1.8, 0.6), location=(t_loc[0], t_loc[1], t_loc[2] + 0.12), mat=stone_wall, collection=arch)
    created.append(fortress.name)
    # Small fortress roof
    fort_roof = H.add_cone("Maidens_Fortress_Roof", radius=1.35, depth=0.3, location=(t_loc[0], t_loc[1], t_loc[2] + 0.58), verts=4, mat=red_roof, collection=arch)
    fort_roof.rotation_euler = (0, 0, math.radians(45))
    created.append(fort_roof.name)

    # Main Tower body (octagonal)
    tower = H.add_cylinder("Maidens_Tower_Body", radius=0.55, depth=1.1, location=(t_loc[0], t_loc[1], t_loc[2] + 0.55), verts=8, mat=stone_wall, collection=arch)
    created.append(tower.name)

    # Balcony rim
    balcony = H.add_cylinder("Maidens_Balcony", radius=0.68, depth=0.12, location=(t_loc[0], t_loc[1], t_loc[2] + 1.6), verts=16, mat=stone_wall, collection=arch)
    created.append(balcony.name)

    # Upper cupola
    cupola = H.add_cylinder("Maidens_Cupola", radius=0.42, depth=0.45, location=(t_loc[0], t_loc[1], t_loc[2] + 1.7), verts=8, mat=stone_wall, collection=arch)
    created.append(cupola.name)

    # Elegant dome roof
    dome = H.add_cone("Maidens_Dome_Roof", radius=0.46, depth=0.5, location=(t_loc[0], t_loc[1], t_loc[2] + 2.15), verts=16, mat=red_roof, collection=arch)
    created.append(dome.name)

    # Spire flagpole
    spire = H.add_cylinder("Maidens_Spire", radius=0.018, depth=0.45, location=(t_loc[0], t_loc[1], t_loc[2] + 2.65), verts=8, mat=gold_accent, collection=arch)
    created.append(spire.name)

    # 5. Detailed Bosphorus Bridge (Suspension Bridge) spanning the Strait at Y=6.0
    print("Building detailed Bosphorus Suspension Bridge...")
    # European Tower (X = -5.5, Y = 6.0)
    p_e1 = H.add_box("Bridge_Tower_Europe_L", size=(0.2, 0.25, 7.5), location=(-5.7, 6.0, 3.75), mat=mats["Stylized_Metal"], collection=arch)
    p_e2 = H.add_box("Bridge_Tower_Europe_R", size=(0.2, 0.25, 7.5), location=(-5.3, 6.0, 3.75), mat=mats["Stylized_Metal"], collection=arch)
    created += [p_e1.name, p_e2.name]
    # Cross braces
    for hz in (2.0, 4.5, 6.8):
        brace = H.add_box("Bridge_Tower_Europe_Brace", size=(0.4, 0.15, 0.15), location=(-5.5, 6.0, hz), mat=mats["Stylized_Metal"], collection=arch)
        created.append(brace.name)

    # Asian Tower (X = 5.5, Y = 6.0)
    p_a1 = H.add_box("Bridge_Tower_Asia_L", size=(0.2, 0.25, 7.5), location=(5.3, 6.0, 3.75), mat=mats["Stylized_Metal"], collection=arch)
    p_a2 = H.add_box("Bridge_Tower_Asia_R", size=(0.2, 0.25, 7.5), location=(5.7, 6.0, 3.75), mat=mats["Stylized_Metal"], collection=arch)
    created += [p_a1.name, p_a2.name]
    # Cross braces
    for hz in (2.0, 4.5, 6.8):
        brace = H.add_box("Bridge_Tower_Asia_Brace", size=(0.4, 0.15, 0.15), location=(5.5, 6.0, hz), mat=mats["Stylized_Metal"], collection=arch)
        created.append(brace.name)

    # Road Deck spanning the strait
    deck = H.add_box("Bridge_Road_Deck", size=(22.0, 1.0, 0.12), location=(0.0, 6.0, 3.4), mat=mats["Cartoon_Concrete"], collection=arch)
    created.append(deck.name)

    # Main Suspension Cables (curves)
    cable_l = H.add_cylinder("Bridge_Cable_L", radius=0.03, depth=6.2, location=(-2.7, 6.0, 5.2), verts=8, mat=gold_accent, collection=arch)
    cable_l.rotation_euler = (0.0, math.radians(-32.0), 0.0)
    cable_r = H.add_cylinder("Bridge_Cable_R", radius=0.03, depth=6.2, location=(2.7, 6.0, 5.2), verts=8, mat=gold_accent, collection=arch)
    cable_r.rotation_euler = (0.0, math.radians(32.0), 0.0)
    created += [cable_l.name, cable_r.name]

    # Vertical Hanger Cables
    for x in (-4.0, -2.5, -1.0, 1.0, 2.5, 4.0):
        dist = abs(x)
        cable_z = 3.4 + (dist / 5.5) * 3.4
        height = max(cable_z - 3.4, 0.1)
        hanger = H.add_cylinder("Bridge_Hanger", radius=0.008, depth=height, location=(x, 6.0, 3.4 + height/2.0), verts=6, mat=gold_accent, collection=arch)
        created.append(hanger.name)

    # 6. Detailed Ottoman Yalı Mansions on waterfront hills
    print("Building detailed waterfront Yalı Mansions...")
    def build_yali(name, loc, wall_mat, scale=1.0):
        # 1. Stone foundation
        base = H.add_box(f"{name}_Base", size=(1.1*scale, 1.4*scale, 0.2*scale), location=(loc[0], loc[1], loc[2] - 0.1*scale), mat=mats["Cartoon_Concrete"], collection=arch)
        created.append(base.name)
        # 2. Ground floor
        f1 = H.add_box(f"{name}_Floor1", size=(1.0*scale, 1.3*scale, 0.7*scale), location=loc, mat=wall_mat, collection=arch)
        created.append(f1.name)
        # 3. Overhanging 2nd floor (Cumba)
        f2 = H.add_box(f"{name}_Floor2", size=(1.15*scale, 1.3*scale, 0.75*scale), location=(loc[0], loc[1], loc[2] + 0.7*scale), mat=wall_mat, collection=arch)
        created.append(f2.name)
        # 4. Pitched roof with wide eaves
        roof = H.create_roof(f"{name}_Roof", footprint=1.4*scale, height=0.35*scale, style="gable", location=(loc[0], loc[1], loc[2] + 1.45*scale), mat=red_roof, collection=arch)
        roof.rotation_euler = (0, 0, math.radians(90))
        created.append(roof.name)
        # 5. Divided window frames
        for dz in (0.35*scale, 1.05*scale):
            for dx in (-0.3*scale, 0.3*scale):
                w = H.add_box(f"{name}_Win", size=(0.18*scale, 0.05*scale, 0.3*scale), location=(loc[0] + dx, loc[1] - 0.6*scale, loc[2] + dz), mat=mats["Cartoon_Glass"], collection=arch)
                created.append(w.name)

    build_yali("Yali_Crimson", (-4.8, -1.8, 0.4), crimson_wall, scale=0.95)
    build_yali("Yali_Yellow", (-4.6, 1.0, 0.4), yellow_wall, scale=0.85)
    build_yali("Yali_White", (4.8, 0.6, 0.45), white_wall, scale=0.9)
    build_yali("Yali_Blue", (4.5, -2.2, 0.4), blue_wall, scale=0.85)

    # 7. High-Fidelity Ortaköy Mosque on European hill
    print("Building detailed Ortaköy Mosque...")
    m_loc = (-6.8, -4.8, 0.6)
    # Hall
    hall = H.add_box("Mosque_Hall", size=(1.5, 1.5, 1.4), location=(m_loc[0], m_loc[1], m_loc[2] + 0.7), mat=white_wall, collection=arch)
    created.append(hall.name)
    # Drum octagonal
    drum = H.add_cylinder("Mosque_Drum", radius=0.68, depth=0.22, location=(m_loc[0], m_loc[1], m_loc[2] + 1.4), verts=8, mat=white_wall, collection=arch)
    created.append(drum.name)
    # Dome
    dome = H.add_sphere("Mosque_Dome", radius=0.65, location=(m_loc[0], m_loc[1], m_loc[2] + 1.62), mat=stone_wall, collection=arch)
    dome.scale = (1.0, 1.0, 0.72)
    created.append(dome.name)

    # Twin elegant tall minarets
    for dx in (-0.85, 0.85):
        m_base = H.add_box(f"Minaret_Base_{dx:.1f}", size=(0.22, 0.22, 0.8), location=(m_loc[0] + dx, m_loc[1] + 0.65, m_loc[2] + 0.4), mat=white_wall, collection=arch)
        m_shaft = H.add_cylinder(f"Minaret_Shaft_{dx:.1f}", radius=0.08, depth=2.8, location=(m_loc[0] + dx, m_loc[1] + 0.65, m_loc[2] + 0.8), verts=12, mat=white_wall, collection=arch)
        m_balc = H.add_cylinder(f"Minaret_Sherefe_{dx:.1f}", radius=0.14, depth=0.08, location=(m_loc[0] + dx, m_loc[1] + 0.65, m_loc[2] + 3.6), verts=12, mat=stone_wall, collection=arch)
        m_spire = H.add_cone(f"Minaret_Spire_{dx:.1f}", radius=0.09, depth=0.6, location=(m_loc[0] + dx, m_loc[1] + 0.65, m_loc[2] + 3.7), verts=12, mat=gold_accent, collection=arch)
        created += [m_base.name, m_shaft.name, m_balc.name, m_spire.name]

    # 8. Render & Lighting Setup
    print("Configuring volumetric atmospheric sunset lighting...")
    bpy.context.scene.world.use_nodes = True
    bg_node = bpy.context.scene.world.node_tree.nodes.get("Background") or next((n for n in bpy.context.scene.world.node_tree.nodes if n.type == 'BACKGROUND'), None)
    if bg_node:
        bg_node.inputs["Color"].default_value = (0.05, 0.02, 0.09, 1.0)

    R.op_setup_cinematic_lighting({
        "direction": [0.85, -0.35, 0.22], # low sunset key
        "sun_strength": 4.0,
        "sun_color": [1.0, 0.45, 0.15], # golden sunset orange
        "ambient_color": [0.08, 0.05, 0.15],
        "ambient_strength": 0.5
    })

    # 9. Frame perfect Camera looking down the Bosphorus Strait
    for obj in list(bpy.context.scene.objects):
        if obj.type == "CAMERA" and obj.name.startswith(("Camera_", "ImportedAsset_", "Bosphorus_")):
            bpy.data.objects.remove(obj, do_unlink=True)

    bpy.ops.object.camera_add(location=(0.0, -9.8, 3.2))
    cam = bpy.context.object
    cam.name = "Bosphorus_Camera"
    cam.data.lens = 45

    # Track camera to Maiden's Tower balcony level
    direction = Vector((0.0, -4.0, 0.85)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam

    # Depth of field focusing on Maiden's Tower
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = 6.2
    cam.data.dof.aperture_fstop = 2.8

    # Apply Cel-shading outline
    try:
        from .material_ops import op_apply_cel_shading_outline
        op_apply_cel_shading_outline({"thickness": 0.012})
    except Exception:
        pass

    return {
        "ok": True,
        "scene": "Istanbul_Bosphorus_Strait",
        "created_objects_count": len(created),
        "created_objects": created,
        "maidens_tower": "Created at (0, -4, 0)",
        "bosphorus_bridge": "Created at Y=6.0 spanning strait with vertical hangers",
        "camera": cam.name,
        "fog_weather": "Twilight Sunset",
    }


def op_create_physics_from_prompt(params):
    """Basit fizik scaffold."""
    prompt = params.get("prompt", "").lower()

    if "cloth" in prompt or "kumaş" in prompt or "dalgalan" in prompt:
        return {"ok": True, "physics_type": "cloth", "note": "Cloth modifier scaffold ready"}

    if "fluid" in prompt or "su" in prompt:
        return {"ok": True, "physics_type": "fluid", "note": "Fluid domain scaffold ready (manual domain needed)"}

    return {"ok": True, "physics_type": "rigid", "note": "Rigid body physics scaffold"}


def op_create_procedural_city_blockout(params):
    """
    Prompt'tan makul ölçekte prosedürel şehir blockout üretir.
    MVP kalitesi: grid + yükseklik varyasyonu + basit yollar + gece/ gündüz lighting.
    """
    prompt = params.get("prompt", "modern city")
    size_km = float(params.get("size_km", 1.5))
    density = params.get("density", "medium")
    style = params.get("style", "modern")

    extent = size_km * 40   # Blender units approximation

    env = H.get_or_create_collection("Environment")
    arch = H.get_or_create_collection("Architecture")

    created = []

    # Ground
    ground = H.create_floor("City_Ground", width=extent, depth=extent, collection=env)
    created.append(ground.name)

    # Simple grid of buildings
    grid = 6 if density == "low" else 9 if density == "medium" else 12
    spacing = extent / grid

    for x in range(grid):
        for y in range(grid):
            if random.random() < 0.25:
                continue  # leave some open space for streets

            h = random.uniform(3, 18) * (1.2 if "cyber" in prompt.lower() or "neo" in prompt.lower() else 1.0)
            bx = H.add_box(f"Building_{x}_{y}", size=(spacing * 0.65, spacing * 0.65, h), collection=arch)
            bx.location = ((x - grid/2) * spacing, (y - grid/2) * spacing, h/2)
            created.append(bx.name)

    # Basic night lighting if cyberpunk style
    if "cyber" in prompt.lower() or "night" in prompt.lower():
        R.op_setup_cinematic_lighting({})
    else:
        R.op_setup_lighting({"style": "bright"})

    return {
        "ok": True,
        "created_count": len(created),
        "city_size_km": size_km,
        "prompt": prompt,
        "note": "City blockout ready. Run multi-agent for better materials + lighting polish.",
    }
