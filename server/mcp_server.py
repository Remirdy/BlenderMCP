"""Remirdy Blender Studio MCP server.

Creates the FastMCP instance and registers every tool module. The server is a
thin, validated façade over the in-Blender bridge: it never runs Blender Python
directly. Each tool maps to a structured bridge operation.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .tools import (
    architecture_tools,
    asset_tools,
    asset_source_tools,
    character_tools,
    connection_tools,
    export_tools,
    game_tools,
    import_tools,
    interior_tools,
    marketplace_tools,
    material_tools,
    modular_tools,
    product_tools,
    reference_asset_tools,
    quality_tools,
    render_tools,
    scene_tools,
    telemetry_tools,
    understanding_tools,
)
from .utils.logging_utils import get_logger

log = get_logger("remirdy.server")

INSTRUCTIONS = """
Remirdy Blender Studio MCP — a local MCP bridge for Blender.

Use these tools to build game-ready assets, stylized environments, architectural
exteriors, interiors, product renders and cinematic scenes, then inspect, fix,
render and export them (GLB/FBX/OBJ/blend) with Unity/Unreal presets.

For reference-image work, use create_3d_asset_from_reference_image. If a local
image-to-3D command is configured, the bridge waits for the generated GLB and
imports it into Blender. If it is not configured, the tool reports the reason
and uses the procedural fallback.

Typical flow:
  1. connect_blender
  2. create_scene_from_prompt  (or a specific create_* tool)
  3. scene_quality_check / auto_fix_scene
  4. render_preview
  5. export_glb / prepare_for_unity_export

The server talks to Blender through a local socket bridge (the Remirdy add-on).
Raw Python execution is NOT exposed by default.
""".strip()


def build_server() -> FastMCP:
    mcp = FastMCP("Remirdy Blender Studio", instructions=INSTRUCTIONS)
    for module in (
        connection_tools,
        scene_tools,
        game_tools,
        architecture_tools,
        interior_tools,
        render_tools,
        material_tools,
        quality_tools,
        export_tools,
        asset_tools,
        asset_source_tools,
        character_tools,
        understanding_tools,
        import_tools,
        telemetry_tools,
        modular_tools,
        product_tools,
        reference_asset_tools,
        marketplace_tools,
    ):
        module.register(mcp)
        log.info("Registered tools from %s", module.__name__)
    return mcp


def run() -> None:
    server = build_server()
    log.info("Starting Remirdy Blender Studio MCP over stdio…")
    server.run()
