"""Interior design generation operations with layout logic."""
from __future__ import annotations

import bpy

from . import helpers as H
from . import material_ops as M
from . import render_ops as R

PALETTES = {
    "warm_modern": {"floor": (0.45, 0.30, 0.18), "wall": (0.93, 0.90, 0.85), "accent": (0.5, 0.3, 0.2)},
    "minimalist_neutral": {"floor": (0.8, 0.78, 0.74), "wall": (0.95, 0.95, 0.94), "accent": (0.6, 0.6, 0.6)},
    "luxury_dark": {"floor": (0.2, 0.18, 0.16), "wall": (0.25, 0.24, 0.26), "accent": (0.8, 0.7, 0.4)},
}


def _shell(width, depth, height, palette, ceiling=True):
    """Build a room shell (floor, 4 walls, optional ceiling) with one open wall for the camera."""
    arch = H.get_or_create_collection("Architecture")
    p = PALETTES.get(palette, PALETTES["warm_modern"])
    floor_mat = H.make_material(f"Floor_{palette}", color=p["floor"], roughness=0.4)
    wall_mat = H.make_material(f"Wall_{palette}", color=p["wall"], roughness=0.8)
    H.create_floor("Room_Floor", width=width, depth=depth, mat=floor_mat, collection=arch)
    H.create_wall("Wall_Back", length=width, height=height, location=(0, depth / 2, 0), axis="x", collection=arch, mat=wall_mat)
    H.create_wall("Wall_Left", length=depth, height=height, location=(-width / 2, 0, 0), axis="y", collection=arch, mat=wall_mat)
    H.create_wall("Wall_Right", length=depth, height=height, location=(width / 2, 0, 0), axis="y", collection=arch, mat=wall_mat)
    if ceiling:
        ceil = H.add_plane("Room_Ceiling", size=(width, depth), location=(0, 0, height), mat=wall_mat, collection=arch)
    return floor_mat, wall_mat, p


def _interior_finish(warm):
    R.op_setup_archviz_camera({"focal_length": 28, "eye_level": 1.5})
    R.op_setup_archviz_lighting({"time_of_day": "midday", "interior": True})
    if warm:
        coll = H.get_or_create_collection("Lighting")
        lamp = bpy.data.lights.new("Warm_Lamp", "POINT")
        lamp.energy = 200
        lamp.color = (1.0, 0.8, 0.55)
        obj = bpy.data.objects.new("Warm_Lamp", lamp)
        coll.objects.link(obj)
        obj.location = (1.5, 0, 2.2)
    R.op_apply_render_preset({"preset": "archviz_render"})


def op_create_living_room_scene(params):
    style = params.get("style", "luxury_apartment")
    palette = "warm_modern" if "warm" in style or style == "luxury_apartment" else "minimalist_neutral"
    M.op_create_archviz_materials({})
    _shell(6.0, 5.0, 2.8, palette)
    furn = H.get_or_create_collection("Furniture")
    wood = bpy.data.materials.get("Warm_Wood")
    fabric = bpy.data.materials.get("Fabric")
    marble = bpy.data.materials.get("Marble")
    glass = bpy.data.materials.get("Clear_Glass")
    created = []
    sofa = H.create_sofa("Sofa", location=(0, -1.5, 0), mat=fabric, collection=furn)
    created += [o.name for o in sofa]
    table = H.create_table("CoffeeTable", location=(0, 0, 0), w=1.1, d=0.6, h=0.4, mat=wood, collection=furn)
    created += [o.name for o in table]
    tv = H.add_box("TV_Wall", size=(2.0, 0.08, 1.1), location=(0, 2.4, 1.0), mat=bpy.data.materials.get("Dark_Metal"), collection=furn)
    rug = H.add_plane("Rug", size=(2.6, 2.0), location=(0, -0.2, 0.01), mat=fabric, collection=furn)
    win = H.create_window("Picture_Window", width=2.4, height=1.8, location=(-3.0, 0, 1.4), collection=H.get_or_create_collection("Architecture"), mat=glass)
    created += [tv.name, rug.name, win.name]
    # plants
    leaf = H.make_material("Plant_Leaf", color=(0.2, 0.5, 0.25), roughness=0.8)
    for i, (x, y) in enumerate([(2.5, -2.0), (-2.5, 2.0)]):
        H.create_tree(f"Plant_{i}", location=(x, y, 0), scale=0.7, collection=furn,
                      trunk_mat=wood, leaf_mat=leaf)
    _interior_finish(params.get("warm_lighting", True))
    return {"created": created, "room": "living_room", "style": style}


def op_create_bedroom_scene(params):
    palette = "minimalist_neutral" if params.get("style") == "minimalist_interior" else "warm_modern"
    M.op_create_archviz_materials({})
    _shell(5.0, 4.5, 2.7, palette)
    furn = H.get_or_create_collection("Furniture")
    wood = bpy.data.materials.get("Warm_Wood")
    fabric = bpy.data.materials.get("Fabric")
    created = []
    bed = H.add_box("Bed", size=(2.0, 2.2, 0.5), location=(0, 1.0, 0), mat=fabric, collection=furn)
    head = H.add_box("Headboard", size=(2.0, 0.15, 1.0), location=(0, 2.1, 0), mat=wood, collection=furn)
    created += [bed.name, head.name]
    for dx in (-1.3, 1.3):
        n = H.create_cabinet(f"Nightstand_{dx:.0f}", location=(dx, 1.6, 0), w=0.5, d=0.4, h=0.5, mat=wood, collection=furn)
        created.append(n.name)
    wardrobe = H.create_cabinet("Wardrobe", location=(-2.0, -1.5, 0), w=1.6, d=0.6, h=2.2, mat=wood, collection=furn)
    created.append(wardrobe.name)
    H.create_window("Bedroom_Window", width=1.6, height=1.4, location=(2.5, 0, 1.4),
                    collection=H.get_or_create_collection("Architecture"), mat=bpy.data.materials.get("Clear_Glass"))
    _interior_finish(True)
    return {"created": created, "room": "bedroom"}


def op_create_kitchen_scene(params):
    M.op_create_archviz_materials({})
    _shell(5.5, 4.5, 2.8, "minimalist_neutral")
    furn = H.get_or_create_collection("Furniture")
    wood = bpy.data.materials.get("Warm_Wood")
    metal = bpy.data.materials.get("Dark_Metal")
    tile = bpy.data.materials.get("Ceramic_Tile")
    created = []
    # base cabinets along back wall
    for i in range(4):
        c = H.create_cabinet(f"Cabinet_{i}", location=(-2.0 + i * 1.1, 1.9, 0), w=1.0, d=0.6, h=0.9, mat=wood, collection=furn)
        created.append(c.name)
    counter = H.add_box("Counter", size=(4.4, 0.65, 0.05), location=(-0.35, 1.9, 0.9), mat=tile, collection=furn)
    created.append(counter.name)
    if params.get("island", True):
        island = H.add_box("Island", size=(2.0, 1.0, 0.9), location=(0, -0.5, 0), mat=wood, collection=furn)
        itop = H.add_box("Island_Top", size=(2.1, 1.1, 0.05), location=(0, -0.5, 0.9), mat=tile, collection=furn)
        created += [island.name, itop.name]
    H.add_box("Fridge", size=(0.7, 0.7, 1.9), location=(2.2, 1.8, 0), mat=metal, collection=furn)
    _interior_finish(True)
    return {"created": created, "room": "kitchen"}


def op_create_office_interior(params):
    M.op_create_archviz_materials({})
    desks = int(params.get("desks", 6))
    _shell(10.0, 8.0, 2.9, "minimalist_neutral")
    furn = H.get_or_create_collection("Furniture")
    wood = bpy.data.materials.get("Warm_Wood")
    metal = bpy.data.materials.get("Dark_Metal")
    glass = bpy.data.materials.get("Frosted_Glass")
    created = []
    cols = 3
    for i in range(desks):
        x = -3.5 + (i % cols) * 3.0
        y = 2.0 - (i // cols) * 3.0
        d = H.create_table(f"Desk_{i:02d}", location=(x, y, 0), w=1.4, d=0.7, h=0.74, mat=wood, collection=furn)
        H.create_chair(f"OfficeChair_{i:02d}", location=(x, y - 0.7, 0), mat=metal, collection=furn)
        created.append(f"Desk_{i:02d}")
    if params.get("glass_partitions", True):
        for gx in (-2.0, 2.0):
            g = H.add_box(f"Partition_{gx:.0f}", size=(0.05, 5.0, 2.2), location=(gx, 0, 0), mat=glass, collection=furn)
            created.append(g.name)
    # ceiling light panels
    for lx in (-2, 2):
        for ly in (-2, 2):
            ll = bpy.data.lights.new(f"Panel_{lx}_{ly}", "AREA")
            ll.energy = 200
            ll.size = 1.5
            o = bpy.data.objects.new(f"Panel_{lx}_{ly}", ll)
            H.get_or_create_collection("Lighting").objects.link(o)
            o.location = (lx, ly, 2.85)
    R.op_setup_archviz_camera({"focal_length": 22})
    R.op_setup_archviz_lighting({"interior": True})
    R.op_apply_render_preset({"preset": "archviz_render"})
    return {"created": created, "room": "office", "desks": desks}


def op_create_interior_design_scene(params):
    room = params.get("room", "living_room")
    dispatch = {
        "living_room": op_create_living_room_scene,
        "bedroom": op_create_bedroom_scene,
        "kitchen": op_create_kitchen_scene,
        "office": op_create_office_interior,
    }
    fn = dispatch.get(room, op_create_living_room_scene)
    return fn(params)


def op_create_apartment_interior(params):
    # Build a living room as the hero space; partitions imply additional rooms.
    res = op_create_living_room_scene(params)
    res["rooms"] = int(params.get("rooms", 3))
    return res


def op_add_furniture_set(params):
    set_name = params.get("set_name", "living_room")
    dispatch = {
        "living_room": op_create_living_room_scene,
        "bedroom": op_create_bedroom_scene,
        "kitchen": op_create_kitchen_scene,
        "office": op_create_office_interior,
    }
    return dispatch.get(set_name, op_create_living_room_scene)({})


def op_apply_interior_material_palette(params):
    palette = params.get("palette", "warm_modern")
    p = PALETTES.get(palette, PALETTES["warm_modern"])
    wall = H.make_material(f"Wall_{palette}", color=p["wall"], roughness=0.8)
    floor = H.make_material(f"Floor_{palette}", color=p["floor"], roughness=0.4)
    skinned = 0
    for o in H.all_mesh_objects():
        if "Wall" in o.name or "Ceiling" in o.name:
            H.assign_material(o, wall); skinned += 1
        elif "Floor" in o.name:
            H.assign_material(o, floor); skinned += 1
    return {"palette": palette, "objects_skinned": skinned}
