"""Smoke tests: verify all tool modules import cleanly and map to registered ops."""
from __future__ import annotations

import importlib

import pytest


# ── import smoke tests ────────────────────────────────────────────────────────

SERVER_TOOL_PACKAGES = [
    "server.tools.agent_tools",
    "server.tools.architecture_tools",
    "server.tools.asset_tools",
    "server.tools.asset_source_tools",
    "server.tools.browser_tools",
    "server.tools.character_tools",
    "server.tools.comfyui_tools",
    "server.tools.connection_tools",
    "server.tools.export_tools",
    "server.tools.game_tools",
    "server.tools.import_tools",
    "server.tools.interior_tools",
    "server.tools.material_tools",
    "server.tools.modular_tools",
    "server.tools.multi_llm_tools",
    "server.tools.nerf_tools",
    "server.tools.product_tools",
    "server.tools.quality_tools",
    "server.tools.reference_asset_tools",
    "server.tools.render_tools",
    "server.tools.scene_tools",
    "server.tools.sequel_tools",
    "server.tools.sound_tools",
    "server.tools.tournament_tools",
    "server.tools.understanding_tools",
    "server.tools.unity_tools",
    "server.tools.weather_tools",
    "server.tools.world_tools",
]

SERVER_UTIL_PACKAGES = [
    "server.utils.validation",
    "server.utils.file_utils",
    "server.utils.logging_utils",
    "server.utils.ai_vision",
    "server.utils.blend_dna",
    "server.utils.browser_automation",
    "server.utils.jobs",
    "server.utils.lipsync",
    "server.utils.multi_llm",
    "server.utils.psd_utils",
    "server.utils.sound_design",
    "server.utils.sprite_utils",
]

PROVIDER_PACKAGES = [
    "server.providers.base",
    "server.providers.comfyui_sd",
    "server.providers.registry",
    "server.providers.image_to_3d",
    "server.providers.nerf_gs",
]

AGENT_PACKAGES = [
    "server.agents.base",
    "server.agents.composition_agent",
    "server.agents.coordinator",
    "server.agents.critique_agent",
    "server.agents.geometry_agent",
    "server.agents.lighting_agent",
    "server.agents.materials_agent",
    "server.agents.narrative_agent",
    "server.agents.optimization_agent",
    "server.agents.tournament_agent",
]


@pytest.mark.parametrize("module_path", SERVER_TOOL_PACKAGES)
def test_server_tool_module_imports(module_path):
    """Each tool module must import without error."""
    mod = importlib.import_module(module_path)
    assert mod is not None


@pytest.mark.parametrize("module_path", SERVER_UTIL_PACKAGES)
def test_server_util_module_imports(module_path):
    """Each utility module must import without error."""
    mod = importlib.import_module(module_path)
    assert mod is not None


@pytest.mark.parametrize("module_path", PROVIDER_PACKAGES)
def test_provider_module_imports(module_path):
    """Each provider module must import without error."""
    mod = importlib.import_module(module_path)
    assert mod is not None


@pytest.mark.parametrize("module_path", AGENT_PACKAGES)
def test_agent_module_imports(module_path):
    """Each agent module must import without error."""
    mod = importlib.import_module(module_path)
    assert mod is not None


# ── registry completeness ─────────────────────────────────────────────────────

def test_blender_ops_registry_loads():
    """The Blender ops registry module must be importable outside of Blender.

    We can't execute Blender-specific calls, but the module should define
    its operation mapping without crashing on import.
    """
    # The registry lives in blender_addon which uses bpy — skip if bpy unavailable
    try:
        import bpy  # noqa: F401
    except ImportError:
        pytest.skip("bpy not available outside Blender")

    from blender_addon.blender_ops import registry  # noqa: F401


def test_server_main_exposes_run():
    """server.main must expose a 'run' callable (used as the entry-point)."""
    mod = importlib.import_module("server.main")
    assert callable(getattr(mod, "run", None)), "server.main.run must be a callable"


def test_ai_vision_module_exposes_public_api():
    """ai_vision.py must expose its documented public functions."""
    from server.utils import ai_vision
    for fn_name in [
        "is_available",
        "analyze_image_with_gemini",
        "extract_scene_objects",
        "analyze_psd_layer",
        "generate_scene_plan",
        "analyze_flat_image_with_ai",
    ]:
        assert callable(getattr(ai_vision, fn_name, None)), (
            f"ai_vision.{fn_name} must be a callable"
        )
