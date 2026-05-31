"""Reusable Blender modeling/material/scene helpers.

Every helper is written defensively so the generation engine produces clean,
intentional scenes: named objects, assigned materials, sensible origins and
collection organization.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

import bpy
import bmesh
from mathutils import Vector

WORKSPACE_COLLECTIONS = (
    "Architecture",
    "Furniture",
    "Props",
    "Environment",
    "Lighting",
    "Cameras",
)


# --------------------------------------------------------------------------- #
# Collections
# --------------------------------------------------------------------------- #
def get_or_create_collection(name: str, parent: Optional[bpy.types.Collection] = None) -> bpy.types.Collection:
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    coll = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(coll)
    return coll


def link_to_collection(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    collection.objects.link(obj)


# --------------------------------------------------------------------------- #
# Materials
# --------------------------------------------------------------------------- #
def make_material(
    name: str,
    color=(0.6, 0.6, 0.6, 1.0),
    metallic: float = 0.0,
    roughness: float = 0.5,
    emission_strength: float = 0.0,
    emission_color=None,
) -> bpy.types.Material:
    """Create (or fetch) a Principled BSDF material."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color if len(color) == 4 else (*color, 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = next((node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    if bsdf:
        if len(color) == 3:
            color = (*color, 1.0)
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
        # Emission inputs renamed across Blender versions; set defensively.
        ecol = emission_color or color
        if len(ecol) == 3:
            ecol = (*ecol, 1.0)
        for key in ("Emission Color", "Emission"):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = ecol
                break
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


def assign_material(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    obj.data.materials.clear()
    obj.data.materials.append(mat)


# --------------------------------------------------------------------------- #
# Primitives
# --------------------------------------------------------------------------- #
def _finish(obj: bpy.types.Object, name: str, collection, mat) -> bpy.types.Object:
    obj.name = name
    if obj.data is not None:
        obj.data.name = name
    if mat is not None:
        assign_material(obj, mat)
    if collection is not None:
        link_to_collection(obj, collection)
    return obj


def add_box(name, size=(1, 1, 1), location=(0, 0, 0), collection=None, mat=None) -> bpy.types.Object:
    """Add a box whose base sits on its Z origin (good pivot for props/buildings)."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    sx, sy, sz = size
    obj.scale = (sx, sy, sz)
    # raise so the base sits at location.z
    obj.location = (location[0], location[1], location[2] + sz / 2.0)
    return _finish(obj, name, collection, mat)


def add_plane(name, size=(10, 10), location=(0, 0, 0), collection=None, mat=None) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.0)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.scale = (size[0] / 2.0, size[1] / 2.0, 1.0)
    obj.location = location
    return _finish(obj, name, collection, mat)


def add_cylinder(name, radius=0.5, depth=1.0, location=(0, 0, 0), verts=24, collection=None, mat=None):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=verts,
        radius1=radius, radius2=radius, depth=depth,
    )
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = (location[0], location[1], location[2] + depth / 2.0)
    return _finish(obj, name, collection, mat)


def add_cone(name, radius=1.0, depth=1.0, location=(0, 0, 0), verts=24, collection=None, mat=None):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=True, segments=verts,
        radius1=radius, radius2=0.0, depth=depth,
    )
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = (location[0], location[1], location[2] + depth / 2.0)
    return _finish(obj, name, collection, mat)


def add_sphere(name, radius=0.5, location=(0, 0, 0), collection=None, mat=None):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=12, radius=radius)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    return _finish(obj, name, collection, mat)


# --------------------------------------------------------------------------- #
# Composite helpers (named in the spec)
# --------------------------------------------------------------------------- #
def create_wall(name, length=4.0, height=2.7, thickness=0.15, location=(0, 0, 0), axis="x", collection=None, mat=None):
    size = (length, thickness, height) if axis == "x" else (thickness, length, height)
    return add_box(name, size=size, location=location, collection=collection, mat=mat)


def create_floor(name, width=6.0, depth=6.0, location=(0, 0, 0), collection=None, mat=None):
    return add_plane(name, size=(width, depth), location=location, collection=collection, mat=mat)


def create_window(name, width=1.2, height=1.4, location=(0, 0, 1.2), collection=None, mat=None):
    return add_box(name, size=(width, 0.08, height), location=(location[0], location[1], location[2] - height / 2), collection=collection, mat=mat)


def create_door(name, width=0.9, height=2.1, location=(0, 0, 0), collection=None, mat=None):
    return add_box(name, size=(width, 0.1, height), location=location, collection=collection, mat=mat)


def create_stairs(name, steps=8, width=1.2, rise=0.18, run=0.28, location=(0, 0, 0), collection=None, mat=None):
    objs = []
    for i in range(steps):
        s = add_box(
            f"{name}_step_{i:02d}",
            size=(width, run, rise),
            location=(location[0], location[1] + i * run, location[2] + i * rise),
            collection=collection, mat=mat,
        )
        objs.append(s)
    return objs


def create_roof(name, footprint=6.0, height=2.0, style="gable", location=(0, 0, 0), collection=None, mat=None):
    if style == "flat":
        return add_box(name, size=(footprint, footprint, 0.2), location=location, collection=collection, mat=mat)
    roof = add_cone(name, radius=footprint * 0.75, depth=height, location=location, verts=4, collection=collection, mat=mat)
    roof.rotation_euler = (0, 0, math.radians(45))
    return roof


def create_tree(name, location=(0, 0, 0), scale=1.0, collection=None, trunk_mat=None, leaf_mat=None):
    trunk = add_cylinder(f"{name}_trunk", radius=0.12 * scale, depth=1.0 * scale, location=location, verts=8, collection=collection, mat=trunk_mat)
    crown = add_cone(f"{name}_crown", radius=0.7 * scale, depth=1.6 * scale, location=(location[0], location[1], location[2] + 0.9 * scale), verts=8, collection=collection, mat=leaf_mat)
    return [trunk, crown]


def create_road(name, length=20.0, width=3.0, location=(0, 0, 0.01), collection=None, mat=None):
    return add_plane(name, size=(width, length), location=location, collection=collection, mat=mat)


def create_table(name, location=(0, 0, 0), w=1.2, d=0.7, h=0.45, collection=None, mat=None):
    parts = [add_box(f"{name}_top", size=(w, d, 0.05), location=(location[0], location[1], location[2] + h - 0.05), collection=collection, mat=mat)]
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        parts.append(add_box(
            f"{name}_leg", size=(0.06, 0.06, h - 0.05),
            location=(location[0] + dx * (w / 2 - 0.08), location[1] + dy * (d / 2 - 0.08), location[2]),
            collection=collection, mat=mat))
    return parts


def create_chair(name, location=(0, 0, 0), collection=None, mat=None):
    s = 0.45
    parts = [add_box(f"{name}_seat", size=(s, s, 0.05), location=(location[0], location[1], location[2] + 0.43), collection=collection, mat=mat)]
    parts.append(add_box(f"{name}_back", size=(s, 0.05, 0.45), location=(location[0], location[1] - s / 2 + 0.03, location[2] + 0.45), collection=collection, mat=mat))
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        parts.append(add_box(f"{name}_leg", size=(0.04, 0.04, 0.43), location=(location[0] + dx * (s / 2 - 0.05), location[1] + dy * (s / 2 - 0.05), location[2]), collection=collection, mat=mat))
    return parts


def create_sofa(name, location=(0, 0, 0), collection=None, mat=None):
    w, d = 2.0, 0.9
    parts = [add_box(f"{name}_base", size=(w, d, 0.4), location=location, collection=collection, mat=mat)]
    parts.append(add_box(f"{name}_back", size=(w, 0.2, 0.5), location=(location[0], location[1] - d / 2 + 0.1, location[2] + 0.4), collection=collection, mat=mat))
    for dx in (-1, 1):
        parts.append(add_box(f"{name}_arm", size=(0.2, d, 0.55), location=(location[0] + dx * (w / 2 - 0.1), location[1], location[2] + 0.2), collection=collection, mat=mat))
    return parts


def create_cabinet(name, location=(0, 0, 0), w=1.0, d=0.5, h=0.9, collection=None, mat=None):
    return add_box(name, size=(w, d, h), location=location, collection=collection, mat=mat)


def create_shelf(name, location=(0, 0, 0), w=1.2, h=1.8, levels=4, collection=None, mat=None):
    parts = [add_box(f"{name}_frame", size=(w, 0.3, h), location=location, collection=collection, mat=mat)]
    return parts


def create_game_prop(name, kind="crate", location=(0, 0, 0), collection=None, mat=None):
    if kind == "barrel":
        return add_cylinder(name, radius=0.4, depth=0.9, location=location, verts=16, collection=collection, mat=mat)
    if kind == "rock":
        r = add_sphere(name, radius=0.5, location=(location[0], location[1], location[2] + 0.3), collection=collection, mat=mat)
        r.scale = (1.0, 0.8, 0.6)
        return r
    return add_box(name, size=(0.8, 0.8, 0.8), location=location, collection=collection, mat=mat)


def create_emissive_panel(name, location=(0, 0, 0), size=(0.2, 1.5, 0.05), collection=None, mat=None):
    return add_box(name, size=size, location=location, collection=collection, mat=mat)


def create_modular_wall_panel(name, location=(0, 0, 0), grid=2.0, height=3.0, collection=None, mat=None):
    return add_box(name, size=(grid, 0.15, height), location=location, collection=collection, mat=mat)


def create_building_block(name, footprint=6.0, stories=3, location=(0, 0, 0), collection=None, mat=None):
    h = stories * 3.0
    return add_box(name, size=(footprint, footprint, h), location=location, collection=collection, mat=mat)


# --------------------------------------------------------------------------- #
# Origins / transforms
# --------------------------------------------------------------------------- #
def set_origin_bottom_center(obj: bpy.types.Object) -> None:
    if obj.type != "MESH":
        return
    mesh = obj.data
    min_z = min((obj.matrix_world @ v.co).z for v in mesh.vertices) if mesh.vertices else obj.location.z
    # Use cursor-based origin set on the active object.
    bpy.context.view_layer.objects.active = obj
    cursor = bpy.context.scene.cursor.location.copy()
    bpy.context.scene.cursor.location = Vector((obj.location.x, obj.location.y, min_z))
    try:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    finally:
        bpy.context.scene.cursor.location = cursor


def select_only(objs: Iterable[bpy.types.Object]) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    objs = list(objs)
    for o in objs:
        o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]


def all_mesh_objects():
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def join_objects(name, objs, collection=None, mat=None):
    """Join a list of mesh objects into a single named asset with a clean pivot."""
    objs = [o for o in objs if o and o.type == "MESH"]
    if not objs:
        return None
    if len(objs) == 1:
        obj = objs[0]
    else:
        select_only(objs)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.join()
        obj = bpy.context.view_layer.objects.active
    obj.name = name
    if obj.data:
        obj.data.name = name
    if mat is not None:
        # keep existing multi-material assets; only assign if empty
        if not obj.data.materials:
            assign_material(obj, mat)
    if collection is not None:
        link_to_collection(obj, collection)
    try:
        set_origin_bottom_center(obj)
    except Exception:
        pass
    return obj


def poly_count(obj) -> int:
    return len(obj.data.polygons) if obj and obj.type == "MESH" else 0


def hide_all_except(keep):
    keep_set = set(keep)
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            o.hide_render = o not in keep_set


def show_all():
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            o.hide_render = False
