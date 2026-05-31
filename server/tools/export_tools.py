"""Export pipeline tools. All outputs are written inside the workspace sandbox."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..schemas.tool_schemas import EXPORT_TARGETS
from ..utils.validation import ensure_in
from ._common import call


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def export_blend(filename: str = "scene.blend") -> dict:
        """Save the current scene as a .blend file in outputs/blends."""
        return call("export_blend", {"filename": filename})

    @mcp.tool()
    def export_glb(filename: str = "scene.glb", target: str = "generic", selected_only: bool = False) -> dict:
        """Export to glTF Binary (.glb) in outputs/exports.

        target: generic | unity | unreal  (applies scale/axis presets).
        """
        ensure_in(target, EXPORT_TARGETS, "target")
        return call("export_glb", {"filename": filename, "target": target, "selected_only": selected_only})

    @mcp.tool()
    def export_fbx(filename: str = "scene.fbx", target: str = "generic", selected_only: bool = False) -> dict:
        """Export to FBX (.fbx) in outputs/exports with Unity/Unreal scale presets."""
        ensure_in(target, EXPORT_TARGETS, "target")
        return call("export_fbx", {"filename": filename, "target": target, "selected_only": selected_only})

    @mcp.tool()
    def export_obj(filename: str = "scene.obj") -> dict:
        """Export to Wavefront OBJ (.obj) in outputs/exports."""
        return call("export_obj", {"filename": filename})

    @mcp.tool()
    def export_render_image(filename: str = "render.png", width: int = 1920, height: int = 1080) -> dict:
        """Render and write a still image to outputs/renders."""
        return call("export_render_image", {"filename": filename, "width": width, "height": height})

    @mcp.tool()
    def export_turntable_animation(filename: str = "turntable.mp4", frames: int = 48) -> dict:
        """Render a 360° turntable animation of the scene subject to outputs/renders."""
        return call("export_turntable_animation", {"filename": filename, "frames": frames})
