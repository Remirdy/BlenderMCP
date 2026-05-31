"""Architectural exterior generation operations."""
from __future__ import annotations

import math

import bpy

from . import helpers as H
from . import material_ops as M
from . import render_ops as R


def _arch_mats():
    M.op_create_archviz_materials({})
    return {n: bpy.data.materials[n] for n in (
        "Warm_Wood", "Polished_Concrete", "White_Plaster", "Dark_Metal",
        "Clear_Glass", "Marble", "Ceramic_Tile")}


def op_create_floor_plan_blockout(params):
    mats = _arch_mats()
    arch = H.get_or_create_collection("Architecture")
    w = float(params.get("width", 12.0))
    d = float(params.get("depth", 9.0))
    rooms = int(params.get("rooms", 4))
    created = []
    H.create_floor("FloorSlab", width=w, depth=d, mat=mats["Polished_Concrete"], collection=arch)
    created.append("FloorSlab")
    walls = [
        ("Wall_N", w, (0, d / 2, 0), "x"),
        ("Wall_S", w, (0, -d / 2, 0), "x"),
        ("Wall_E", d, (w / 2, 0, 0), "y"),
        ("Wall_W", d, (-w / 2, 0, 0), "y"),
    ]
    for nm, length, loc, axis in walls:
        H.create_wall(nm, length=length, height=2.8, location=loc, axis=axis,
                      collection=arch, mat=mats["White_Plaster"])
        created.append(nm)
    # interior partitions
    for i in range(1, rooms):
        x = -w / 2 + i * (w / rooms)
        H.create_wall(f"Partition_{i}", length=d * 0.7, height=2.8, location=(x, 0, 0),
                      axis="y", collection=arch, mat=mats["White_Plaster"])
        created.append(f"Partition_{i}")
    return {"created": created, "rooms": rooms}


def op_create_modern_house_exterior(params):
    mats = _arch_mats()
    arch = H.get_or_create_collection("Architecture")
    env = H.get_or_create_collection("Environment")
    floors = int(params.get("floors", 2))
    created = []
    # plot
    grass = H.make_material("Lawn", color=(0.3, 0.55, 0.25), roughness=0.9)
    H.create_floor("Lawn", width=30, depth=30, mat=grass, collection=env)
    created.append("Lawn")
    fp_w, fp_d = 10.0, 8.0
    h = floors * 3.2
    # main mass (concrete) + glass facade
    H.add_box("House_Mass", size=(fp_w, fp_d, h), mat=mats["Polished_Concrete"], collection=arch)
    H.add_box("Facade_Glass", size=(fp_w * 0.6, 0.1, h * 0.9),
              location=(0, -fp_d / 2 - 0.05, 0), mat=mats["Clear_Glass"], collection=arch)
    H.add_box("Wood_Accent", size=(fp_w, 0.15, 1.2),
              location=(0, fp_d / 2 + 0.05, 0), mat=mats["Warm_Wood"], collection=arch)
    created += ["House_Mass", "Facade_Glass", "Wood_Accent"]
    # windows per floor
    for f in range(floors):
        for wx in (-fp_w / 3, fp_w / 3):
            nm = f"Win_{f}_{wx:.0f}"
            H.create_window(nm, width=1.4, height=1.6, location=(wx, fp_d / 2 + 0.06, 1.5 + f * 3.2),
                            collection=arch, mat=mats["Clear_Glass"])
            created.append(nm)
    # flat roof
    H.create_roof("House_Roof", footprint=fp_w, height=0.4, style="flat", location=(0, 0, h),
                  collection=arch, mat=mats["Dark_Metal"])
    created.append("House_Roof")
    # pathway
    path = H.make_material("Path_Stone", color=(0.6, 0.58, 0.55), roughness=0.7)
    H.create_road("Pathway", length=10, width=1.6, location=(0, -fp_d / 2 - 6, 0.02), mat=path, collection=env)
    created.append("Pathway")
    if params.get("pool"):
        water = H.make_material("Pool_Water", color=(0.1, 0.5, 0.7), roughness=0.05, metallic=0.0)
        H.add_box("Pool", size=(5, 3, 0.4), location=(8, -4, -0.4), mat=water, collection=env)
        created.append("Pool")
    if params.get("garden", True):
        trunk = H.make_material("Tree_Trunk", color=(0.36, 0.24, 0.14), roughness=0.8)
        leaf = H.make_material("Tree_Leaf", color=(0.2, 0.5, 0.22), roughness=0.8)
        for i, (x, y) in enumerate([(-11, -8), (12, -6), (-12, 8), (11, 9)]):
            H.create_tree(f"GardenTree_{i}", location=(x, y, 0), scale=1.4,
                          collection=env, trunk_mat=trunk, leaf_mat=leaf)
    R.op_setup_archviz_camera({"focal_length": 24})
    R.op_setup_archviz_lighting({"time_of_day": "sunset"})
    R.op_apply_render_preset({"preset": "archviz_render"})
    return {"created": created, "floors": floors}


def op_create_architectural_exterior(params):
    preset = params.get("preset", "modern_villa")
    return op_create_modern_house_exterior({
        "floors": params.get("floors", 2),
        "pool": preset == "modern_villa",
        "garden": params.get("landscaping", True),
    })


def op_add_architectural_details(params):
    mats = _arch_mats()
    arch = H.get_or_create_collection("Architecture")
    level = params.get("level", "medium")
    count = {"low": 2, "medium": 4, "high": 8}.get(level, 4)
    created = []
    for i in range(count):
        t = H.add_box(f"Trim_{i:02d}", size=(0.2, 0.2, 0.1), location=(i - count / 2, 0, 2.7 + i * 0.05),
                      mat=mats["Dark_Metal"], collection=arch)
        created.append(t.name)
    return {"created": created, "level": level}


def op_add_windows_doors_stairs(params):
    mats = _arch_mats()
    arch = H.get_or_create_collection("Architecture")
    created = []
    for i in range(int(params.get("windows", 6))):
        w = H.create_window(f"AddWin_{i:02d}", location=(i * 1.8 - 5, -4.1, 1.4),
                            collection=arch, mat=mats["Clear_Glass"])
        created.append(w.name)
    for i in range(int(params.get("doors", 2))):
        d = H.create_door(f"AddDoor_{i:02d}", location=(i * 2 - 1, -4.1, 0),
                          collection=arch, mat=mats["Warm_Wood"])
        created.append(d.name)
    if params.get("stairs", True):
        steps = H.create_stairs("Stairs", steps=8, location=(0, 4, 0), collection=arch, mat=mats["Polished_Concrete"])
        created += [s.name for s in steps]
    return {"created": created}
