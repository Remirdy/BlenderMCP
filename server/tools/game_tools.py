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

    @mcp.tool()
    def apply_biome_painter(density: int = 25, seed: int = 42) -> dict:
        """Procedurally scatter stylized foliage, flowers and rocks across the terrain hills surface."""
        return call("apply_biome_painter", {"density": density, "seed": seed})

    @mcp.tool()
    def create_bezier_path(width: float = 1.2, name: str = "Stylized_Curve_Path") -> dict:
        """Procedurally sweeps a stylized curved path (cobblestone or water) using Bezier curves."""
        return call("create_bezier_path", {"width": width, "name": name})

    @mcp.tool()
    def spawn_weather_particles(type: str = "snow", density: int = 120) -> dict:
        """Spawns animatable particle weather layers representing stylized falling rain or snow cards.

        type: snow | rain
        """
        return call("spawn_weather_particles", {"type": type, "density": density})

    @mcp.tool()
    def create_building_facade(stories: int = 2, width: float = 6.0, height_per_story: float = 3.2) -> dict:
        """Procedurally construct multi-tier architectural facades featuring columns, arches and window frames."""
        return call("create_building_facade", {"stories": stories, "width": width, "height_per_story": height_per_story})

    @mcp.tool()
    def create_procedural_foliage(iterations: int = 3, height: float = 4.5) -> dict:
        """Generate high-fidelity stylized branching trees utilizing L-system expansion and custom leaves."""
        return call("create_procedural_foliage", {"iterations": iterations, "height": height})

    @mcp.tool()
    def create_istanbul_bosphorus(clear_scene: bool = True) -> dict:
        """Procedurally build a beautiful, professional 3D game scene of the Istanbul Bosphorus Strait.
        Includes Bosphorus water, Maiden's Tower, Suspension Bosphorus Bridge, European/Asian hills, yalı mansions, Ortaköy mosque, cinematic twilight sunset lighting, and cartoon outlines!
        """
        return call("create_istanbul_bosphorus", {"clear_scene": clear_scene})

    @mcp.tool()
    def create_physics_from_prompt(prompt: str, object_name: str | None = None) -> dict:
        """
        Prompt'tan basit fizik simülasyonu tetikler (cloth, fluid, rigid body).
        Örnek promptlar: "kumaş dalgalanıyor", "su dökülüyor", "nesne düşüyor"
        """
        return call("create_physics_from_prompt", {"prompt": prompt, "object_name": object_name})
