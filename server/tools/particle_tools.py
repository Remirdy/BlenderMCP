"""Particle, scatter and vegetation tools — built for game export.

Geometry-Nodes scatter (realized → exportable) is the game-ready path; classic
hair is available for look-dev. Bake anything to mesh with convert_particles_to_mesh.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ._common import call


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def scatter_objects(
        target: str,
        source: str,
        density: float = 10.0,
        seed: int = 0,
        scale_min: float = 0.8,
        scale_max: float = 1.2,
        align_normal: bool = True,
        realize: bool = True,
    ) -> dict:
        """Scatter copies of `source` over `target`'s surface with Geometry Nodes.

        Random scale + surface-aligned rotation. realize=True bakes instances to
        real geometry so the result exports to FBX/glTF (the game-ready default).
        """
        return call("scatter_objects", {
            "target": target, "source": source, "density": density, "seed": seed,
            "scale_min": scale_min, "scale_max": scale_max,
            "align_normal": align_normal, "realize": realize,
        })

    @mcp.tool()
    def scatter_collection(
        target: str,
        collection: str,
        density: float = 5.0,
        seed: int = 0,
        scale_min: float = 0.8,
        scale_max: float = 1.2,
        align_normal: bool = True,
        realize: bool = True,
    ) -> dict:
        """Scatter random picks from a collection (rocks/props/trees) over a surface.
        realize=True for export-ready mesh."""
        return call("scatter_collection", {
            "target": target, "collection": collection, "density": density,
            "seed": seed, "scale_min": scale_min, "scale_max": scale_max,
            "align_normal": align_normal, "realize": realize,
        })

    @mcp.tool()
    def create_grass_field(
        target: str,
        density: float = 50.0,
        height: float = 0.3,
        seed: int = 0,
        align_normal: bool = True,
    ) -> dict:
        """Build a stylized, export-ready game grass field on a surface object."""
        return call("create_grass_field", {
            "target": target, "density": density, "height": height,
            "seed": seed, "align_normal": align_normal,
        })

    @mcp.tool()
    def scatter_debris(
        target: str,
        density: float = 8.0,
        seed: int = 3,
        scale_min: float = 0.5,
        scale_max: float = 1.6,
    ) -> dict:
        """Scatter low-poly rock/debris chunks over a surface for environment art."""
        return call("scatter_debris", {
            "target": target, "density": density, "seed": seed,
            "scale_min": scale_min, "scale_max": scale_max,
        })

    @mcp.tool()
    def add_hair_fur(object: str, count: int = 1000, length: float = 0.1, seed: int = 0) -> dict:
        """Add a classic hair particle system (fur) for look-dev.

        Note: hair particles don't export — use convert_particles_to_mesh, or
        prefer create_grass_field/scatter_objects for game assets.
        """
        return call("add_hair_fur", {
            "object": object, "count": count, "length": length, "seed": seed,
        })

    @mcp.tool()
    def convert_particles_to_mesh(object: str, apply_modifiers: bool = True) -> dict:
        """Bake a scatter into real, exportable mesh: realize particle instances
        and apply Geometry-Nodes modifiers on the object."""
        return call("convert_particles_to_mesh", {
            "object": object, "apply_modifiers": apply_modifiers,
        })
