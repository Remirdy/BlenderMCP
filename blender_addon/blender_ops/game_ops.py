"""Game asset and environment generation operations."""
from __future__ import annotations

import math
import random

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
