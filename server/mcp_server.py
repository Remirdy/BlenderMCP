"""Remirdy Blender Studio MCP server.

Creates the FastMCP instance and registers every tool module. The server is a
thin, validated façade over the in-Blender bridge: it never runs Blender Python
directly. Each tool maps to a structured bridge operation.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .tools import (
    agent_tools,
    animation_tools,    # Keyframes, drivers, timeline, undo/redo
    architecture_tools,
    asset_tools,
    asset_source_tools,
    browser_tools,       # API-less: Midjourney / ChatGPT / Leonardo / DALL-E / Ideogram
    character_tools,
    comfyui_tools,       # ComfyUI / Stable Diffusion local
    connection_tools,
    export_tools,
    game_tools,
    import_tools,
    interior_tools,
    lipsync_tools,       # Lip sync animation
    marketplace_tools,
    material_tools,
    modular_tools,
    multi_llm_tools,     # Parallel Claude + ChatGPT + Gemini orchestration
    nerf_tools,          # NeRF / Gaussian Splatting → Blender
    node_design_tools,   # Node-based design: Geometry Nodes + Shader Nodes
    particle_tools,      # Game-ready scatter / vegetation / hair
    uv_tools,            # UV unwrapping
    product_tools,
    reference_asset_tools,
    quality_tools,
    render_tools,
    scene_tools,
    sequel_tools,        # .blend DNA + sequel scene generator
    sound_tools,         # Automatic sound design
    telemetry_tools,
    tournament_tools,    # Genetic algorithm scene tournament
    understanding_tools,
    unity_tools,         # Complete Unity project export
    weather_tools,
    world_tools,         # Procedural narrative world — create_world()
)
from .utils.logging_utils import get_logger

log = get_logger("remirdy.server")

INSTRUCTIONS = """
Remirdy Blender Studio MCP — a local MCP bridge for Blender.

Core:   scene/render/export/materials/characters/game/interior/architecture tools.
AI:     Gemini Vision, Multi-Agent orchestration, scene tournament (genetic algorithm).
Media:  ComfyUI/SD textures, NeRF/3DGS photogrammetry, lip sync, sound design.
World:  create_world() — narrative-driven full world generation.
Story:  generate_sequel_scene() — .blend DNA → same-universe new scene.
Web:    API-less Midjourney/ChatGPT/Leonardo/DALL-E/Ideogram → Blender pipeline.
LLM:    plan_scene_with_all_llms() — Claude + ChatGPT + Gemini in parallel.
Unity:  export_complete_unity_project() — .unitypackage with C# scripts + NavMesh.

Typical flow:
  1. connect_blender
  2. create_scene_from_prompt  (or create_world for full world-building)
  3. scene_quality_check / auto_fix_scene
  4. design_scene_audio        (ambient sound + optional narration)
  5. render_preview
  6. export_complete_unity_project / export_glb

Raw Python execution is NOT exposed by default.
""".strip()


def build_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    mcp_path: str = "/mcp",
) -> FastMCP:
    mcp = FastMCP(
        "Remirdy Blender Studio",
        instructions=INSTRUCTIONS,
        host=host,
        port=port,
        streamable_http_path=mcp_path,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    for module in (
        connection_tools,
        scene_tools,
        game_tools,
        architecture_tools,
        interior_tools,
        render_tools,
        material_tools,
        node_design_tools, # Node-based design (Geometry + Shader nodes)
        animation_tools,   # Animation, drivers, timeline, history
        particle_tools,    # Game-ready scatter / vegetation / hair
        uv_tools,          # UV unwrapping
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
        agent_tools,       # Multi-Agent Scene Orchestration
        weather_tools,     # Real-time weather
        browser_tools,     # API-less image gen → Blender
        tournament_tools,  # Genetic algorithm tournament
        sequel_tools,      # DNA analysis + sequel generator
        world_tools,       # Procedural narrative world
        comfyui_tools,     # ComfyUI / Stable Diffusion local
        sound_tools,       # Automatic sound design
        nerf_tools,        # NeRF / Gaussian Splatting
        lipsync_tools,     # Lip sync animation
        multi_llm_tools,   # Multi-LLM orchestration
        unity_tools,       # Complete Unity project export
    ):
        module.register(mcp)
        log.info("Registered tools from %s", module.__name__)
    return mcp


def run() -> None:
    server = build_server()
    log.info("Starting Remirdy Blender Studio MCP over stdio…")
    server.run()
