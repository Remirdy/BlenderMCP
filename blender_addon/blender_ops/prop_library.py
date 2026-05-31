"""Original procedural prop builders.

Each builder composes simple primitives into one joined, named, materialed asset
with a clean bottom-center pivot. Designs are generic (stylized medieval, low-poly
city, cozy cafe, modern interior) and original — no copyrighted or branded shapes.

Signature: builder(name, location, mats, collection) -> bpy.types.Object
`mats` is a dict of named materials provided by the pack palette.
"""
from __future__ import annotations

import math

import bpy

from . import helpers as H


def _m(mats, *keys):
    for k in keys:
        if k in mats:
            return mats[k]
    return next(iter(mats.values()))


# --------------------------------------------------------------------------- #
# Medieval / market props
# --------------------------------------------------------------------------- #
def crate(name, loc, mats, coll):
    wood = _m(mats, "wood")
    parts = [H.add_box(f"{name}_b", size=(0.7, 0.7, 0.7), location=loc, mat=wood, collection=coll)]
    for z in (0.18, 0.52):
        parts.append(H.add_box(f"{name}_s", size=(0.74, 0.06, 0.08), location=(loc[0], loc[1], loc[2] + z), mat=wood, collection=coll))
    return H.join_objects(name, parts, coll, wood)


def barrel(name, loc, mats, coll):
    wood = _m(mats, "wood")
    metal = _m(mats, "metal", "wood")
    body = H.add_cylinder(f"{name}_body", radius=0.38, depth=0.95, location=loc, verts=16, mat=wood, collection=coll)
    parts = [body]
    for z in (0.2, 0.75):
        parts.append(H.add_cylinder(f"{name}_ring", radius=0.4, depth=0.06, location=(loc[0], loc[1], loc[2] + z), verts=16, mat=metal, collection=coll))
    return H.join_objects(name, parts, coll, wood)


def lantern(name, loc, mats, coll):
    metal = _m(mats, "metal", "wood")
    glass = _m(mats, "glass", "emissive", "metal")
    base = H.add_cylinder(f"{name}_base", radius=0.12, depth=0.08, location=loc, verts=12, mat=metal, collection=coll)
    glassbox = H.add_box(f"{name}_glass", size=(0.16, 0.16, 0.22), location=(loc[0], loc[1], loc[2] + 0.08), mat=glass, collection=coll)
    top = H.add_cone(f"{name}_top", radius=0.13, depth=0.12, location=(loc[0], loc[1], loc[2] + 0.3), verts=8, mat=metal, collection=coll)
    ring = H.add_cylinder(f"{name}_ring", radius=0.03, depth=0.1, location=(loc[0], loc[1], loc[2] + 0.42), verts=8, mat=metal, collection=coll)
    return H.join_objects(name, [base, glassbox, top, ring], coll, metal)


def sign(name, loc, mats, coll):
    wood = _m(mats, "wood")
    post = H.add_box(f"{name}_post", size=(0.08, 0.08, 1.4), location=loc, mat=wood, collection=coll)
    board = H.add_box(f"{name}_board", size=(0.7, 0.05, 0.4), location=(loc[0], loc[1], loc[2] + 1.05), mat=wood, collection=coll)
    return H.join_objects(name, [post, board], coll, wood)


def market_stand(name, loc, mats, coll):
    wood = _m(mats, "wood")
    fabric = _m(mats, "fabric", "wood")
    parts = []
    top = H.add_box(f"{name}_top", size=(1.6, 1.0, 0.06), location=(loc[0], loc[1], loc[2] + 0.9), mat=wood, collection=coll)
    parts.append(top)
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        parts.append(H.add_box(f"{name}_leg", size=(0.08, 0.08, 0.9), location=(loc[0] + dx * 0.7, loc[1] + dy * 0.4, loc[2]), mat=wood, collection=coll))
    canopy = H.add_box(f"{name}_canopy", size=(1.8, 1.2, 0.05), location=(loc[0], loc[1], loc[2] + 1.9), mat=fabric, collection=coll)
    canopy.rotation_euler = (math.radians(8), 0, 0)
    parts.append(canopy)
    for dx in (-1, 1):
        parts.append(H.add_box(f"{name}_pole", size=(0.06, 0.06, 1.0), location=(loc[0] + dx * 0.85, loc[1] + 0.5, loc[2] + 0.9), mat=wood, collection=coll))
    return H.join_objects(name, parts, coll, wood)


def basket(name, loc, mats, coll):
    wood = _m(mats, "wood", "fabric")
    b = H.add_cylinder(f"{name}_b", radius=0.28, depth=0.32, location=loc, verts=12, mat=wood, collection=coll)
    rim = H.add_cylinder(f"{name}_rim", radius=0.3, depth=0.05, location=(loc[0], loc[1], loc[2] + 0.3), verts=12, mat=wood, collection=coll)
    return H.join_objects(name, [b, rim], coll, wood)


def rug(name, loc, mats, coll):
    fabric = _m(mats, "fabric", "wood")
    r = H.add_box(f"{name}_r", size=(1.6, 1.0, 0.04), location=loc, mat=fabric, collection=coll)
    return H.join_objects(name, [r], coll, fabric)


def cart(name, loc, mats, coll):
    wood = _m(mats, "wood")
    metal = _m(mats, "metal", "wood")
    parts = [H.add_box(f"{name}_bed", size=(1.6, 0.9, 0.12), location=(loc[0], loc[1], loc[2] + 0.5), mat=wood, collection=coll)]
    for dx in (-1, 1):
        parts.append(H.add_box(f"{name}_side", size=(1.6, 0.05, 0.3), location=(loc[0], loc[1] + dx * 0.45, loc[2] + 0.6), mat=wood, collection=coll))
    for dx in (-1, 1):
        w = H.add_cylinder(f"{name}_wheel", radius=0.35, depth=0.1, location=(loc[0] + dx * 0.6, loc[1], loc[2]), verts=16, mat=metal, collection=coll)
        w.rotation_euler = (0, math.radians(90), 0)
        parts.append(w)
    return H.join_objects(name, parts, coll, wood)


def table(name, loc, mats, coll):
    wood = _m(mats, "wood")
    return H.join_objects(name, H.create_table(name, location=loc, mat=wood, collection=coll), coll, wood)


def chair(name, loc, mats, coll):
    wood = _m(mats, "wood")
    return H.join_objects(name, H.create_chair(name, location=loc, mat=wood, collection=coll), coll, wood)


# --------------------------------------------------------------------------- #
# Cafe props
# --------------------------------------------------------------------------- #
def coffee_cup(name, loc, mats, coll):
    cer = _m(mats, "ceramic", "white", "wood")
    cup = H.add_cylinder(f"{name}_cup", radius=0.05, depth=0.09, location=(loc[0], loc[1], loc[2] + 0.01), verts=14, mat=cer, collection=coll)
    saucer = H.add_cylinder(f"{name}_saucer", radius=0.09, depth=0.012, location=loc, verts=16, mat=cer, collection=coll)
    return H.join_objects(name, [cup, saucer], coll, cer)


def menu_board(name, loc, mats, coll):
    dark = _m(mats, "dark", "metal", "wood")
    wood = _m(mats, "wood", "dark")
    board = H.add_box(f"{name}_board", size=(0.7, 0.05, 1.0), location=(loc[0], loc[1], loc[2] + 0.9), mat=dark, collection=coll)
    for dx in (-1, 1):
        H.add_box(f"{name}_leg", size=(0.05, 0.4, 0.9), location=(loc[0] + dx * 0.3, loc[1], loc[2]), mat=wood, collection=coll)
    parts = [o for o in bpy.context.scene.objects if o.name.startswith(name)]
    return H.join_objects(name, parts, coll, dark)


def counter(name, loc, mats, coll):
    wood = _m(mats, "wood")
    top = _m(mats, "marble", "ceramic", "wood")
    body = H.add_box(f"{name}_body", size=(2.0, 0.8, 1.0), location=loc, mat=wood, collection=coll)
    cap = H.add_box(f"{name}_top", size=(2.1, 0.9, 0.06), location=(loc[0], loc[1], loc[2] + 1.0), mat=top, collection=coll)
    return H.join_objects(name, [body, cap], coll, wood)


def pastry_display(name, loc, mats, coll):
    glass = _m(mats, "glass", "white", "metal")
    metal = _m(mats, "metal", "wood")
    base = H.add_box(f"{name}_base", size=(1.2, 0.6, 0.9), location=loc, mat=metal, collection=coll)
    case = H.add_box(f"{name}_case", size=(1.2, 0.6, 0.5), location=(loc[0], loc[1], loc[2] + 0.9), mat=glass, collection=coll)
    return H.join_objects(name, [base, case], coll, metal)


def shelf(name, loc, mats, coll):
    wood = _m(mats, "wood")
    parts = [H.add_box(f"{name}_frame", size=(1.0, 0.3, 1.8), location=loc, mat=wood, collection=coll)]
    for z in (0.4, 0.9, 1.4):
        parts.append(H.add_box(f"{name}_lvl", size=(0.96, 0.3, 0.04), location=(loc[0], loc[1], loc[2] + z), mat=wood, collection=coll))
    return H.join_objects(name, parts, coll, wood)


def potted_plant(name, loc, mats, coll):
    pot = _m(mats, "ceramic", "wood")
    leaf = _m(mats, "leaf", "fabric", "wood")
    p = H.add_cylinder(f"{name}_pot", radius=0.16, depth=0.24, location=loc, verts=12, mat=pot, collection=coll)
    foliage = H.add_sphere(f"{name}_foliage", radius=0.3, location=(loc[0], loc[1], loc[2] + 0.5), mat=leaf, collection=coll)
    foliage.scale = (1.0, 1.0, 1.2)
    return H.join_objects(name, [p, foliage], coll, pot)


def lamp_post(name, loc, mats, coll):
    metal = _m(mats, "metal", "dark", "wood")
    glow = _m(mats, "emissive", "glass", "metal")
    pole = H.add_cylinder(f"{name}_pole", radius=0.06, depth=3.0, location=loc, verts=10, mat=metal, collection=coll)
    head = H.add_box(f"{name}_head", size=(0.3, 0.3, 0.3), location=(loc[0], loc[1], loc[2] + 3.0), mat=glow, collection=coll)
    return H.join_objects(name, [pole, head], coll, metal)


def bench(name, loc, mats, coll):
    wood = _m(mats, "wood")
    parts = [H.add_box(f"{name}_seat", size=(1.4, 0.4, 0.06), location=(loc[0], loc[1], loc[2] + 0.45), mat=wood, collection=coll)]
    parts.append(H.add_box(f"{name}_back", size=(1.4, 0.05, 0.4), location=(loc[0], loc[1] - 0.18, loc[2] + 0.65), mat=wood, collection=coll))
    for dx in (-1, 1):
        parts.append(H.add_box(f"{name}_leg", size=(0.06, 0.4, 0.45), location=(loc[0] + dx * 0.6, loc[1], loc[2]), mat=wood, collection=coll))
    return H.join_objects(name, parts, coll, wood)


# --------------------------------------------------------------------------- #
# Low-poly city props
# --------------------------------------------------------------------------- #
def house(name, loc, mats, coll):
    wall = _m(mats, "plaster", "concrete", "wood")
    roof = _m(mats, "roof", "dark", "wood")
    body = H.add_box(f"{name}_body", size=(2.2, 2.0, 2.4), location=loc, mat=wall, collection=coll)
    r = H.create_roof(f"{name}_roof", footprint=2.2, height=1.0, style="gable", location=(loc[0], loc[1], loc[2] + 2.4), mat=roof, collection=coll)
    return H.join_objects(name, [body, r], coll, wall)


def shop(name, loc, mats, coll):
    wall = _m(mats, "plaster", "concrete", "wood")
    glass = _m(mats, "glass", "metal", "wood")
    body = H.add_box(f"{name}_body", size=(2.6, 2.2, 2.6), location=loc, mat=wall, collection=coll)
    window = H.add_box(f"{name}_window", size=(1.8, 0.1, 1.2), location=(loc[0], loc[1] - 1.1, loc[2] + 0.9), mat=glass, collection=coll)
    awn = H.add_box(f"{name}_awning", size=(2.2, 0.6, 0.08), location=(loc[0], loc[1] - 1.2, loc[2] + 1.7), mat=_m(mats, "fabric", "roof", "wood"), collection=coll)
    return H.join_objects(name, [body, window, awn], coll, wall)


def car(name, loc, mats, coll):
    body_m = _m(mats, "paint", "metal", "wood")
    glass = _m(mats, "glass", "dark", "metal")
    tyre = _m(mats, "dark", "metal", "wood")
    body = H.add_box(f"{name}_body", size=(1.8, 0.9, 0.5), location=(loc[0], loc[1], loc[2] + 0.3), mat=body_m, collection=coll)
    cab = H.add_box(f"{name}_cab", size=(1.0, 0.8, 0.4), location=(loc[0], loc[1], loc[2] + 0.75), mat=glass, collection=coll)
    parts = [body, cab]
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        w = H.add_cylinder(f"{name}_wheel", radius=0.22, depth=0.16, location=(loc[0] + dx * 0.6, loc[1] + dy * 0.45, loc[2] + 0.05), verts=14, mat=tyre, collection=coll)
        w.rotation_euler = (math.radians(90), 0, 0)
        parts.append(w)
    return H.join_objects(name, parts, coll, body_m)


def tree_prop(name, loc, mats, coll):
    trunk = _m(mats, "trunk", "wood")
    leaf = _m(mats, "leaf", "fabric")
    return H.join_objects(name, H.create_tree(name, location=loc, scale=1.1, collection=coll, trunk_mat=trunk, leaf_mat=leaf), coll, trunk)


def fence(name, loc, mats, coll):
    wood = _m(mats, "wood", "metal")
    parts = []
    for i in range(4):
        parts.append(H.add_box(f"{name}_post", size=(0.06, 0.06, 0.8), location=(loc[0] + i * 0.5 - 0.75, loc[1], loc[2]), mat=wood, collection=coll))
    for z in (0.3, 0.6):
        parts.append(H.add_box(f"{name}_rail", size=(2.0, 0.04, 0.06), location=(loc[0], loc[1], loc[2] + z), mat=wood, collection=coll))
    return H.join_objects(name, parts, coll, wood)


def road_tile(name, loc, mats, coll):
    road = _m(mats, "road", "concrete", "dark")
    t = H.add_box(f"{name}_t", size=(4.0, 4.0, 0.1), location=loc, mat=road, collection=coll)
    return H.join_objects(name, [t], coll, road)


# --------------------------------------------------------------------------- #
# Interior furniture
# --------------------------------------------------------------------------- #
def sofa(name, loc, mats, coll):
    fabric = _m(mats, "fabric", "leather", "wood")
    return H.join_objects(name, H.create_sofa(name, location=loc, mat=fabric, collection=coll), coll, fabric)


def armchair(name, loc, mats, coll):
    fabric = _m(mats, "fabric", "leather", "wood")
    base = H.add_box(f"{name}_base", size=(0.9, 0.9, 0.4), location=loc, mat=fabric, collection=coll)
    back = H.add_box(f"{name}_back", size=(0.9, 0.18, 0.6), location=(loc[0], loc[1] - 0.36, loc[2] + 0.4), mat=fabric, collection=coll)
    parts = [base, back]
    for dx in (-1, 1):
        parts.append(H.add_box(f"{name}_arm", size=(0.16, 0.9, 0.45), location=(loc[0] + dx * 0.37, loc[1], loc[2] + 0.25), mat=fabric, collection=coll))
    return H.join_objects(name, parts, coll, fabric)


def coffee_table(name, loc, mats, coll):
    wood = _m(mats, "wood")
    return H.join_objects(name, H.create_table(name, location=loc, w=1.1, d=0.6, h=0.42, mat=wood, collection=coll), coll, wood)


def cabinet(name, loc, mats, coll):
    wood = _m(mats, "wood")
    return H.join_objects(name, [H.create_cabinet(name, location=loc, mat=wood, collection=coll)], coll, wood)


def floor_lamp(name, loc, mats, coll):
    metal = _m(mats, "metal", "dark", "wood")
    shade = _m(mats, "fabric", "ceramic", "wood")
    base = H.add_cylinder(f"{name}_base", radius=0.18, depth=0.05, location=loc, verts=16, mat=metal, collection=coll)
    pole = H.add_cylinder(f"{name}_pole", radius=0.03, depth=1.5, location=(loc[0], loc[1], loc[2] + 0.05), verts=8, mat=metal, collection=coll)
    sh = H.add_cone(f"{name}_shade", radius=0.22, depth=0.3, location=(loc[0], loc[1], loc[2] + 1.45), verts=16, mat=shade, collection=coll)
    return H.join_objects(name, [base, pole, sh], coll, metal)


def tv_wall(name, loc, mats, coll):
    dark = _m(mats, "dark", "metal", "wood")
    panel = H.add_box(f"{name}_panel", size=(1.8, 0.06, 1.0), location=(loc[0], loc[1], loc[2] + 0.9), mat=dark, collection=coll)
    return H.join_objects(name, [panel], coll, dark)


def carpet(name, loc, mats, coll):
    fabric = _m(mats, "fabric", "leather", "wood")
    r = H.add_box(f"{name}_r", size=(2.4, 1.8, 0.03), location=loc, mat=fabric, collection=coll)
    return H.join_objects(name, [r], coll, fabric)
