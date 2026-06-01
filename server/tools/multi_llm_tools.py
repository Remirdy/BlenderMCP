"""MCP tools — Multi-LLM Orchestration for scene planning."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from ..utils.logging_utils import get_logger

log = get_logger("remirdy.multi_llm_tools")


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def check_llm_providers() -> dict:
        """
        Show which LLM providers are configured and ready for multi-LLM orchestration.
        Returns: available providers, which need API keys, browser session status.
        """
        from ..utils.multi_llm import available_providers, ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY
        avail = available_providers()
        return {
            "ok": True,
            "available_providers": avail,
            "provider_status": {
                "claude":          {"configured": bool(ANTHROPIC_API_KEY), "key_var": "ANTHROPIC_API_KEY"},
                "openai":          {"configured": bool(OPENAI_API_KEY),    "key_var": "OPENAI_API_KEY"},
                "gemini":          {"configured": bool(GEMINI_API_KEY),    "key_var": "GEMINI_API_KEY or GOOGLE_GEMINI_API_KEY"},
                "chatgpt_browser": {"configured": "chatgpt_browser" in avail, "key_var": "None (browser session required)"},
            },
            "ready_count": len(avail),
        }

    @mcp.tool()
    def plan_scene_with_all_llms(
        scene_description: str,
        strategy: str = "best",
        providers: list[str] | None = None,
        timeout_seconds: float = 45.0,
        auto_build: bool = False,
    ) -> dict:
        """
        Send a scene description to ALL configured LLMs in parallel and pick the best plan.

        Claude + ChatGPT + Gemini all plan the same scene simultaneously.
        The winner is selected by scoring plan completeness and detail.
        Optionally build the winning scene immediately in Blender.

        Strategy options:
          "best"    — Run all, score each, return winner (default).
          "fastest" — Return whichever LLM responds first.
          "ensemble"— Return all responses without selecting a winner.

        Args:
            scene_description : What the scene should look like.
            strategy          : "best" | "fastest" | "ensemble"
            providers         : List of providers to use. None = all configured.
                                Options: "claude", "openai", "gemini", "chatgpt_browser"
            timeout_seconds   : Max wait per provider (default 45s).
            auto_build        : If True, build the winning scene plan in Blender.

        Returns: winner_provider, winner_plan, all_responses, scores, timing.
        """
        from ..utils.multi_llm import orchestrate_llms
        from ..tools._common import call

        result = orchestrate_llms(
            scene_description=scene_description,
            providers=providers,
            strategy=strategy,
            timeout_s=timeout_seconds,
        )

        if auto_build and result.get("ok") and result.get("winner_plan"):
            plan = result["winner_plan"]
            # Convert plan to a scene_from_prompt call
            mood = plan.get("mood", "")
            objects_desc = ", ".join(
                o.get("name", "") for o in plan.get("objects", [])[:5]
            )
            reconstructed_prompt = f"{mood} scene with {objects_desc}. {scene_description}"

            scene_result = call("create_scene_from_prompt", {"prompt": reconstructed_prompt})
            result["scene_built"] = True
            result["scene_result"] = scene_result
        else:
            result["scene_built"] = False

        return result

    @mcp.tool()
    def compare_llm_styles(
        scene_description: str,
        render_each: bool = False,
    ) -> dict:
        """
        Ask all configured LLMs to plan the same scene, then compare their approaches.
        Shows side-by-side what Claude, ChatGPT, and Gemini would each suggest.

        Useful for understanding how different AI models interpret the same creative brief.

        Args:
            scene_description : The scene to plan.
            render_each       : If True, build and render one scene per LLM (slow).
        """
        from ..utils.multi_llm import orchestrate_llms
        from ..tools._common import call

        result = orchestrate_llms(
            scene_description=scene_description,
            strategy="ensemble",
            timeout_s=45.0,
        )

        comparison = {}
        for provider, data in result.get("all_responses", {}).items():
            plan = data.get("plan") or {}
            comparison[provider] = {
                "mood": plan.get("mood", "not specified"),
                "object_count": len(plan.get("objects", [])),
                "lighting_style": plan.get("lighting", {}).get("style", "not specified"),
                "camera_angle": plan.get("camera", {}).get("angle", "not specified"),
                "color_palette": plan.get("color_palette", []),
                "top_objects": [o.get("name") for o in plan.get("objects", [])[:3]],
                "ok": data.get("ok"),
            }

        return {
            **result,
            "comparison": comparison,
            "insight": (
                f"Compared {len(comparison)} LLM scene plans for: '{scene_description[:60]}'. "
                f"Use plan_scene_with_all_llms(strategy='best') to automatically pick the winner."
            ),
        }
