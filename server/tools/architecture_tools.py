"""Architecture exterior tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ._common import call


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def create_floor_plan_blockout(width: float = 12.0, depth: float = 9.0, rooms: int = 4) -> dict:
        """Block out a floor plan with exterior walls and interior partitions for a given room count."""
        return call("create_floor_plan_blockout", {"width": width, "depth": depth, "rooms": rooms})

    @mcp.tool()
    def create_modern_house_exterior(floors: int = 2, pool: bool = False, garden: bool = True) -> dict:
        """Create a modern house exterior with glass facade, concrete/wood materials and optional pool/garden."""
        return call("create_modern_house_exterior", {"floors": floors, "pool": pool, "garden": garden})

    @mcp.tool()
    def add_architectural_details(level: str = "medium") -> dict:
        """Add trims, sills, fascia and facade detailing to existing architecture (low | medium | high)."""
        return call("add_architectural_details", {"level": level})

    @mcp.tool()
    def add_windows_doors_stairs(
        windows: int = 6, doors: int = 2, stairs: bool = True
    ) -> dict:
        """Add windows, doors and stairs with believable proportions to the current building."""
        return call("add_windows_doors_stairs", {"windows": windows, "doors": doors, "stairs": stairs})
