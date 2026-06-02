"""Particle, scatter and vegetation system — built for game export.

Why this exists: classic Blender particle systems and hair do NOT export to
FBX/glTF, so the professional game pipeline is "scatter with Geometry Nodes →
Realize Instances → real mesh". This module makes that the easy path, while
still supporting classic particle hair/fur for look-dev and a bake step that
turns either kind into an exportable mesh.

Ops:
  * scatter_objects     — scatter a source object over a surface (GN, realized,
    exportable) with density, seed, random scale & rotation, normal align.
  * scatter_collection  — scatter random picks from a collection (rocks, props).
  * create_grass_field  — stylized game grass blades on a surface.
  * scatter_debris      — quick rock/debris scatter for environment art.
  * add_hair_fur        — classic hair particle system (fur) for look-dev.
  * convert_to_mesh     — realize a GN scatter / make particle instances real →
    a single exportable mesh.

All GN graphs are built through the safe node engine; nothing executes
caller-supplied code.
"""
from __future__ import annotations

import math

import bpy

from . import helpers as H
from . import node_design_ops as ND


# --------------------------------------------------------------------------- #
# Low-level: build a scatter Geometry-Nodes graph on `obj`
# --------------------------------------------------------------------------- #
def _set_node_input(node, key, value):
    sock = ND._resolve_socket(node.inputs, key)
    return ND._set_socket_default(sock, value)


def _link(ng, a, a_sock, b, b_sock):
    out = ND._resolve_socket(a.outputs, a_sock)
    inp = ND._resolve_socket(b.inputs, b_sock)
    if out is not None and inp is not None:
        try:
            ng.links.new(out, inp)
            return True
        except (RuntimeError, TypeError):
            return False
    return False


def _fresh_gn(obj, tree_name):
    mod = obj.modifiers.new(name=tree_name, type="NODES")
    ng = bpy.data.node_groups.new(tree_name, "GeometryNodeTree")
    mod.node_group = ng
    ND._ensure_geo_io(ng)
    return mod, ng


def _build_scatter_graph(obj, *, instance_source=None, collection_source=None,
                         density=10.0, seed=0, scale_min=0.8, scale_max=1.2,
                         align_normal=True, random_yaw=True, realize=True,
                         tree_name="Scatter"):
    """Assemble a distribute→instance→realize GN graph. Returns the modifier."""
    mod, ng = _fresh_gn(obj, tree_name)
    nodes = ng.nodes
    gin = next((n for n in nodes if n.bl_idname == "NodeGroupInput"), None) or nodes.new("NodeGroupInput")
    gout = next((n for n in nodes if n.bl_idname == "NodeGroupOutput"), None) or nodes.new("NodeGroupOutput")
    gin.location = (-800, 0)
    gout.location = (800, 0)

    distribute = nodes.new("GeometryNodeDistributePointsOnFaces")
    distribute.location = (-520, 0)
    _set_node_input(distribute, "Density", float(density))
    _set_node_input(distribute, "Seed", int(seed))

    # source geometry: object OR collection
    if collection_source is not None:
        src = nodes.new("GeometryNodeCollectionInfo")
        src.location = (-520, -260)
        try:
            src.inputs["Collection"].default_value = collection_source
        except (KeyError, TypeError, AttributeError):
            pass
        for attr in ("Separate Children", "Pick Instance"):
            ND._set_socket_default(ND._resolve_socket(src.inputs, attr), True)
        src_out = "Instances"
    else:
        src = nodes.new("GeometryNodeObjectInfo")
        src.location = (-520, -260)
        if instance_source is not None:
            try:
                src.inputs["Object"].default_value = instance_source
            except (KeyError, TypeError, AttributeError):
                pass
        try:
            src.transform_space = "RELATIVE"
        except (AttributeError, TypeError):
            pass
        src_out = "Geometry"

    inst = nodes.new("GeometryNodeInstanceOnPoints")
    inst.location = (-180, 0)

    # random scale
    rscale = nodes.new("FunctionNodeRandomValue")
    rscale.location = (-180, -300)
    try:
        rscale.data_type = "FLOAT_VECTOR"
    except (AttributeError, TypeError):
        pass
    _set_node_input(rscale, "Min", (scale_min, scale_min, scale_min))
    _set_node_input(rscale, "Max", (scale_max, scale_max, scale_max))
    _set_node_input(rscale, "Seed", int(seed) + 1)

    _link(ng, gin, "Geometry", distribute, "Mesh")
    _link(ng, distribute, "Points", inst, "Points")
    _link(ng, src, src_out, inst, "Instance")
    _link(ng, rscale, "Value", inst, "Scale")
    if align_normal:
        _link(ng, distribute, "Rotation", inst, "Rotation")

    tail = inst
    if realize:
        rz = nodes.new("GeometryNodeRealizeInstances")
        rz.location = (180, 0)
        _link(ng, inst, "Instances", rz, "Geometry")
        tail = rz
    _link(ng, tail, "Geometry", gout, "Geometry")
    return mod, ng


# --------------------------------------------------------------------------- #
# Public ops
# --------------------------------------------------------------------------- #
def op_scatter_objects(params: dict) -> dict:
    """Scatter copies of a source object over a target surface (game-ready).

    params: target (surface object), source (object to instance), density,
            seed, scale_min, scale_max, align_normal, realize (default True).
    """
    target = bpy.data.objects.get(params.get("target"))
    if target is None:
        return {"ok": False, "error": f"target '{params.get('target')}' not found"}
    source = bpy.data.objects.get(params.get("source")) if params.get("source") else None
    mod, ng = _build_scatter_graph(
        target, instance_source=source,
        density=params.get("density", 10.0), seed=params.get("seed", 0),
        scale_min=params.get("scale_min", 0.8), scale_max=params.get("scale_max", 1.2),
        align_normal=params.get("align_normal", True),
        realize=params.get("realize", True),
        tree_name=params.get("tree_name", f"{target.name}_Scatter"),
    )
    return {"ok": True, "target": target.name, "source": getattr(source, "name", None),
            "modifier": mod.name, "tree": ng.name,
            "exportable": params.get("realize", True),
            "hint": "Source object set? If not, set its 'Object' input or pass 'source'."}


def op_scatter_collection(params: dict) -> dict:
    """Scatter random picks from a collection over a surface (rocks, props, trees).

    params: target, collection (name), density, seed, scale_min, scale_max,
            align_normal, realize.
    """
    target = bpy.data.objects.get(params.get("target"))
    if target is None:
        return {"ok": False, "error": f"target '{params.get('target')}' not found"}
    coll = bpy.data.collections.get(params.get("collection")) if params.get("collection") else None
    if coll is None:
        return {"ok": False, "error": f"collection '{params.get('collection')}' not found"}
    mod, ng = _build_scatter_graph(
        target, collection_source=coll,
        density=params.get("density", 5.0), seed=params.get("seed", 0),
        scale_min=params.get("scale_min", 0.8), scale_max=params.get("scale_max", 1.2),
        align_normal=params.get("align_normal", True),
        realize=params.get("realize", True),
        tree_name=params.get("tree_name", f"{target.name}_FoliageScatter"),
    )
    return {"ok": True, "target": target.name, "collection": coll.name,
            "modifier": mod.name, "tree": ng.name,
            "exportable": params.get("realize", True)}


def op_create_grass_field(params: dict) -> dict:
    """Build a stylized, game-ready grass field on a surface (GN, realized).

    params: target (surface), density (default 50), height (default 0.3),
            seed. Instances thin cone blades with random scale + yaw.
    """
    target = bpy.data.objects.get(params.get("target"))
    if target is None:
        return {"ok": False, "error": f"target '{params.get('target')}' not found"}
    height = float(params.get("height", 0.3))

    # blade source: a thin tall cone
    blade = H.add_cone(f"{target.name}_GrassBlade", radius=0.02, depth=height,
                       location=(0, 0, -1000))  # parked off-scene; GN instances it
    mat = H.make_material("Game_Grass", color=(0.30, 0.62, 0.24), roughness=0.85)
    H.assign_material(blade, mat)

    mod, ng = _build_scatter_graph(
        target, instance_source=blade,
        density=params.get("density", 50.0), seed=params.get("seed", 0),
        scale_min=params.get("scale_min", 0.7), scale_max=params.get("scale_max", 1.3),
        align_normal=params.get("align_normal", True), realize=True,
        tree_name=f"{target.name}_GrassField",
    )
    return {"ok": True, "target": target.name, "blade": blade.name,
            "modifier": mod.name, "material": mat.name, "exportable": True}


def op_scatter_debris(params: dict) -> dict:
    """Scatter low-poly rock/debris chunks over a surface for environment art.

    params: target, count_hint (density), seed, scale_min, scale_max.
    Creates a small ico-rock source then GN-scatters & realizes it.
    """
    target = bpy.data.objects.get(params.get("target"))
    if target is None:
        return {"ok": False, "error": f"target '{params.get('target')}' not found"}
    rock = H.add_sphere(f"{target.name}_Rock", radius=0.15, location=(0, 0, -1000))
    mat = H.make_material("Game_Rock", color=(0.32, 0.30, 0.28), roughness=0.9)
    H.assign_material(rock, mat)
    mod, ng = _build_scatter_graph(
        target, instance_source=rock,
        density=params.get("density", 8.0), seed=params.get("seed", 3),
        scale_min=params.get("scale_min", 0.5), scale_max=params.get("scale_max", 1.6),
        align_normal=False, realize=True,
        tree_name=f"{target.name}_Debris",
    )
    return {"ok": True, "target": target.name, "rock": rock.name,
            "modifier": mod.name, "material": mat.name, "exportable": True}


def op_add_hair_fur(params: dict) -> dict:
    """Add a classic hair particle system (fur) to an object for look-dev.

    params: object, count (default 1000), length (default 0.1), seed.
    NOTE: hair particles do NOT export to FBX/glTF — call convert_to_mesh, or
    prefer create_grass_field/scatter_objects for game assets.
    """
    obj = bpy.data.objects.get(params.get("object"))
    if obj is None:
        return {"ok": False, "error": f"object '{params.get('object')}' not found"}
    psys_mod = obj.modifiers.new(name="Fur", type="PARTICLE_SYSTEM")
    psys = obj.particle_systems[-1] if obj.particle_systems else None
    settings = psys.settings if psys else getattr(psys_mod, "particle_system", None)
    if settings is None:
        return {"ok": False, "error": "could not access particle settings"}
    s = settings.settings if hasattr(settings, "settings") else settings
    try:
        s.type = "HAIR"
        s.count = int(params.get("count", 1000))
        s.hair_length = float(params.get("length", 0.1))
        s.use_advanced_hair = True
    except (AttributeError, TypeError):
        pass
    return {"ok": True, "object": obj.name, "system": "Fur",
            "count": params.get("count", 1000),
            "warning": "Hair particles are not export-ready; use convert_to_mesh "
                       "or a Geometry-Nodes scatter for game assets."}


def op_convert_particles_to_mesh(params: dict) -> dict:
    """Make a scatter exportable: apply GN modifiers and/or realize particle
    instances into real mesh data on the object.

    params: object, apply_modifiers (default True).
    """
    obj = bpy.data.objects.get(params.get("object"))
    if obj is None:
        return {"ok": False, "error": f"object '{params.get('object')}' not found"}

    applied = []
    # ensure active/selected for ops that need context
    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
    except (AttributeError, RuntimeError):
        pass

    # 1) make any particle-instanced duplicates real, then convert visual geo
    try:
        bpy.ops.object.duplicates_make_real()
    except (RuntimeError, AttributeError):
        pass

    # 2) apply NODES (Geometry Nodes) modifiers so the realized mesh is permanent
    if params.get("apply_modifiers", True):
        for mod in list(obj.modifiers):
            if mod.type in {"NODES", "PARTICLE_SYSTEM"}:
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                    applied.append(mod.name)
                except (RuntimeError, TypeError):
                    try:
                        obj.modifiers.remove(mod)
                    except RuntimeError:
                        pass
    return {"ok": True, "object": obj.name, "applied_modifiers": applied,
            "exportable": True}
