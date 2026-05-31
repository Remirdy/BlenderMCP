"""Game asset and optimization tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ._common import call


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def create_game_ready_prop(name: str = "Crate", kind: str = "crate", detail: str = "mid") -> dict:
        """Create a single game-ready prop with clean origin, optimized geometry and a game material.

        kind: crate | barrel | rock | lamp | bench | fence | sign
        detail: low | mid
        """
        return call("create_game_ready_prop", {"name": name, "kind": kind, "detail": detail})

    @mcp.tool()
    def create_modular_environment_piece(piece: str = "wall_panel", grid: float = 2.0) -> dict:
        """Create a modular, grid-snapped environment piece (wall_panel, floor_tile, corner, doorway, pillar)."""
        return call("create_modular_environment_piece", {"piece": piece, "grid": grid})

    @mcp.tool()
    def create_low_poly_environment(theme: str = "nature", extent: int = 6) -> dict:
        """Generate a clean low-poly environment (nature, desert, island) for prototypes."""
        return call("create_low_poly_environment", {"theme": theme, "extent": extent})

    @mcp.tool()
    def create_stylized_building(stories: int = 3, footprint: float = 6.0, roof: str = "gable") -> dict:
        """Create a stylized building block with windows, door, trim and a roof."""
        return call("create_stylized_building", {"stories": stories, "footprint": footprint, "roof": roof})

    @mcp.tool()
    def create_mobile_game_scene(theme: str = "campus", isometric_camera: bool = True) -> dict:
        """Create a bright, optimized mobile game scene with an isometric camera option."""
        return call("create_mobile_game_scene", {"theme": theme, "isometric_camera": isometric_camera})

    @mcp.tool()
    def optimize_for_game_engine(target_tris: int = 50000, merge_materials: bool = True) -> dict:
        """Optimize the scene: cap polycount, merge materials, clean transforms for engine import."""
        return call("optimize_for_game_engine", {"target_tris": target_tris, "merge_materials": merge_materials})

    @mcp.tool()
    def prepare_for_unity_export(apply_transforms: bool = True) -> dict:
        """Apply Unity conventions: meters scale, +Y up handling, clean origins, readable names."""
        return call("prepare_for_unity_export", {"apply_transforms": apply_transforms})

    @mcp.tool()
    def prepare_for_unreal_export(apply_transforms: bool = True) -> dict:
        """Apply Unreal conventions: correct scale, clean FBX-ready static-mesh names."""
        return call("prepare_for_unreal_export", {"apply_transforms": apply_transforms})
