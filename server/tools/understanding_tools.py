"""Scene understanding tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ._common import call


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def capture_viewport_screenshot(
        view: str = "camera",
        width: int = 1280,
        height: int = 720,
        filename: str = "viewport_screenshot.png",
    ) -> dict:
        """Capture a Blender camera/front/side/top/perspective screenshot to the workspace."""
        return call("capture_viewport_screenshot", {
            "view": view,
            "width": width,
            "height": height,
            "filename": filename,
        })

    @mcp.tool()
    def capture_scene_contact_sheet(width: int = 960, height: int = 540) -> dict:
        """Capture camera, front, side and top screenshots for scene review."""
        return call("capture_scene_contact_sheet", {"width": width, "height": height})

    @mcp.tool()
    def analyze_scene_visuals(view: str = "camera") -> dict:
        """Capture a screenshot and return high-level visual/structural scene facts."""
        return call("analyze_scene_visuals", {"view": view})

    @mcp.tool()
    def get_scene_graph() -> dict:
        """Return collections, objects, transforms, bounds, materials and armature bones."""
        return call("get_scene_graph", {})
