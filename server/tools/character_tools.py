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

    @mcp.tool()
    def bind_auto_weights() -> dict:
        """Automatically bind mesh parts to the character armature utilizing bone heat weighting."""
        return call("bind_auto_weights")

    @mcp.tool()
    def add_text_motion_preset(motion: str = "run", frames: int = 40) -> dict:
        """Bake dynamic keyframed animation presets representing 'run', 'jump', or 'attack' onto rigs."""
        return call("add_text_motion_preset", {"motion": motion, "frames": frames})

    @mcp.tool()
    def create_facial_blendshapes() -> dict:
        """Create facial expression shape keys (smile, blink, mouth open) on character head meshes."""
        return call("create_facial_blendshapes")

    @mcp.tool()
    def fit_clothing_mesh() -> dict:
        """Auto-scale custom clothing meshes to character armature dimensions and attach rig modifiers."""
        return call("fit_clothing_mesh")

    @mcp.tool()
    def convert_hair_to_curves() -> dict:
        """Convert custom hair polygon mesh caps into beautiful stylized curve geometry objects."""
        return call("convert_hair_to_curves")

    @mcp.tool()
    def reduce_armature_bones() -> dict:
        """Simplify rig hierarchies by trimming or merging non-essential skeleton child joints for mobile optimization."""
        return call("reduce_armature_bones")

    @mcp.tool()
    def adapt_fbx_rig(source_rig: str = "") -> dict:
        """Automatically maps bone nomenclature and retargets animation keyframes from imported Mixamo/FBX rigs."""
        return call("adapt_fbx_rig", {"source_rig": source_rig})
