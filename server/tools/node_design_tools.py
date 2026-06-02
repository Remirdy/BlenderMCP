"""Node-based design tools — Geometry Nodes & Shader Nodes.

Lets the AI *design procedurally* by declaring node graphs, instead of only
gluing primitives together. Two paths: curated presets for one-call results,
and a generic graph builder for designing anything node-by-node.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ._common import call


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_node_presets() -> dict:
        """List the curated Geometry-Node and Shader-Node presets available, plus
        the allow-listed node families the generic graph builders accept.
        Call this first to discover what's buildable."""
        return call("list_node_presets")

    @mcp.tool()
    def apply_geometry_node_preset(
        object: str,
        preset: str = "displace_noise",
        scale: float | None = None,
        strength: float | None = None,
        density: float | None = None,
        count: int | None = None,
        radius: float | None = None,
        level: int | None = None,
    ) -> dict:
        """Attach a curated Geometry Nodes graph to an object (procedural design).

        preset: displace_noise | scatter_on_surface | procedural_array |
                point_instances | wireframe_tubes | smooth_subdivide
        Extra params tune the preset (scale/strength for noise, density for
        scatter, count for array, radius for tubes, level for subdivision).
        """
        params: dict = {"object": object, "preset": preset}
        for k, v in (("scale", scale), ("strength", strength), ("density", density),
                     ("count", count), ("radius", radius), ("level", level)):
            if v is not None:
                params[k] = v
        return call("apply_geometry_node_preset", params)

    @mcp.tool()
    def apply_shader_node_preset(
        preset: str = "procedural_marble",
        material: str | None = None,
        assign_to: str | None = None,
        scale: float | None = None,
        strength: float | None = None,
    ) -> dict:
        """Build a curated procedural shader graph on a material.

        preset: procedural_marble | procedural_wood | procedural_bricks |
                gradient_emission | fresnel_rim | wave_stripes
        assign_to: optional object name to also assign the material to.
        """
        params: dict = {"preset": preset}
        for k, v in (("material", material), ("assign_to", assign_to),
                     ("scale", scale), ("strength", strength)):
            if v is not None:
                params[k] = v
        return call("apply_shader_node_preset", params)

    @mcp.tool()
    def build_geometry_node_graph(
        object: str,
        nodes: list[dict],
        links: list[dict],
        tree_name: str | None = None,
        clear: bool = True,
    ) -> dict:
        """Design an arbitrary Geometry Nodes graph on an object from a spec.

        nodes: list of {id, type, location?[x,y], inputs?{socket: value},
               props?{attr: value}}. `type` is a Blender node bl_idname
               (e.g. "GeometryNodeSetPosition", "ShaderNodeTexNoise").
               Sockets may be addressed by name ("Geometry") or index (0).
        links: list of {from, from_socket, to, to_socket} referencing node ids.

        Group Input/Output nodes are auto-added if omitted. Only built-in
        GeometryNode/ShaderNode/FunctionNode families are allowed (no code exec).
        Use inspect_node_graph afterward to read the result and iterate.
        """
        params: dict = {"object": object, "nodes": nodes, "links": links, "clear": clear}
        if tree_name is not None:
            params["tree_name"] = tree_name
        return call("build_geometry_node_graph", params)

    @mcp.tool()
    def build_shader_node_graph(
        material: str,
        nodes: list[dict],
        links: list[dict],
        assign_to: str | None = None,
        clear: bool = True,
    ) -> dict:
        """Design an arbitrary shader node graph on a material from a spec.

        Same spec format as build_geometry_node_graph. A Material Output node is
        auto-added if omitted. assign_to optionally assigns the material to an object.
        """
        params: dict = {"material": material, "nodes": nodes, "links": links, "clear": clear}
        if assign_to is not None:
            params["assign_to"] = assign_to
        return call("build_shader_node_graph", params)

    @mcp.tool()
    def create_node_group(
        name: str,
        kind: str = "geometry",
        interface: list[dict] | None = None,
        nodes: list[dict] | None = None,
        links: list[dict] | None = None,
    ) -> dict:
        """Create a standalone, reusable node group (not attached to anything).

        kind: geometry | shader | compositor.
        interface: named typed sockets [{name, type(FLOAT/GEOMETRY/COLOR/...),
                   in_out(INPUT/OUTPUT), default?}]. For geometry groups a
                   Geometry in+out pair is added automatically if omitted.
        Returns the group name; instance it on many objects with instance_node_group.
        """
        return call("create_node_group", {
            "name": name, "kind": kind, "interface": interface or [],
            "nodes": nodes or [], "links": links or [],
        })

    @mcp.tool()
    def instance_node_group(
        group: str,
        object: str | None = None,
        material: str | None = None,
        assign_to: str | None = None,
        modifier_name: str | None = None,
    ) -> dict:
        """Re-use an existing node group. A geometry group attaches as a modifier
        on `object`; a shader group is wrapped in a material (optionally assigned
        to `assign_to`). This is how one design is reused across many assets."""
        params: dict = {"group": group}
        for k, v in (("object", object), ("material", material),
                     ("assign_to", assign_to), ("modifier_name", modifier_name)):
            if v is not None:
                params[k] = v
        return call("instance_node_group", params)

    @mcp.tool()
    def list_node_groups() -> dict:
        """List every reusable node group in the file (name, kind, user count)."""
        return call("list_node_groups")

    @mcp.tool()
    def expose_geometry_input(
        object: str,
        name: str,
        type: str = "FLOAT",
        default: float | int | bool | list | None = None,
        connect_to: dict | None = None,
    ) -> dict:
        """Add an adjustable input to an object's Geometry Nodes group — it shows
        up as a slider/field in the modifier panel.

        type: FLOAT|INT|BOOL|VECTOR|COLOR. connect_to {node_label, socket} wires
        the new Group Input socket into a node in the graph. Tune it later with
        set_geometry_input or animate it with animate_property.
        """
        params: dict = {"object": object, "name": name, "type": type}
        if default is not None:
            params["default"] = default
        if connect_to is not None:
            params["connect_to"] = connect_to
        return call("expose_geometry_input", params)

    @mcp.tool()
    def set_geometry_input(object: str, name: str, value) -> dict:
        """Set the value of an exposed Geometry-Nodes modifier input (the slider)."""
        return call("set_geometry_input", {"object": object, "name": name, "value": value})

    @mcp.tool()
    def build_compositor_graph(
        nodes: list[dict],
        links: list[dict],
        clear: bool = True,
    ) -> dict:
        """Design the scene's post-processing (compositor) node graph from a spec.

        Same node/link spec as the other builders; Render Layers + Composite
        output are auto-added. Use CompositorNode* node types.
        """
        return call("build_compositor_graph", {"nodes": nodes, "links": links, "clear": clear})

    @mcp.tool()
    def apply_compositor_preset(preset: str = "glare") -> dict:
        """Apply a curated post-process compositor preset.

        preset: glare | color_grade | vignette | sharpen.
        """
        return call("apply_compositor_preset", {"preset": preset})

    @mcp.tool()
    def inspect_node_graph(object: str | None = None, material: str | None = None) -> dict:
        """Read back an existing node tree so you can iterate on a design.

        Pass `material` to read a shader tree, or `object` to read its first
        Geometry Nodes modifier. Returns every node (name, type, sockets) and
        all links — the feedback half of the build → inspect → tweak loop.
        """
        params: dict = {}
        if object is not None:
            params["object"] = object
        if material is not None:
            params["material"] = material
        return call("inspect_node_graph", params)
