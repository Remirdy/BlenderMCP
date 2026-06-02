"""Animation, drivers, timeline and edit-history tools.

Keyframe objects and node sockets, add drivers, control the timeline, and
undo/redo edits — the design loop's "move it, time it, take it back" layer.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ._common import call


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def keyframe_object(
        object: str,
        keyframes: list[dict],
        interpolation: str = "BEZIER",
    ) -> dict:
        """Keyframe an object's transform.

        keyframes: [{frame, location?[x,y,z], rotation_euler?[x,y,z], scale?[x,y,z]}].
        interpolation: CONSTANT | LINEAR | BEZIER.
        """
        return call("keyframe_object", {
            "object": object, "keyframes": keyframes, "interpolation": interpolation,
        })

    @mcp.tool()
    def animate_property(
        object: str,
        data_path: str,
        keys: list[dict],
        index: int | None = None,
        interpolation: str = "BEZIER",
    ) -> dict:
        """Keyframe one allow-listed property over frame:value pairs.

        data_path: location | rotation_euler | scale | hide_viewport |
                   hide_render | color. keys: [{frame, value}]. index selects a
                   single vector component (0/1/2).
        """
        params: dict = {"object": object, "data_path": data_path, "keys": keys,
                        "interpolation": interpolation}
        if index is not None:
            params["index"] = index
        return call("animate_property", params)

    @mcp.tool()
    def animate_node_input(
        node: str,
        socket,
        keys: list[dict],
        material: str | None = None,
        object: str | None = None,
    ) -> dict:
        """Keyframe a node socket's value over time — procedural motion graphics.

        Animate e.g. a noise Scale, displace Strength, or emission Color. Target
        a shader node via `material`, or a geometry-node modifier via `object`.
        socket: name or index. keys: [{frame, value}].
        """
        params: dict = {"node": node, "socket": socket, "keys": keys}
        if material is not None:
            params["material"] = material
        if object is not None:
            params["object"] = object
        return call("animate_node_input", params)

    @mcp.tool()
    def add_driver(
        object: str,
        data_path: str,
        target_object: str,
        target_data_path: str,
        index: int = -1,
        expression: str = "var",
    ) -> dict:
        """Drive one property from another (single-variable scripted driver).

        The driven property follows `expression` (default "var"), where `var`
        reads target_object.target_data_path.
        """
        return call("add_driver", {
            "object": object, "data_path": data_path, "index": index,
            "target_object": target_object, "target_data_path": target_data_path,
            "expression": expression,
        })

    @mcp.tool()
    def set_frame_range(start: int, end: int, fps: int | None = None) -> dict:
        """Set the scene playback range (and optional fps)."""
        params: dict = {"start": start, "end": end}
        if fps is not None:
            params["fps"] = fps
        return call("set_frame_range", params)

    @mcp.tool()
    def create_turntable(object: str, frames: int = 120, revolutions: float = 1.0) -> dict:
        """Keyframe a constant-speed Z spin on an object (classic turntable)."""
        return call("create_turntable", {
            "object": object, "frames": frames, "revolutions": revolutions,
        })

    @mcp.tool()
    def clear_animation(object: str) -> dict:
        """Remove all animation data from an object."""
        return call("clear_animation", {"object": object})

    @mcp.tool()
    def checkpoint(message: str = "Remirdy checkpoint") -> dict:
        """Push a named undo checkpoint before a risky change so you can roll back."""
        return call("checkpoint", {"message": message})

    @mcp.tool()
    def undo(steps: int = 1) -> dict:
        """Undo the last N edits."""
        return call("undo", {"steps": steps})

    @mcp.tool()
    def redo(steps: int = 1) -> dict:
        """Redo the last N undone edits."""
        return call("redo", {"steps": steps})
