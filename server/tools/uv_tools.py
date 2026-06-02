"""UV unwrapping tools — so procedural and image textures sit correctly."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ._common import call


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def smart_uv_project(object: str, angle_limit: float = 66.0, island_margin: float = 0.02) -> dict:
        """Angle-based automatic unwrap — the best one-call default for props."""
        return call("smart_uv_project", {
            "object": object, "angle_limit": angle_limit, "island_margin": island_margin,
        })

    @mcp.tool()
    def unwrap(object: str, method: str = "ANGLE_BASED", margin: float = 0.02) -> dict:
        """Unwrap using existing seams. method: ANGLE_BASED | CONFORMAL."""
        return call("unwrap", {"object": object, "method": method, "margin": margin})

    @mcp.tool()
    def mark_seams_by_angle(object: str, angle: float = 40.0) -> dict:
        """Auto-mark sharp edges as UV seams, then unwrap."""
        return call("mark_seams_by_angle", {"object": object, "angle": angle})

    @mcp.tool()
    def pack_uv_islands(object: str, margin: float = 0.02) -> dict:
        """Repack UV islands to use the 0–1 space efficiently (unwrap first)."""
        return call("pack_uv_islands", {"object": object, "margin": margin})
