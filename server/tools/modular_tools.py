"""Modular environment kit builder tools (MVP 2)."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ._common import call

KIT_TYPES = ("sci_fi_corridor", "dungeon_room", "medieval_village", "modern_city_street",
             "stylized_campus", "cyberpunk_alley", "interior_room", "office", "store", "platformer")


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def create_modular_kit(kit_type: str = "sci_fi_corridor", grid: float = 2.0,
                           test_layout: bool = True, render_preview: bool = True, name: str = "") -> dict:
        """Generate a grid-aligned modular kit (walls, floors, corners, doors, windows, roofs, stairs, props),
        assemble a test layout to prove snapping, validate the grid and set up a preview.

        kit_type: sci_fi_corridor | dungeon_room | medieval_village | modern_city_street |
                  stylized_campus | cyberpunk_alley | interior_room | office | store | platformer
        """
        return call("create_modular_kit", {"kit_type": kit_type, "grid": grid,
                                            "test_layout": test_layout, "render_preview": render_preview, "name": name})

    @mcp.tool()
    def create_modular_wall_piece(style: str = "low_poly_city", grid: float = 2.0) -> dict:
        """Create a single grid-sized modular wall piece."""
        return call("create_modular_wall_piece", {"style": style, "grid": grid})

    @mcp.tool()
    def create_modular_floor_piece(style: str = "low_poly_city", grid: float = 2.0) -> dict:
        """Create a single grid-sized modular floor tile."""
        return call("create_modular_floor_piece", {"style": style, "grid": grid})

    @mcp.tool()
    def create_modular_corner_piece(style: str = "low_poly_city", grid: float = 2.0) -> dict:
        """Create a modular L-shaped corner wall piece."""
        return call("create_modular_corner_piece", {"style": style, "grid": grid})

    @mcp.tool()
    def create_modular_door_piece(style: str = "low_poly_city", grid: float = 2.0) -> dict:
        """Create a modular wall-with-doorway piece."""
        return call("create_modular_door_piece", {"style": style, "grid": grid})

    @mcp.tool()
    def create_modular_window_piece(style: str = "low_poly_city", grid: float = 2.0) -> dict:
        """Create a modular wall-with-window piece."""
        return call("create_modular_window_piece", {"style": style, "grid": grid})

    @mcp.tool()
    def create_modular_roof_piece(style: str = "low_poly_city", grid: float = 2.0) -> dict:
        """Create a modular roof/ceiling tile."""
        return call("create_modular_roof_piece", {"style": style, "grid": grid})

    @mcp.tool()
    def create_modular_stair_piece(style: str = "low_poly_city", grid: float = 2.0) -> dict:
        """Create a modular staircase piece."""
        return call("create_modular_stair_piece", {"style": style, "grid": grid})

    @mcp.tool()
    def create_modular_prop_variants(style: str = "low_poly_city", grid: float = 2.0) -> dict:
        """Create modular dressing props (vents, pipes, emissive panels)."""
        return call("create_modular_prop_variants", {"style": style, "grid": grid})

    @mcp.tool()
    def validate_modular_grid(grid: float = 2.0) -> dict:
        """Check that kit pieces align to the grid and have correct floor-level origins for snapping."""
        return call("validate_modular_grid", {"grid": grid})

    @mcp.tool()
    def export_modular_kit(target: str = "unreal", format: str = "fbx") -> dict:
        """Package and export the modular kit (FBX for Unreal / GLB for Unity) with previews + docs."""
        return call("export_modular_kit", {"target": target, "format": format})
