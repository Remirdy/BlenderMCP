"""Node-based design engine — Geometry Nodes & Shader Nodes.

This is the "design with nodes" capability. The rest of the add-on builds
geometry imperatively (primitives + modifiers). This module lets the AI design
*procedurally* by declaring a node graph and having it built safely inside
Blender.

Two ways to use it:

  1. Declarative graph spec  (``build_geometry_node_graph`` /
     ``build_shader_node_graph``):  the caller passes a JSON-ish description of
     nodes + links and we assemble the real node tree.  This is the open-ended
     "design anything with nodes" path.

  2. Curated presets  (``apply_geometry_node_preset`` /
     ``apply_shader_node_preset``):  known-good graphs (scatter, array, noise
     displace, procedural wood/marble/bricks, fresnel rim, …) so the AI gets a
     professional result in one call without hand-wiring every socket.

A read-back op (``inspect_node_graph``) returns the existing tree so the AI can
iterate: build → inspect → tweak, a true node-design loop.

Safety: this module never executes caller-supplied Python.  It only creates
nodes whose ``bl_idname`` is on an allow-list of Blender node classes, mirroring
the registry's "no arbitrary code" guarantee.
"""
from __future__ import annotations

from typing import Any

import bpy

from . import helpers as H

# --------------------------------------------------------------------------- #
# Safety: only node classes whose id starts with one of these may be created.
# These are all built-in, side-effect-free Blender node families.
# --------------------------------------------------------------------------- #
_ALLOWED_NODE_PREFIXES = (
    "GeometryNode",
    "ShaderNode",
    "FunctionNode",
    "CompositorNode",
    "NodeGroupInput",
    "NodeGroupOutput",
    "NodeReroute",
    "NodeFrame",
)

# Map a friendly socket-type keyword to the Blender socket bl_idname.
_SOCKET_TYPES = {
    "GEOMETRY": "NodeSocketGeometry",
    "FLOAT": "NodeSocketFloat",
    "INT": "NodeSocketInt",
    "BOOL": "NodeSocketBool",
    "VECTOR": "NodeSocketVector",
    "COLOR": "NodeSocketColor",
    "STRING": "NodeSocketString",
    "OBJECT": "NodeSocketObject",
    "MATERIAL": "NodeSocketMaterial",
}


def _socket_bl_idname(kind: str) -> str:
    kind = (kind or "FLOAT").upper()
    if kind.startswith("NodeSocket"):
        return kind
    return _SOCKET_TYPES.get(kind, "NodeSocketFloat")


def _node_type_allowed(node_type: str) -> bool:
    return isinstance(node_type, str) and node_type.startswith(_ALLOWED_NODE_PREFIXES)


# --------------------------------------------------------------------------- #
# Version-defensive interface (group input/output socket) helpers
# --------------------------------------------------------------------------- #
def _new_interface_socket(ng, name: str, in_out: str, socket_type: str):
    """Add a group I/O socket across Blender 3.x and 4.x APIs."""
    # Blender 4.x: node_group.interface.new_socket(...)
    iface = getattr(ng, "interface", None)
    if iface is not None and hasattr(iface, "new_socket"):
        try:
            return iface.new_socket(name=name, in_out=in_out, socket_type=socket_type)
        except TypeError:
            return iface.new_socket(name, in_out=in_out, socket_type=socket_type)
    # Blender 3.x: node_group.inputs.new / node_group.outputs.new
    coll = ng.inputs if in_out == "INPUT" else ng.outputs
    return coll.new(socket_type, name)


def _ensure_geo_io(ng) -> None:
    """Guarantee a Geometry input and Geometry output socket exist on a GN tree."""
    def _has(in_out: str) -> bool:
        iface = getattr(ng, "interface", None)
        if iface is not None and hasattr(iface, "items_tree"):
            return any(
                getattr(it, "in_out", None) == in_out
                and getattr(it, "socket_type", "") == "NodeSocketGeometry"
                for it in iface.items_tree
            )
        coll = ng.inputs if in_out == "INPUT" else ng.outputs
        return any(s.type == "GEOMETRY" for s in coll)

    if not _has("INPUT"):
        _new_interface_socket(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    if not _has("OUTPUT"):
        _new_interface_socket(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")


# --------------------------------------------------------------------------- #
# Socket addressing helpers (by name OR integer index)
# --------------------------------------------------------------------------- #
def _resolve_socket(sockets, key):
    """Find a socket by name (str) or position (int). Returns socket or None."""
    if isinstance(key, int):
        # index across *enabled* sockets to match what the user sees
        enabled = [s for s in sockets if getattr(s, "enabled", True)]
        if 0 <= key < len(enabled):
            return enabled[key]
        return None
    # by name — prefer enabled, exact match
    match = [s for s in sockets if s.name == key]
    if not match:
        return None
    for s in match:
        if getattr(s, "enabled", True):
            return s
    return match[0]


def _set_socket_default(socket, value) -> bool:
    if socket is None or not hasattr(socket, "default_value"):
        return False
    try:
        socket.default_value = value
        return True
    except (TypeError, ValueError, AttributeError):
        # e.g. wrong vector length; try best-effort scalar/vector coercion
        try:
            dv = socket.default_value
            if hasattr(dv, "__len__") and not isinstance(value, (list, tuple)):
                for i in range(len(dv)):
                    socket.default_value[i] = value
                return True
        except Exception:  # noqa: BLE001 - never crash a build over one socket
            pass
    return False


# --------------------------------------------------------------------------- #
# Core generic graph builder (shared by geometry + shader)
# --------------------------------------------------------------------------- #
def _build_graph(ng, spec_nodes: list[dict], spec_links: list[dict]) -> dict:
    """Create nodes + links inside an existing node tree from a spec.

    spec_nodes: [{id, type, location?[x,y], inputs?{socket: value}, props?{attr: val}}]
    spec_links: [{from, from_socket, to, to_socket}]
    """
    created: dict[str, Any] = {}
    skipped: list[dict] = []
    warnings: list[str] = []

    for nd in spec_nodes:
        node_type = nd.get("type", "")
        nid = nd.get("id") or node_type
        if not _node_type_allowed(node_type):
            skipped.append({"id": nid, "type": node_type, "reason": "type not allowed"})
            continue
        try:
            node = ng.nodes.new(node_type)
        except (RuntimeError, TypeError) as exc:
            skipped.append({"id": nid, "type": node_type, "reason": str(exc)})
            continue
        node.label = nid
        loc = nd.get("location")
        if isinstance(loc, (list, tuple)) and len(loc) == 2:
            node.location = (float(loc[0]), float(loc[1]))
        # node-level properties (e.g. operation="MULTIPLY", domain="POINT")
        for attr, val in (nd.get("props") or {}).items():
            try:
                setattr(node, attr, val)
            except (AttributeError, TypeError, ValueError):
                warnings.append(f"{nid}: could not set prop '{attr}'")
        # input socket defaults
        for sock_key, val in (nd.get("inputs") or {}).items():
            key = int(sock_key) if isinstance(sock_key, str) and sock_key.isdigit() else sock_key
            if not _set_socket_default(_resolve_socket(node.inputs, key), val):
                warnings.append(f"{nid}: could not set input '{sock_key}'")
        created[nid] = node

    for ln in spec_links:
        a = created.get(ln.get("from"))
        b = created.get(ln.get("to"))
        if a is None or b is None:
            warnings.append(f"link {ln.get('from')}->{ln.get('to')}: node missing")
            continue
        out = _resolve_socket(a.outputs, ln.get("from_socket", 0))
        inp = _resolve_socket(b.inputs, ln.get("to_socket", 0))
        if out is None or inp is None:
            warnings.append(f"link {ln.get('from')}->{ln.get('to')}: socket missing")
            continue
        try:
            ng.links.new(out, inp)
        except (RuntimeError, TypeError) as exc:
            warnings.append(f"link {ln.get('from')}->{ln.get('to')}: {exc}")

    return {
        "nodes_created": list(created.keys()),
        "node_count": len(created),
        "skipped": skipped,
        "warnings": warnings,
    }


def _auto_layout(ng) -> None:
    """Rough left-to-right layout for nodes that arrived without locations."""
    placed = [n for n in ng.nodes if tuple(n.location) == (0.0, 0.0)]
    for i, n in enumerate(placed):
        n.location = (i * 220.0, 0.0)


# --------------------------------------------------------------------------- #
# Geometry Nodes
# --------------------------------------------------------------------------- #
def _get_or_create_gn_modifier(obj, tree_name: str, clear: bool):
    mod = next((m for m in obj.modifiers if m.type == "NODES"), None)
    if mod is None:
        mod = obj.modifiers.new(name="RemirdyNodes", type="NODES")
    ng = mod.node_group
    if ng is None or clear:
        ng = bpy.data.node_groups.new(tree_name, "GeometryNodeTree")
        mod.node_group = ng
    _ensure_geo_io(ng)
    return mod, ng


def op_build_geometry_node_graph(params: dict) -> dict:
    """Build a Geometry Nodes graph on an object from a declarative spec.

    params: object, tree_name?, nodes[], links[], clear? (default True),
            auto_connect_io? (default True) — auto-wire a lone Group Input/Output
            to the first/last node when the spec omits those links.
    """
    obj_name = params.get("object")
    obj = bpy.data.objects.get(obj_name) if obj_name else None
    if obj is None:
        return {"ok": False, "error": f"object '{obj_name}' not found"}

    tree_name = params.get("tree_name", f"{obj.name}_GN")
    mod, ng = _get_or_create_gn_modifier(obj, tree_name, params.get("clear", True))

    nodes = list(params.get("nodes", []))
    links = list(params.get("links", []))

    # Ensure group input/output exist in the spec (add if caller omitted them).
    have_in = any(n.get("type") == "NodeGroupInput" for n in nodes)
    have_out = any(n.get("type") == "NodeGroupOutput" for n in nodes)
    if not have_in:
        nodes.insert(0, {"id": "group_input", "type": "NodeGroupInput", "location": [-400, 0]})
    if not have_out:
        nodes.append({"id": "group_output", "type": "NodeGroupOutput", "location": [600, 0]})

    report = _build_graph(ng, nodes, links)
    _auto_layout(ng)
    return {
        "ok": True,
        "object": obj.name,
        "modifier": mod.name,
        "tree": ng.name,
        **report,
    }


def op_apply_geometry_node_preset(params: dict) -> dict:
    """Apply a curated Geometry Nodes preset to an object.

    presets: scatter_on_surface | procedural_array | displace_noise |
             point_instances | wireframe_tubes | smooth_subdivide
    """
    preset = params.get("preset", "displace_noise")
    obj_name = params.get("object")
    obj = bpy.data.objects.get(obj_name) if obj_name else None
    if obj is None:
        return {"ok": False, "error": f"object '{obj_name}' not found"}

    spec = _GEO_PRESETS.get(preset)
    if spec is None:
        return {"ok": False, "error": f"unknown geometry preset '{preset}'",
                "available": sorted(_GEO_PRESETS.keys())}

    p = dict(params)
    p["nodes"] = spec(params)["nodes"]
    p["links"] = spec(params)["links"]
    p["tree_name"] = params.get("tree_name", f"{obj.name}_{preset}")
    result = op_build_geometry_node_graph(p)
    result["preset"] = preset
    return result


# ---- Geometry preset graph factories (return {nodes, links}) -------------- #
def _geo_displace_noise(params):
    scale = float(params.get("scale", 5.0))
    strength = float(params.get("strength", 0.3))
    return {
        "nodes": [
            {"id": "in", "type": "NodeGroupInput", "location": [-600, 0]},
            {"id": "pos", "type": "GeometryNodeInputPosition", "location": [-600, -200]},
            {"id": "noise", "type": "ShaderNodeTexNoise", "location": [-400, -200],
             "inputs": {"Scale": scale}},
            {"id": "scale_vec", "type": "ShaderNodeVectorMath", "location": [-180, -200],
             "props": {"operation": "SCALE"}, "inputs": {"Scale": strength}},
            {"id": "setpos", "type": "GeometryNodeSetPosition", "location": [120, 0]},
            {"id": "out", "type": "NodeGroupOutput", "location": [420, 0]},
        ],
        "links": [
            {"from": "in", "from_socket": "Geometry", "to": "setpos", "to_socket": "Geometry"},
            {"from": "pos", "from_socket": "Position", "to": "noise", "to_socket": "Vector"},
            {"from": "noise", "from_socket": "Fac", "to": "scale_vec", "to_socket": "Vector"},
            {"from": "scale_vec", "from_socket": "Vector", "to": "setpos", "to_socket": "Offset"},
            {"from": "setpos", "from_socket": "Geometry", "to": "out", "to_socket": "Geometry"},
        ],
    }


def _geo_scatter_on_surface(params):
    density = float(params.get("density", 10.0))
    return {
        "nodes": [
            {"id": "in", "type": "NodeGroupInput", "location": [-600, 0]},
            {"id": "scatter", "type": "GeometryNodeDistributePointsOnFaces",
             "location": [-300, 0], "inputs": {"Density": density}},
            {"id": "ico", "type": "GeometryNodeMeshIcoSphere", "location": [-300, -260],
             "inputs": {"Radius": float(params.get("instance_radius", 0.1))}},
            {"id": "inst", "type": "GeometryNodeInstanceOnPoints", "location": [0, 0]},
            {"id": "realize", "type": "GeometryNodeRealizeInstances", "location": [300, 0]},
            {"id": "out", "type": "NodeGroupOutput", "location": [560, 0]},
        ],
        "links": [
            {"from": "in", "from_socket": "Geometry", "to": "scatter", "to_socket": "Mesh"},
            {"from": "scatter", "from_socket": "Points", "to": "inst", "to_socket": "Points"},
            {"from": "ico", "from_socket": "Mesh", "to": "inst", "to_socket": "Instance"},
            {"from": "inst", "from_socket": "Instances", "to": "realize", "to_socket": "Geometry"},
            {"from": "realize", "from_socket": "Geometry", "to": "out", "to_socket": "Geometry"},
        ],
    }


def _geo_procedural_array(params):
    count = int(params.get("count", 5))
    return {
        "nodes": [
            {"id": "in", "type": "NodeGroupInput", "location": [-600, 0]},
            {"id": "line", "type": "GeometryNodeMeshLine", "location": [-400, -220],
             "inputs": {"Count": count, "Offset": list(params.get("offset", [2.0, 0.0, 0.0]))}},
            {"id": "inst", "type": "GeometryNodeInstanceOnPoints", "location": [-120, 0]},
            {"id": "realize", "type": "GeometryNodeRealizeInstances", "location": [180, 0]},
            {"id": "out", "type": "NodeGroupOutput", "location": [440, 0]},
        ],
        "links": [
            {"from": "line", "from_socket": "Mesh", "to": "inst", "to_socket": "Points"},
            {"from": "in", "from_socket": "Geometry", "to": "inst", "to_socket": "Instance"},
            {"from": "inst", "from_socket": "Instances", "to": "realize", "to_socket": "Geometry"},
            {"from": "realize", "from_socket": "Geometry", "to": "out", "to_socket": "Geometry"},
        ],
    }


def _geo_point_instances(params):
    count = int(params.get("count", 50))
    return {
        "nodes": [
            {"id": "in", "type": "NodeGroupInput", "location": [-600, 0]},
            {"id": "pts", "type": "GeometryNodeDistributePointsInVolume", "location": [-360, 0]},
            {"id": "cube", "type": "GeometryNodeMeshCube", "location": [-360, -260],
             "inputs": {"Size": [0.2, 0.2, 0.2]}},
            {"id": "inst", "type": "GeometryNodeInstanceOnPoints", "location": [-60, 0]},
            {"id": "realize", "type": "GeometryNodeRealizeInstances", "location": [240, 0]},
            {"id": "out", "type": "NodeGroupOutput", "location": [500, 0]},
        ],
        "links": [
            {"from": "in", "from_socket": "Geometry", "to": "pts", "to_socket": "Geometry"},
            {"from": "pts", "from_socket": "Points", "to": "inst", "to_socket": "Points"},
            {"from": "cube", "from_socket": "Mesh", "to": "inst", "to_socket": "Instance"},
            {"from": "inst", "from_socket": "Instances", "to": "realize", "to_socket": "Geometry"},
            {"from": "realize", "from_socket": "Geometry", "to": "out", "to_socket": "Geometry"},
        ],
    }


def _geo_wireframe_tubes(params):
    radius = float(params.get("radius", 0.02))
    return {
        "nodes": [
            {"id": "in", "type": "NodeGroupInput", "location": [-600, 0]},
            {"id": "m2c", "type": "GeometryNodeMeshToCurve", "location": [-360, 0]},
            {"id": "circle", "type": "GeometryNodeCurvePrimitiveCircle", "location": [-360, -240],
             "inputs": {"Radius": radius}},
            {"id": "c2m", "type": "GeometryNodeCurveToMesh", "location": [-60, 0]},
            {"id": "out", "type": "NodeGroupOutput", "location": [240, 0]},
        ],
        "links": [
            {"from": "in", "from_socket": "Geometry", "to": "m2c", "to_socket": "Mesh"},
            {"from": "m2c", "from_socket": "Curve", "to": "c2m", "to_socket": "Curve"},
            {"from": "circle", "from_socket": "Curve", "to": "c2m", "to_socket": "Profile Curve"},
            {"from": "c2m", "from_socket": "Mesh", "to": "out", "to_socket": "Geometry"},
        ],
    }


def _geo_smooth_subdivide(params):
    level = int(params.get("level", 2))
    return {
        "nodes": [
            {"id": "in", "type": "NodeGroupInput", "location": [-400, 0]},
            {"id": "subdiv", "type": "GeometryNodeSubdivisionSurface", "location": [-120, 0],
             "inputs": {"Level": level}},
            {"id": "out", "type": "NodeGroupOutput", "location": [180, 0]},
        ],
        "links": [
            {"from": "in", "from_socket": "Geometry", "to": "subdiv", "to_socket": "Mesh"},
            {"from": "subdiv", "from_socket": "Mesh", "to": "out", "to_socket": "Geometry"},
        ],
    }


_GEO_PRESETS = {
    "displace_noise": _geo_displace_noise,
    "scatter_on_surface": _geo_scatter_on_surface,
    "procedural_array": _geo_procedural_array,
    "point_instances": _geo_point_instances,
    "wireframe_tubes": _geo_wireframe_tubes,
    "smooth_subdivide": _geo_smooth_subdivide,
}


# --------------------------------------------------------------------------- #
# Shader Nodes
# --------------------------------------------------------------------------- #
def _get_or_create_material(name: str, clear: bool):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    if clear:
        nt.nodes.clear()
    return mat, nt


def op_build_shader_node_graph(params: dict) -> dict:
    """Build a shader node graph on a material from a declarative spec.

    params: material, nodes[], links[], clear? (default True),
            assign_to? (optional object name to assign the material to).
    """
    mat_name = params.get("material", "NodeMaterial")
    mat, nt = _get_or_create_material(mat_name, params.get("clear", True))

    nodes = list(params.get("nodes", []))
    links = list(params.get("links", []))
    # Guarantee an output node so the material renders.
    if not any(n.get("type") == "ShaderNodeOutputMaterial" for n in nodes):
        nodes.append({"id": "mat_output", "type": "ShaderNodeOutputMaterial",
                      "location": [600, 0]})

    report = _build_graph(nt, nodes, links)
    _auto_layout(nt)

    assigned = None
    target = params.get("assign_to")
    if target:
        obj = bpy.data.objects.get(target)
        if obj is not None and hasattr(obj.data, "materials"):
            H.assign_material(obj, mat)
            assigned = obj.name

    return {"ok": True, "material": mat.name, "assigned_to": assigned, **report}


def op_apply_shader_node_preset(params: dict) -> dict:
    """Apply a curated procedural shader preset.

    presets: procedural_wood | procedural_marble | procedural_bricks |
             gradient_emission | fresnel_rim | wave_stripes
    """
    preset = params.get("preset", "procedural_marble")
    spec = _SHADER_PRESETS.get(preset)
    if spec is None:
        return {"ok": False, "error": f"unknown shader preset '{preset}'",
                "available": sorted(_SHADER_PRESETS.keys())}
    p = dict(params)
    built = spec(params)
    p["nodes"] = built["nodes"]
    p["links"] = built["links"]
    p["material"] = params.get("material", f"Proc_{preset}")
    result = op_build_shader_node_graph(p)
    result["preset"] = preset
    return result


# ---- Shader preset graph factories ---------------------------------------- #
def _sh_procedural_marble(params):
    return {
        "nodes": [
            {"id": "coord", "type": "ShaderNodeTexCoord", "location": [-800, 0]},
            {"id": "noise", "type": "ShaderNodeTexNoise", "location": [-600, 0],
             "inputs": {"Scale": float(params.get("scale", 3.0)), "Detail": 8.0}},
            {"id": "wave", "type": "ShaderNodeTexWave", "location": [-600, -240],
             "inputs": {"Scale": float(params.get("scale", 3.0)), "Distortion": 12.0}},
            {"id": "ramp", "type": "ShaderNodeValToRGB", "location": [-360, 0]},
            {"id": "bsdf", "type": "ShaderNodeBsdfPrincipled", "location": [0, 0],
             "inputs": {"Roughness": 0.25}},
        ],
        "links": [
            {"from": "coord", "from_socket": "Object", "to": "noise", "to_socket": "Vector"},
            {"from": "noise", "from_socket": "Fac", "to": "wave", "to_socket": "Distortion"},
            {"from": "wave", "from_socket": "Color", "to": "ramp", "to_socket": "Fac"},
            {"from": "ramp", "from_socket": "Color", "to": "bsdf", "to_socket": "Base Color"},
            {"from": "bsdf", "from_socket": "BSDF", "to": "mat_output", "to_socket": "Surface"},
        ],
    }


def _sh_procedural_wood(params):
    return {
        "nodes": [
            {"id": "coord", "type": "ShaderNodeTexCoord", "location": [-800, 0]},
            {"id": "wave", "type": "ShaderNodeTexWave", "location": [-560, 0],
             "props": {"wave_type": "RINGS"},
             "inputs": {"Scale": float(params.get("scale", 2.0)), "Distortion": 3.0,
                        "Detail": 6.0}},
            {"id": "ramp", "type": "ShaderNodeValToRGB", "location": [-320, 0]},
            {"id": "bsdf", "type": "ShaderNodeBsdfPrincipled", "location": [0, 0],
             "inputs": {"Roughness": 0.45}},
        ],
        "links": [
            {"from": "coord", "from_socket": "Object", "to": "wave", "to_socket": "Vector"},
            {"from": "wave", "from_socket": "Color", "to": "ramp", "to_socket": "Fac"},
            {"from": "ramp", "from_socket": "Color", "to": "bsdf", "to_socket": "Base Color"},
            {"from": "bsdf", "from_socket": "BSDF", "to": "mat_output", "to_socket": "Surface"},
        ],
    }


def _sh_procedural_bricks(params):
    return {
        "nodes": [
            {"id": "brick", "type": "ShaderNodeTexBrick", "location": [-500, 0],
             "inputs": {"Scale": float(params.get("scale", 6.0))}},
            {"id": "bsdf", "type": "ShaderNodeBsdfPrincipled", "location": [0, 0],
             "inputs": {"Roughness": 0.7}},
        ],
        "links": [
            {"from": "brick", "from_socket": "Color", "to": "bsdf", "to_socket": "Base Color"},
            {"from": "bsdf", "from_socket": "BSDF", "to": "mat_output", "to_socket": "Surface"},
        ],
    }


def _sh_gradient_emission(params):
    strength = float(params.get("strength", 3.0))
    return {
        "nodes": [
            {"id": "coord", "type": "ShaderNodeTexCoord", "location": [-700, 0]},
            {"id": "grad", "type": "ShaderNodeTexGradient", "location": [-500, 0]},
            {"id": "ramp", "type": "ShaderNodeValToRGB", "location": [-300, 0]},
            {"id": "emit", "type": "ShaderNodeEmission", "location": [0, 0],
             "inputs": {"Strength": strength}},
        ],
        "links": [
            {"from": "coord", "from_socket": "Generated", "to": "grad", "to_socket": "Vector"},
            {"from": "grad", "from_socket": "Color", "to": "ramp", "to_socket": "Fac"},
            {"from": "ramp", "from_socket": "Color", "to": "emit", "to_socket": "Color"},
            {"from": "emit", "from_socket": "Emission", "to": "mat_output", "to_socket": "Surface"},
        ],
    }


def _sh_fresnel_rim(params):
    return {
        "nodes": [
            {"id": "fresnel", "type": "ShaderNodeFresnel", "location": [-600, 100],
             "inputs": {"IOR": 1.45}},
            {"id": "emit", "type": "ShaderNodeEmission", "location": [-340, 200],
             "inputs": {"Strength": float(params.get("strength", 2.0))}},
            {"id": "diffuse", "type": "ShaderNodeBsdfPrincipled", "location": [-340, -120]},
            {"id": "mix", "type": "ShaderNodeMixShader", "location": [0, 0]},
        ],
        "links": [
            {"from": "fresnel", "from_socket": "Fac", "to": "mix", "to_socket": "Fac"},
            {"from": "diffuse", "from_socket": "BSDF", "to": "mix", "to_socket": 1},
            {"from": "emit", "from_socket": "Emission", "to": "mix", "to_socket": 2},
            {"from": "mix", "from_socket": "Shader", "to": "mat_output", "to_socket": "Surface"},
        ],
    }


def _sh_wave_stripes(params):
    return {
        "nodes": [
            {"id": "wave", "type": "ShaderNodeTexWave", "location": [-500, 0],
             "inputs": {"Scale": float(params.get("scale", 8.0))}},
            {"id": "ramp", "type": "ShaderNodeValToRGB", "location": [-280, 0]},
            {"id": "bsdf", "type": "ShaderNodeBsdfPrincipled", "location": [0, 0]},
        ],
        "links": [
            {"from": "wave", "from_socket": "Fac", "to": "ramp", "to_socket": "Fac"},
            {"from": "ramp", "from_socket": "Color", "to": "bsdf", "to_socket": "Base Color"},
            {"from": "bsdf", "from_socket": "BSDF", "to": "mat_output", "to_socket": "Surface"},
        ],
    }


_SHADER_PRESETS = {
    "procedural_marble": _sh_procedural_marble,
    "procedural_wood": _sh_procedural_wood,
    "procedural_bricks": _sh_procedural_bricks,
    "gradient_emission": _sh_gradient_emission,
    "fresnel_rim": _sh_fresnel_rim,
    "wave_stripes": _sh_wave_stripes,
}


# --------------------------------------------------------------------------- #
# Inspect / discover (read-back so the AI can iterate on a design)
# --------------------------------------------------------------------------- #
def _serialize_tree(nt) -> dict:
    nodes = []
    for n in nt.nodes:
        nodes.append({
            "name": n.name,
            "label": n.label,
            "type": n.bl_idname,
            "location": [round(n.location.x, 1), round(n.location.y, 1)],
            "inputs": [s.name for s in n.inputs],
            "outputs": [s.name for s in n.outputs],
        })
    links = [
        {"from": l.from_node.name, "from_socket": l.from_socket.name,
         "to": l.to_node.name, "to_socket": l.to_socket.name}
        for l in nt.links
    ]
    return {"nodes": nodes, "links": links, "node_count": len(nodes)}


def op_inspect_node_graph(params: dict) -> dict:
    """Read back an existing node tree (geometry-nodes object OR material).

    params: object (reads its first GN modifier) OR material (reads its shader tree).
    """
    mat_name = params.get("material")
    if mat_name:
        mat = bpy.data.materials.get(mat_name)
        if mat is None or not mat.use_nodes:
            return {"ok": False, "error": f"material '{mat_name}' has no node tree"}
        return {"ok": True, "kind": "shader", "material": mat.name,
                **_serialize_tree(mat.node_tree)}

    obj_name = params.get("object")
    obj = bpy.data.objects.get(obj_name) if obj_name else None
    if obj is None:
        return {"ok": False, "error": "provide a valid 'object' or 'material'"}
    mod = next((m for m in obj.modifiers if m.type == "NODES" and m.node_group), None)
    if mod is None:
        return {"ok": False, "error": f"'{obj_name}' has no Geometry Nodes modifier"}
    return {"ok": True, "kind": "geometry", "object": obj.name,
            "modifier": mod.name, "tree": mod.node_group.name,
            **_serialize_tree(mod.node_group)}


def op_list_node_presets(params: dict) -> dict:
    """List available curated node presets (geometry + shader + compositor)."""
    return {
        "ok": True,
        "geometry_presets": sorted(_GEO_PRESETS.keys()),
        "shader_presets": sorted(_SHADER_PRESETS.keys()),
        "compositor_presets": sorted(_COMP_PRESETS.keys()),
        "allowed_node_prefixes": list(_ALLOWED_NODE_PREFIXES),
    }


# --------------------------------------------------------------------------- #
# Reusable node groups (create once, instance everywhere)
# --------------------------------------------------------------------------- #
_TREE_KINDS = {
    "geometry": "GeometryNodeTree",
    "shader": "ShaderNodeTree",
    "compositor": "CompositorNodeTree",
}

# bl_idname of the "group" wrapper node, per tree kind.
_GROUP_NODE_IDNAME = {
    "geometry": "GeometryNodeGroup",
    "shader": "ShaderNodeGroup",
    "compositor": "CompositorNodeGroup",
}


def _add_interface_sockets(ng, sockets: list[dict]) -> list[str]:
    """Create named, typed interface sockets on a node group.

    sockets: [{name, type?(FLOAT/GEOMETRY/...), in_out?(INPUT/OUTPUT), default?}]
    """
    made = []
    for s in sockets or []:
        in_out = (s.get("in_out") or "INPUT").upper()
        sock = _new_interface_socket(ng, s.get("name", "Value"), in_out,
                                     _socket_bl_idname(s.get("type", "FLOAT")))
        if sock is not None and "default" in s and hasattr(sock, "default_value"):
            try:
                sock.default_value = s["default"]
            except (TypeError, ValueError, AttributeError):
                pass
        made.append(s.get("name", "Value"))
    return made


def op_create_node_group(params: dict) -> dict:
    """Create a standalone, reusable node group (not attached to anything).

    params: name, kind (geometry|shader|compositor), interface[] (named typed
            sockets), nodes[], links[]. Returns the group name for instancing.
    """
    kind = (params.get("kind") or "geometry").lower()
    tree_kind = _TREE_KINDS.get(kind)
    if tree_kind is None:
        return {"ok": False, "error": f"unknown kind '{kind}'", "available": list(_TREE_KINDS)}

    name = params.get("name", f"Remirdy_{kind}_group")
    ng = bpy.data.node_groups.new(name, tree_kind)

    interface = params.get("interface")
    if not interface and kind == "geometry":
        # sensible default so a geometry group is usable immediately
        interface = [{"name": "Geometry", "type": "GEOMETRY", "in_out": "INPUT"},
                     {"name": "Geometry", "type": "GEOMETRY", "in_out": "OUTPUT"}]
    sockets_made = _add_interface_sockets(ng, interface or [])

    report = _build_graph(ng, list(params.get("nodes", [])), list(params.get("links", [])))
    _auto_layout(ng)
    return {"ok": True, "group": ng.name, "kind": kind,
            "interface": sockets_made, **report}


def op_instance_node_group(params: dict) -> dict:
    """Re-use an existing node group on a target.

    geometry group -> added as a NODES modifier on `object`.
    shader group   -> wrapped in a group node inside `material` (assigned if asked).
    """
    group_name = params.get("group")
    ng = bpy.data.node_groups.get(group_name) if group_name else None
    if ng is None:
        return {"ok": False, "error": f"node group '{group_name}' not found"}

    kind = {"GeometryNodeTree": "geometry", "ShaderNodeTree": "shader",
            "CompositorNodeTree": "compositor"}.get(ng.bl_idname, "geometry")

    if kind == "geometry":
        obj = bpy.data.objects.get(params.get("object"))
        if obj is None:
            return {"ok": False, "error": "geometry group needs a valid 'object'"}
        mod = obj.modifiers.new(name=params.get("modifier_name", ng.name), type="NODES")
        mod.node_group = ng
        return {"ok": True, "object": obj.name, "modifier": mod.name, "group": ng.name}

    if kind == "shader":
        mat_name = params.get("material", f"{ng.name}_mat")
        mat, nt = _get_or_create_material(mat_name, params.get("clear", True))
        grp = nt.nodes.new(_GROUP_NODE_IDNAME["shader"])
        grp.node_tree = ng
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        out.location = (300, 0)
        # wire first group output to surface if compatible
        if grp.outputs:
            try:
                nt.links.new(grp.outputs[0], out.inputs["Surface"])
            except (RuntimeError, TypeError):
                pass
        assigned = None
        target = params.get("assign_to")
        if target and (obj := bpy.data.objects.get(target)) is not None:
            H.assign_material(obj, mat)
            assigned = obj.name
        return {"ok": True, "material": mat.name, "group": ng.name, "assigned_to": assigned}

    return {"ok": False, "error": f"instancing not supported for '{kind}' groups yet"}


def op_list_node_groups(params: dict) -> dict:
    """List every reusable node group in the file, with kind and socket counts."""
    groups = []
    for ng in bpy.data.node_groups:
        groups.append({
            "name": ng.name,
            "kind": {"GeometryNodeTree": "geometry", "ShaderNodeTree": "shader",
                     "CompositorNodeTree": "compositor"}.get(ng.bl_idname, ng.bl_idname),
            "users": getattr(ng, "users", 0),
        })
    return {"ok": True, "groups": groups, "count": len(groups)}


# --------------------------------------------------------------------------- #
# Expose Geometry-Node inputs as adjustable modifier values (sliders)
# --------------------------------------------------------------------------- #
def _iter_interface_inputs(ng):
    iface = getattr(ng, "interface", None)
    if iface is not None and hasattr(iface, "items_tree"):
        return [it for it in iface.items_tree if getattr(it, "in_out", None) == "INPUT"]
    return list(getattr(ng, "inputs", []))


def _gn_modifier(obj):
    return next((m for m in obj.modifiers if m.type == "NODES" and m.node_group), None)


def op_expose_geometry_input(params: dict) -> dict:
    """Add a named, typed, adjustable input to an object's Geometry Nodes group.

    The new socket appears in the modifier panel as a slider/field the user (or
    a later call) can change. params: object, name, type?(FLOAT/INT/...),
    default?, connect_to?{node_label, socket} to wire it into the graph.
    """
    obj = bpy.data.objects.get(params.get("object"))
    if obj is None:
        return {"ok": False, "error": "valid 'object' required"}
    mod = _gn_modifier(obj)
    if mod is None:
        return {"ok": False, "error": f"'{obj.name}' has no Geometry Nodes modifier"}
    ng = mod.node_group
    sock = _new_interface_socket(ng, params.get("name", "Value"), "INPUT",
                                 _socket_bl_idname(params.get("type", "FLOAT")))
    if sock is not None and "default" in params and hasattr(sock, "default_value"):
        try:
            sock.default_value = params["default"]
        except (TypeError, ValueError, AttributeError):
            pass
    # optionally wire the matching Group Input output socket into a graph node
    wired = False
    conn = params.get("connect_to")
    if conn:
        gin = next((n for n in ng.nodes if n.bl_idname == "NodeGroupInput"), None)
        tgt = next((n for n in ng.nodes if n.label == conn.get("node_label")
                    or n.name == conn.get("node_label")), None)
        if gin and tgt:
            out = _resolve_socket(gin.outputs, params.get("name", "Value"))
            inp = _resolve_socket(tgt.inputs, conn.get("socket", 0))
            if out and inp:
                try:
                    ng.links.new(out, inp)
                    wired = True
                except (RuntimeError, TypeError):
                    pass
    return {"ok": True, "object": obj.name, "input": params.get("name", "Value"),
            "wired": wired}


def _modifier_input_id(mod, name: str):
    """Return the modifier key ('Input_N' / 'Socket_N') for an interface socket name."""
    ng = mod.node_group
    iface = getattr(ng, "interface", None)
    if iface is not None and hasattr(iface, "items_tree"):
        for it in iface.items_tree:
            if getattr(it, "in_out", None) == "INPUT" and it.name == name:
                return getattr(it, "identifier", None)
    else:
        for s in getattr(ng, "inputs", []):
            if s.name == name:
                return s.identifier
    return None


def op_set_geometry_input(params: dict) -> dict:
    """Set the value of an exposed Geometry-Nodes modifier input (the slider).

    params: object, name (socket name), value.
    """
    obj = bpy.data.objects.get(params.get("object"))
    if obj is None:
        return {"ok": False, "error": "valid 'object' required"}
    mod = _gn_modifier(obj)
    if mod is None:
        return {"ok": False, "error": f"'{obj.name}' has no Geometry Nodes modifier"}
    name = params.get("name")
    key = _modifier_input_id(mod, name)
    if key is None:
        return {"ok": False, "error": f"input '{name}' not found on modifier"}
    try:
        mod[key] = params.get("value")
        # nudge a depsgraph update so the change takes effect
        obj.data.update() if hasattr(obj.data, "update") else None
        return {"ok": True, "object": obj.name, "input": name, "value": params.get("value")}
    except (TypeError, ValueError, KeyError) as exc:
        return {"ok": False, "error": str(exc)}


# --------------------------------------------------------------------------- #
# Compositor node graph (post-processing) — reuses the same engine
# --------------------------------------------------------------------------- #
def _ensure_compositor_tree(clear: bool):
    scene = bpy.context.scene
    scene.use_nodes = True
    nt = scene.node_tree
    if clear:
        nt.nodes.clear()
    return nt


def op_build_compositor_graph(params: dict) -> dict:
    """Build the scene compositing (post-process) node graph from a spec.

    Render Layers + Composite output are auto-added if omitted.
    """
    nt = _ensure_compositor_tree(params.get("clear", True))
    nodes = list(params.get("nodes", []))
    links = list(params.get("links", []))
    if not any(n.get("type") == "CompositorNodeRLayers" for n in nodes):
        nodes.insert(0, {"id": "render_layers", "type": "CompositorNodeRLayers",
                         "location": [-600, 0]})
    if not any(n.get("type") == "CompositorNodeComposite" for n in nodes):
        nodes.append({"id": "composite", "type": "CompositorNodeComposite",
                      "location": [600, 0]})
    report = _build_graph(nt, nodes, links)
    _auto_layout(nt)
    return {"ok": True, "tree": "Compositing", **report}


def op_apply_compositor_preset(params: dict) -> dict:
    """Apply a curated compositor preset: glare | color_grade | vignette | sharpen."""
    preset = params.get("preset", "glare")
    spec = _COMP_PRESETS.get(preset)
    if spec is None:
        return {"ok": False, "error": f"unknown compositor preset '{preset}'",
                "available": sorted(_COMP_PRESETS.keys())}
    built = spec(params)
    p = dict(params)
    p["nodes"], p["links"] = built["nodes"], built["links"]
    result = op_build_compositor_graph(p)
    result["preset"] = preset
    return result


def _comp_glare(params):
    return {
        "nodes": [
            {"id": "rl", "type": "CompositorNodeRLayers", "location": [-600, 0]},
            {"id": "glare", "type": "CompositorNodeGlare", "location": [-200, 0],
             "props": {"glare_type": "FOG_GLOW", "quality": "HIGH"}},
            {"id": "comp", "type": "CompositorNodeComposite", "location": [200, 0]},
        ],
        "links": [
            {"from": "rl", "from_socket": "Image", "to": "glare", "to_socket": "Image"},
            {"from": "glare", "from_socket": "Image", "to": "comp", "to_socket": "Image"},
        ],
    }


def _comp_color_grade(params):
    return {
        "nodes": [
            {"id": "rl", "type": "CompositorNodeRLayers", "location": [-600, 0]},
            {"id": "cb", "type": "CompositorNodeColorBalance", "location": [-300, 0]},
            {"id": "cc", "type": "CompositorNodeColorCorrection", "location": [0, 0]},
            {"id": "comp", "type": "CompositorNodeComposite", "location": [320, 0]},
        ],
        "links": [
            {"from": "rl", "from_socket": "Image", "to": "cb", "to_socket": "Image"},
            {"from": "cb", "from_socket": "Image", "to": "cc", "to_socket": "Image"},
            {"from": "cc", "from_socket": "Image", "to": "comp", "to_socket": "Image"},
        ],
    }


def _comp_vignette(params):
    return {
        "nodes": [
            {"id": "rl", "type": "CompositorNodeRLayers", "location": [-700, 0]},
            {"id": "ellipse", "type": "CompositorNodeEllipseMask", "location": [-700, -250],
             "inputs": {"Width": 0.6, "Height": 0.6}},
            {"id": "blur", "type": "CompositorNodeBlur", "location": [-450, -250],
             "inputs": {"Size": 0.5}},
            {"id": "mul", "type": "CompositorNodeMixRGB", "location": [-150, 0],
             "props": {"blend_type": "MULTIPLY"}},
            {"id": "comp", "type": "CompositorNodeComposite", "location": [200, 0]},
        ],
        "links": [
            {"from": "rl", "from_socket": "Image", "to": "mul", "to_socket": 1},
            {"from": "ellipse", "from_socket": "Mask", "to": "blur", "to_socket": "Image"},
            {"from": "blur", "from_socket": "Image", "to": "mul", "to_socket": 2},
            {"from": "mul", "from_socket": "Image", "to": "comp", "to_socket": "Image"},
        ],
    }


def _comp_sharpen(params):
    return {
        "nodes": [
            {"id": "rl", "type": "CompositorNodeRLayers", "location": [-500, 0]},
            {"id": "filt", "type": "CompositorNodeFilter", "location": [-150, 0],
             "props": {"filter_type": "SHARPEN"}},
            {"id": "comp", "type": "CompositorNodeComposite", "location": [200, 0]},
        ],
        "links": [
            {"from": "rl", "from_socket": "Image", "to": "filt", "to_socket": "Image"},
            {"from": "filt", "from_socket": "Image", "to": "comp", "to_socket": "Image"},
        ],
    }


_COMP_PRESETS = {
    "glare": _comp_glare,
    "color_grade": _comp_color_grade,
    "vignette": _comp_vignette,
    "sharpen": _comp_sharpen,
}
