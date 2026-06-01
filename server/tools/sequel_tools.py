"""MCP tools for .blend DNA analysis and sequel scene generation."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from ..utils.logging_utils import get_logger

log = get_logger("remirdy.sequel_tools")


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def extract_scene_dna() -> dict:
        """
        Analyse the currently open Blender scene and extract its style DNA.

        Returns a fingerprint of the scene's aesthetic identity:
          - color_palette   : dominant hex colours
          - material_style  : metallic | organic | stone | stylized | mixed
          - light_style     : cinematic | golden_hour | studio | overcast | neon
          - light_temperature: estimated Kelvin (warm 3200 ↔ cool 7500)
          - geometry_density: sparse | medium | dense | ultra
          - era_hint        : medieval | sci_fi | fantasy | post_apocalyptic | contemporary
          - scene_mood      : warm | cold | dark | bright | neutral
          - has_characters, has_terrain, has_water, has_vegetation

        Use this before generate_sequel_scene to understand your scene's DNA.
        """
        from ..utils.blend_dna import extract_dna_from_bridge
        return extract_dna_from_bridge()

    @mcp.tool()
    def generate_sequel_scene(
        original_prompt: str = "",
        auto_build: bool = True,
        polish_iterations: int = 2,
    ) -> dict:
        """
        Extract the current scene's DNA and generate a "sequel" — a new scene
        in the same fictional universe but a different location and situation.

        Perfect for game developers who want a consistent world across multiple
        levels, or animation studios who need consistent environments across shots.

        Steps:
          1. Extract DNA from the current Blender scene.
          2. Build a sequel prompt (same era/mood/style, new location).
          3. Generate the new scene with full multi-agent polish.
          4. Return the sequel scene + DNA comparison.

        Args:
            original_prompt  : The prompt used for the original scene (helps
                               DNA-to-sequel mapping pick a better location).
            auto_build       : If True, immediately build the sequel scene in Blender.
            polish_iterations: How many multi-agent polish iterations (1–3).
        """
        from ..utils.blend_dna import extract_dna_from_bridge, dna_to_sequel_prompt
        from ..agents.coordinator import SceneCoordinator
        from ..tools._common import call

        # Step 1: Extract DNA
        dna = extract_dna_from_bridge()
        if dna.get("error"):
            return {"ok": False, "error": dna["error"]}

        # Step 2: Build sequel prompt
        sequel_prompt = dna_to_sequel_prompt(dna, original_prompt)
        log.info("[Sequel] Generated prompt: %s", sequel_prompt[:100])

        if not auto_build:
            return {
                "ok": True,
                "dna": dna,
                "sequel_prompt": sequel_prompt,
                "built": False,
                "message": "Use sequel_prompt with create_scene_from_prompt to build the scene.",
            }

        # Step 3: Build + polish
        coord = SceneCoordinator()
        scene_result = call("create_scene_from_prompt", {"prompt": sequel_prompt})

        focus = ["lighting", "materials", "critique"]
        if dna.get("has_terrain"):
            focus.insert(0, "composition")

        polish = coord.orchestrate(
            prompt=sequel_prompt,
            focus_areas=focus,
            max_iterations=max(1, min(polish_iterations, 3)),
            use_vision_critique=True,
        )

        return {
            "ok": True,
            "original_dna": dna,
            "sequel_prompt": sequel_prompt,
            "scene_result": scene_result,
            "polish_report": polish,
            "final_score": polish.get("final_quality_score", 0),
            "built": True,
            "dna_comparison": {
                "era": dna["era_hint"],
                "mood": dna["scene_mood"],
                "material_style": dna["material_style"],
                "light_style": dna["light_style"],
            },
        }

    @mcp.tool()
    def generate_sequel_from_dna(
        dna_json: str,
        auto_build: bool = True,
    ) -> dict:
        """
        Generate a sequel scene from a previously extracted DNA dict (as JSON string).

        Use this when you've already run extract_scene_dna and want to reuse
        the fingerprint for multiple sequels without re-analysing the scene.

        Args:
            dna_json   : JSON string from a previous extract_scene_dna call.
            auto_build : Whether to immediately build the scene in Blender.
        """
        import json as _json
        from ..utils.blend_dna import dna_to_sequel_prompt
        from ..agents.coordinator import SceneCoordinator
        from ..tools._common import call

        try:
            dna = _json.loads(dna_json)
        except Exception as exc:
            return {"ok": False, "error": f"Invalid DNA JSON: {exc}"}

        sequel_prompt = dna_to_sequel_prompt(dna)

        if not auto_build:
            return {"ok": True, "sequel_prompt": sequel_prompt, "built": False}

        coord = SceneCoordinator()
        call("create_scene_from_prompt", {"prompt": sequel_prompt})
        polish = coord.orchestrate(
            prompt=sequel_prompt,
            focus_areas=["lighting", "materials", "critique"],
            max_iterations=2,
        )

        return {
            "ok": True,
            "sequel_prompt": sequel_prompt,
            "polish_report": polish,
            "final_score": polish.get("final_quality_score", 0),
            "built": True,
        }
