"""Procedural organic-mesh engine.

The original generators glued together separate UV-sphere / cube / cone
primitives. That reads as "geometric / amateur" because every limb is a
visible, disconnected blob. This module builds **single, seamless, watertight
organic meshes** instead, using techniques that ship with Blender and require
zero external installs or APIs:

  * Skin Modifier  -> turns a vertex/edge skeleton into a continuous tubular
    body whose limbs and torso are fused at branch points.
  * Subdivision    -> smooths the skinned cage into an organic surface.
  * Voxel Remesh   -> fuses any overlapping volumes (body + head + armour)
    into ONE watertight manifold mesh with even topology.
  * Procedural Displacement -> adds muscle / cloth / surface micro-relief from
    noise textures so the silhouette is not perfectly smooth and "plastic".

Every public helper is defensive across Blender 3.x / 4.x (input socket names
and a few ops were renamed) so a generation run never hard-crashes.
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

import bpy
import bmesh
from mathutils import Vector

from . import helpers as H


# --------------------------------------------------------------------------- #
# Version-defensive socket helpers
# --------------------------------------------------------------------------- #
def _set_input(bsdf, names, value):
    """Set the first matching Principled BSDF input (names change per version)."""
    if bsdf is None:
        return False
    if isinstance(names, str):
        names = (names,)
    for n in names:
        if n in bsdf.inputs:
            try:
                bsdf.inputs[n].default_value = value
                return True
            except Exception:
                continue
    return False


# --------------------------------------------------------------------------- #
# Advanced materials (skin / hair / fabric) with subsurface scattering
# --------------------------------------------------------------------------- #
def make_skin_material(name, color=(0.78, 0.52, 0.4, 1.0), style="realistic"):
    """Principled skin shader with subsurface scattering for believable flesh."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    if len(color) == 3:
        color = (*color, 1.0)
    mat.diffuse_color = color
    bsdf = mat.node_tree.nodes.get("Principled BSDF") or next(
        (n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None
    )
    if bsdf:
        _set_input(bsdf, "Base Color", color)
        if style == "realistic":
            # Blender 4.x uses "Subsurface Weight"; 3.x uses "Subsurface".
            _set_input(bsdf, ("Subsurface Weight", "Subsurface"), 0.18)
            _set_input(bsdf, ("Subsurface Radius",), (0.36, 0.16, 0.10))
            _set_input(bsdf, ("Subsurface Color",), (0.9, 0.45, 0.38, 1.0))
            _set_input(bsdf, "Roughness", 0.46)
            _set_input(bsdf, ("Specular IOR Level", "Specular"), 0.4)
        else:  # stylized -> flatter, cleaner read
            _set_input(bsdf, ("Subsurface Weight", "Subsurface"), 0.06)
            _set_input(bsdf, "Roughness", 0.62)
            _set_input(bsdf, ("Specular IOR Level", "Specular"), 0.25)
        _set_input(bsdf, "Metallic", 0.0)
    return mat


def make_hair_material(name, color=(0.04, 0.028, 0.022, 1.0), style="realistic"):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    if len(color) == 3:
        color = (*color, 1.0)
    mat.diffuse_color = color
    bsdf = mat.node_tree.nodes.get("Principled BSDF") or next(
        (n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None
    )
    if bsdf:
        _set_input(bsdf, "Base Color", color)
        _set_input(bsdf, "Roughness", 0.32 if style == "realistic" else 0.5)
        # anisotropic sheen reads as hair strands under lighting
        _set_input(bsdf, ("Anisotropic", "Anisotropy"), 0.65)
        _set_input(bsdf, "Metallic", 0.0)
    return mat


def make_fabric_material(name, color, roughness=0.78, style="realistic"):
    return H.make_material(name, color=color, metallic=0.0,
                           roughness=roughness if style == "realistic" else roughness * 0.9)


# --------------------------------------------------------------------------- #
# Skin-modifier body builder
# --------------------------------------------------------------------------- #
def build_skin_body(name, joints, bones, radii, collection,
                    subsurf=2, smooth_shade=True):
    """Build ONE organic mesh from a skeleton via the Skin modifier.

    Parameters
    ----------
    joints : dict[str, (x, y, z)]
        Named joint positions.
    bones : list[(joint_a, joint_b)]
        Edges connecting joints; the skin modifier inflates these into tubes
        and automatically fuses them at shared joints (branch points).
    radii : dict[str, (rx, ry)]
        Per-joint skin radius (controls limb thickness). Missing joints fall
        back to a sensible default.
    """
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    order = list(joints.keys())
    index = {jn: i for i, jn in enumerate(order)}
    verts = [bm.verts.new(joints[jn]) for jn in order]
    bm.verts.ensure_lookup_table()
    for a, b in bones:
        try:
            bm.edges.new((verts[index[a]], verts[index[b]]))
        except (KeyError, ValueError):
            continue
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    H.link_to_collection(obj, collection)

    skin = obj.modifiers.new("skin", "SKIN")
    # use smooth interpolation between branch points
    try:
        skin.use_smooth_shade = True
    except Exception:
        pass

    # Per-vertex skin radii
    skin_layer = obj.data.skin_vertices[0].data
    default = (0.12, 0.12)
    for jn, i in index.items():
        rx, ry = radii.get(jn, default)
        skin_layer[i].radius = (rx, ry)
    # mark the pelvis/root vertex so the skin modifier has a stable root
    root_name = "pelvis" if "pelvis" in index else order[0]
    try:
        skin_layer[index[root_name]].use_root = True
    except Exception:
        pass

    if subsurf:
        sub = obj.modifiers.new("subsurf", "SUBSURF")
        sub.levels = subsurf
        sub.render_levels = subsurf

    if smooth_shade:
        bpy.context.view_layer.objects.active = obj
        try:
            bpy.ops.object.shade_smooth()
        except Exception:
            pass
    return obj


# --------------------------------------------------------------------------- #
# Mesh fusion / detailing
# --------------------------------------------------------------------------- #
def apply_all_modifiers(obj):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    for mod in list(obj.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception:
            pass


def unify_meshes(objs, name, collection, voxel_size=0.05):
    """Join a list of meshes and voxel-remesh them into one watertight surface.

    This is what turns "a pile of overlapping primitives" into a single,
    seamless model. Returns the unified object.
    """
    objs = [o for o in objs if o and o.type == "MESH"]
    if not objs:
        return None
    # bake any modifiers first so the remesh sees real geometry
    for o in objs:
        apply_all_modifiers(o)

    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        try:
            bpy.ops.object.join()
        except Exception:
            pass
    obj = bpy.context.view_layer.objects.active
    obj.name = name
    if obj.data:
        obj.data.name = name
    if collection is not None:
        H.link_to_collection(obj, collection)

    # Voxel remesh -> single manifold, even topology
    try:
        obj.data.remesh_voxel_size = voxel_size
        obj.data.remesh_voxel_adaptivity = 0.0
        bpy.ops.object.voxel_remesh()
    except Exception:
        pass
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    if "weighted_normals" not in obj.modifiers:
        obj.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
    return obj


def add_surface_detail(obj, kind="muscle", strength=0.012, scale=4.0):
    """Add procedural micro-relief so the surface is not perfectly smooth.

    kind: 'muscle' (organic flesh), 'cloth' (fabric folds), 'rough' (rocky).
    Uses a Displace modifier driven by a procedural texture -> no image needed.
    """
    if not obj or obj.type != "MESH":
        return None
    tex_name = f"{obj.name}_{kind}_detail"
    tex = bpy.data.textures.get(tex_name)
    if tex is None:
        if kind == "cloth":
            tex = bpy.data.textures.new(tex_name, "WOOD")
            try:
                tex.noise_scale = 0.25
                tex.turbulence = 6.0
            except Exception:
                pass
        elif kind == "rough":
            tex = bpy.data.textures.new(tex_name, "VORONOI")
        else:  # muscle / organic
            tex = bpy.data.textures.new(tex_name, "MUSGRAVE") if hasattr(bpy.data.textures, "new") else None
            try:
                tex = tex or bpy.data.textures.new(tex_name, "CLOUDS")
            except Exception:
                pass
            try:
                tex.noise_scale = 0.4
            except Exception:
                pass
    # MUSGRAVE was removed in some 4.x builds; fall back to CLOUDS.
    if tex is None:
        tex = bpy.data.textures.new(tex_name, "CLOUDS")

    mod = obj.modifiers.get(f"detail_{kind}") or obj.modifiers.new(f"detail_{kind}", "DISPLACE")
    mod.texture = tex
    mod.strength = strength
    mod.mid_level = 0.5
    try:
        mod.texture_coords = "LOCAL"
    except Exception:
        pass
    return mod


def smooth_finalize(obj, subsurf=1):
    """Final smoothing pass for a clean render-ready surface."""
    if not obj or obj.type != "MESH":
        return obj
    if subsurf and "final_subsurf" not in obj.modifiers:
        m = obj.modifiers.new("final_subsurf", "SUBSURF")
        m.levels = subsurf
        m.render_levels = max(subsurf, 2)
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    return obj


# --------------------------------------------------------------------------- #
# Auto-weight bind to an armature (single mesh -> rig)
# --------------------------------------------------------------------------- #
def bind_to_armature(mesh_obj, arm):
    if not mesh_obj or not arm:
        return False
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    try:
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        return True
    except Exception:
        try:
            bpy.ops.object.parent_set(type="ARMATURE_NAME")
        except Exception:
            pass
        return False
