"""Character creation, rigging and animation tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ._common import call


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def create_rigged_character(
        name: str = "Cyber Adventurer",
        style: str = "stylized_hero",
        animation: str = "idle_wave",
        clear_scene: bool = True,
    ) -> dict:
        """Create an original humanoid character with an armature and starter animation.

        style: stylized_hero | cyber_adventurer | fantasy_knight | sci_fi_scout
        animation: idle | wave | walk_preview | idle_wave
        """
        return call(
            "create_rigged_character",
            {
                "name": name,
                "style": style,
                "animation": animation,
                "clear_scene": clear_scene,
            },
        )

    @mcp.tool()
    def add_character_animation(animation: str = "idle_wave", frames: int = 120) -> dict:
        """Add or replace keyframed animation on the active Remirdy character rig.

        animation: idle | wave | walk_preview | idle_wave
        """
        return call("add_character_animation", {"animation": animation, "frames": frames})

    @mcp.tool()
    def validate_character_rig() -> dict:
        """Inspect the current scene for an animation-ready character armature."""
        return call("validate_character_rig", {})

    @mcp.tool()
    def export_character_glb(filename: str = "rigged_character.glb", target: str = "unity") -> dict:
        """Export the rigged character as GLB with armature and animations."""
        return call("export_character_glb", {"filename": filename, "target": target})
