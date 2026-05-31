"""Interior design tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ._common import call


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def create_apartment_interior(rooms: int = 3, style: str = "luxury_apartment") -> dict:
        """Create a multi-room apartment interior shell with furnished, laid-out rooms."""
        return call("create_apartment_interior", {"rooms": rooms, "style": style})

    @mcp.tool()
    def create_living_room_scene(style: str = "luxury_apartment", warm_lighting: bool = True) -> dict:
        """Create a living room: sofa, coffee table, TV wall, windows, rug, plants, warm lighting."""
        return call("create_living_room_scene", {"style": style, "warm_lighting": warm_lighting})

    @mcp.tool()
    def create_bedroom_scene(style: str = "minimalist_interior") -> dict:
        """Create a bedroom: bed, nightstands, wardrobe, window, soft lighting."""
        return call("create_bedroom_scene", {"style": style})

    @mcp.tool()
    def create_kitchen_scene(style: str = "minimalist_interior", island: bool = True) -> dict:
        """Create a kitchen: cabinets, counters, optional island, appliances and lighting."""
        return call("create_kitchen_scene", {"style": style, "island": island})

    @mcp.tool()
    def create_office_interior(desks: int = 6, glass_partitions: bool = True) -> dict:
        """Create an office interior: desks, chairs, meeting area, panels and glass partitions."""
        return call("create_office_interior", {"desks": desks, "glass_partitions": glass_partitions})

    @mcp.tool()
    def add_furniture_set(set_name: str = "living_room") -> dict:
        """Add a coherent furniture set (living_room | bedroom | kitchen | office | cafe) with sensible layout."""
        return call("add_furniture_set", {"set_name": set_name})

    @mcp.tool()
    def apply_interior_material_palette(palette: str = "warm_modern") -> dict:
        """Apply a coordinated interior material palette (warm_modern | minimalist_neutral | luxury_dark)."""
        return call("apply_interior_material_palette", {"palette": palette})
