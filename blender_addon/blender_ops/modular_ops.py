"""Modular environment kit builder.

Generates grid-aligned, consistently-sized, correctly-pivoted modular pieces and
assembles a test layout to validate snapping. Pivots are placed so pieces tile on
the grid without gaps.
"""
from __future__ import annotations

import math

import bpy

from . import asset_ops
from . import helpers as H
from . import render_ops as R

GRID = 2.0          # default module size (meters)
WALL_H = 3.0
THICK = 0.15

KIT_STYLES = {
    "sci_fi_corridor": "low_poly_city",
    "dungeon_room": "medieval",
    "medieval_village": "medieval",
    "modern_city_street": "low_poly_city",
    "stylized_campus": "low_poly_city",
    "cyberpunk_alley": "low_poly_city",
    "interior_room": "modern_interior",
    "office": "modern_interior",
    "store": "cafe",
    "platformer": "low_poly_city",
}

LAST_KIT: dict = {}


def _kit_mats(style):
    return asset_ops._build_palette(style)


def _emissive(style):
    return H.make_material(f"{style}_Emissive", color=(0.1, 0.5, 1.0), roughness=0.3, emission_strength=6.0, emission_color=(0.1, 0.5, 1.0))


def op_create_modular_wall_piece(params):
    style = params.get("style", "low_poly_city")
    mats = _kit_mats(style)
    coll = H.get_or_create_collection(params.get("collection", "ModularKit"))
    grid = float(params.get("grid", GRID))
    mat = list(mats.values())[0]
    obj = H.add_box(params.get("name", "Mod_Wall_A"), size=(grid, THICK, WALL_H), location=(0, 0, 0), mat=mat, collection=coll)
    return {"created": obj.name, "size": [grid, THICK, WALL_H]}


def op_create_modular_floor_piece(params):
    style = params.get("style", "low_poly_city")
    mats = _kit_mats(style)
    coll = H.get_or_create_collection(params.get("collection", "ModularKit"))
    grid = float(params.get("grid", GRID))
    obj = H.add_box(params.get("name", "Mod_Floor_A"), size=(grid, grid, THICK), location=(0, 0, 0), mat=list(mats.values())[0], collection=coll)
    return {"created": obj.name, "size": [grid, grid, THICK]}


def op_create_modular_corner_piece(params):
    style = params.get("style", "low_poly_city")
    mats = _kit_mats(style)
    coll = H.get_or_create_collection(params.get("collection", "ModularKit"))
    grid = float(params.get("grid", GRID))
    a = H.add_box("corner_a", size=(grid, THICK, WALL_H), location=(0, 0, 0), mat=list(mats.values())[0], collection=coll)
    b = H.add_box("corner_b", size=(THICK, grid, WALL_H), location=(-grid / 2 + THICK / 2, grid / 2 - THICK / 2, 0), mat=list(mats.values())[0], collection=coll)
    obj = H.join_objects(params.get("name", "Mod_Corner_A"), [a, b], coll, list(mats.values())[0])
    return {"created": obj.name}


def op_create_modular_door_piece(params):
    style = params.get("style", "low_poly_city")
    mats = _kit_mats(style)
    coll = H.get_or_create_collection(params.get("collection", "ModularKit"))
    grid = float(params.get("grid", GRID))
    mat = list(mats.values())[0]
    parts = [
        H.add_box("door_l", size=(grid / 2 - 0.5, THICK, WALL_H), location=(-(grid / 4 + 0.25), 0, 0), mat=mat, collection=coll),
        H.add_box("door_r", size=(grid / 2 - 0.5, THICK, WALL_H), location=(grid / 4 + 0.25, 0, 0), mat=mat, collection=coll),
        H.add_box("door_top", size=(1.0, THICK, WALL_H - 2.2), location=(0, 0, 2.2), mat=mat, collection=coll),
    ]
    obj = H.join_objects(params.get("name", "Mod_Door_A"), parts, coll, mat)
    return {"created": obj.name}


def op_create_modular_window_piece(params):
    style = params.get("style", "low_poly_city")
    mats = _kit_mats(style)
    coll = H.get_or_create_collection(params.get("collection", "ModularKit"))
    grid = float(params.get("grid", GRID))
    mat = list(mats.values())[0]
    glass = mats.get("glass", mat)
    parts = [
        H.add_box("win_bottom", size=(grid, THICK, 1.0), location=(0, 0, 0), mat=mat, collection=coll),
        H.add_box("win_top", size=(grid, THICK, WALL_H - 2.2), location=(0, 0, 2.2), mat=mat, collection=coll),
        H.add_box("win_glass", size=(grid - 0.4, 0.05, 1.0), location=(0, 0, 1.0), mat=glass, collection=coll),
    ]
    obj = H.join_objects(params.get("name", "Mod_Window_A"), parts, coll, mat)
    return {"created": obj.name}


def op_create_modular_roof_piece(params):
    style = params.get("style", "low_poly_city")
    mats = _kit_mats(style)
    coll = H.get_or_create_collection(params.get("collection", "ModularKit"))
    grid = float(params.get("grid", GRID))
    obj = H.add_box(params.get("name", "Mod_Roof_A"), size=(grid, grid, THICK), location=(0, 0, 0), mat=mats.get("roof", list(mats.values())[0]), collection=coll)
    return {"created": obj.name}


def op_create_modular_stair_piece(params):
    style = params.get("style", "low_poly_city")
    mats = _kit_mats(style)
    coll = H.get_or_create_collection(params.get("collection", "ModularKit"))
    steps = H.create_stairs(params.get("name", "Mod_Stair_A"), steps=8, width=GRID, location=(0, -GRID / 2, 0), collection=coll, mat=list(mats.values())[0])
    obj = H.join_objects(params.get("name", "Mod_Stair_A"), steps, coll, list(mats.values())[0])
    return {"created": obj.name}


def op_create_modular_prop_variants(params):
    style = params.get("style", "low_poly_city")
    mats = _kit_mats(style)
    coll = H.get_or_create_collection(params.get("collection", "ModularKit"))
    emissive = _emissive(style)
    created = []
    # vents, pipes, emissive panels — generic sci-fi/industrial dressing
    vent = H.add_box("Mod_Vent", size=(0.8, 0.1, 0.8), location=(0, 0, 1.5), mat=list(mats.values())[0], collection=coll)
    pipe = H.add_cylinder("Mod_Pipe", radius=0.12, depth=GRID, location=(0, 0, 2.6), verts=10, mat=list(mats.values())[0], collection=coll)
    pipe.rotation_euler = (math.radians(90), 0, 0)
    panel = H.add_box("Mod_EmissivePanel", size=(0.3, 0.05, 1.4), location=(0, 0, 1.5), mat=emissive, collection=coll)
    created = [vent.name, pipe.name, panel.name]
    return {"created": created}


def _build_kit_pieces(style, coll_name, grid):
    pieces = {}
    pieces["wall"] = op_create_modular_wall_piece({"style": style, "collection": coll_name, "grid": grid, "name": "Mod_Wall_A"})["created"]
    pieces["floor"] = op_create_modular_floor_piece({"style": style, "collection": coll_name, "grid": grid, "name": "Mod_Floor_A"})["created"]
    pieces["corner"] = op_create_modular_corner_piece({"style": style, "collection": coll_name, "grid": grid, "name": "Mod_Corner_A"})["created"]
    pieces["door"] = op_create_modular_door_piece({"style": style, "collection": coll_name, "grid": grid, "name": "Mod_Door_A"})["created"]
    pieces["window"] = op_create_modular_window_piece({"style": style, "collection": coll_name, "grid": grid, "name": "Mod_Window_A"})["created"]
    pieces["roof"] = op_create_modular_roof_piece({"style": style, "collection": coll_name, "grid": grid, "name": "Mod_Roof_A"})["created"]
    pieces["stair"] = op_create_modular_stair_piece({"style": style, "collection": coll_name, "grid": grid, "name": "Mod_Stair_A"})["created"]
    op_create_modular_prop_variants({"style": style, "collection": coll_name, "grid": grid})
    return pieces


def op_validate_modular_grid(params):
    grid = float(params.get("grid", GRID))
    coll = bpy.data.collections.get(params.get("collection", LAST_KIT.get("collection", "ModularKit")))
    issues = []
    checked = 0
    if coll:
        for o in coll.objects:
            if o.type != "MESH":
                continue
            checked += 1
            dims = o.dimensions
            for axis, d in zip("xy", (dims.x, dims.y)):
                # piece footprint should be ~multiple of grid or thin
                if d > THICK + 0.01 and abs((d / grid) - round(d / grid)) > 0.1:
                    issues.append({"object": o.name, "axis": axis, "size": round(d, 3),
                                   "message": "footprint not aligned to grid module"})
            # origin should sit on z=base
            if abs(o.location.z) > 0.01 and "Stair" not in o.name:
                issues.append({"object": o.name, "message": "origin not at floor level (z!=0)"})
    return {"grid": grid, "checked": checked, "issues": issues, "aligned": len(issues) == 0}


def op_create_test_layout(params):
    """Assemble pieces into a sample corridor/room to prove snapping."""
    coll = H.get_or_create_collection("ModularKit_TestLayout")
    src = LAST_KIT.get("pieces", {})
    grid = float(params.get("grid", GRID))
    created = []

    def place(src_name, loc, rot=0.0):
        base = bpy.data.objects.get(src_name)
        if not base:
            return
        dup = base.copy()
        dup.data = base.data.copy()
        dup.name = f"{src_name}_inst"
        coll.objects.link(dup)
        dup.location = loc
        dup.rotation_euler = (0, 0, math.radians(rot))
        created.append(dup.name)

    span = 4
    for i in range(span):
        y = i * grid
        place(src.get("floor", ""), (0, y, 0))
        place(src.get("roof", ""), (0, y, WALL_H))
        place(src.get("wall", ""), (-grid / 2, y, 0), 90)
        if i == 1:
            place(src.get("door", ""), (grid / 2, y, 0), 90)
        else:
            place(src.get("window", ""), (grid / 2, y, 0), 90)
    return {"created": created, "layout": "corridor", "length_modules": span}


def op_create_modular_kit(params):
    kit_type = params.get("kit_type", "sci_fi_corridor")
    style = KIT_STYLES.get(kit_type, "low_poly_city")
    grid = float(params.get("grid", GRID))
    coll_name = params.get("name", f"{kit_type}_Kit")
    pieces = _build_kit_pieces(style, coll_name, grid)
    LAST_KIT.clear()
    LAST_KIT.update({"kit_type": kit_type, "style": style, "collection": coll_name, "pieces": pieces, "grid": grid})
    layout = op_create_test_layout({"grid": grid}) if params.get("test_layout", True) else {"created": []}
    validation = op_validate_modular_grid({"grid": grid, "collection": coll_name})
    # name it as an asset pack too so packaging/scoring can reuse the pipeline
    asset_ops.LAST_PACK.clear()
    asset_ops.LAST_PACK.update({
        "name": coll_name, "theme": kit_type, "style": style,
        "assets": [{"name": v, "category": k.title(), "polycount": H.poly_count(bpy.data.objects.get(v)),
                    "materials": [m.name for m in bpy.data.objects[v].data.materials if m] if bpy.data.objects.get(v) else []}
                   for k, v in pieces.items() if bpy.data.objects.get(v)],
        "materials": sorted({m.name for v in pieces.values() if bpy.data.objects.get(v) for m in bpy.data.objects[v].data.materials if m}),
        "collection": coll_name, "assets_collection": coll_name,
    })
    if params.get("render_preview", True):
        R.op_setup_camera({"focal_length": 30})
        R.op_setup_cinematic_lighting({"mood": "dramatic"}) if "sci" in kit_type or "cyber" in kit_type else R.op_setup_lighting({"style": "bright"})
        R.op_apply_render_preset({"preset": "portfolio_render"})
    return {"kit_type": kit_type, "pieces": pieces, "grid": grid,
            "test_layout_objects": len(layout["created"]), "grid_valid": validation["aligned"],
            "grid_issues": validation["issues"],
            "suggested_next": ["validate_modular_grid", "render_preview", "export_modular_kit"]}


def op_export_modular_kit(params):
    from . import packaging_ops
    target = params.get("target", "unreal")
    fmt = params.get("format", "fbx")
    if fmt == "fbx":
        return packaging_ops.op_package_asset_for_marketplace({"fbx": True})
    return packaging_ops.op_package_asset_for_marketplace({"fbx": False})
