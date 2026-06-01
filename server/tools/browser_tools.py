"""
Browser Automation MCP tools — API-less image generation → Blender pipeline.

Supported platforms (zero API keys required):
  midjourney  — Discord web + Midjourney bot
  chatgpt     — ChatGPT web (text + DALL-E images)
  leonardo    — Leonardo.ai
  dalle       — DALL-E via ChatGPT web
  ideogram    — Ideogram.ai

Workflow
--------
1. ``open_browser_session(platform)``      — headed browser, log in once
2. ``generate_image_and_build_scene(...)`` — generate → Blender scene
   OR ``chatgpt_plan_scene(...)``          — get JSON scene plan from ChatGPT
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..utils.browser_automation import (
    PLATFORM_LOGIN_URLS,
    chatgpt_plan_scene,
    clear_session,
    generate_and_build_scene,
    has_session,
    list_sessions,
    open_browser_for_login,
    run_async,
)
from ..utils.logging_utils import get_logger

log = get_logger("remirdy.browser_tools")


def register(mcp: FastMCP) -> None:

    # ── Session management ────────────────────────────────────────────────────

    @mcp.tool()
    def open_browser_session(platform: str) -> dict:
        """
        Open a headed (visible) browser window so you can log in to a platform manually.

        After you log in, cookies are saved to ``~/.remirdy/sessions/<platform>.json``
        and all future calls run headless (no visible window).

        platform: "midjourney" | "chatgpt" | "leonardo" | "dalle" | "ideogram"
        """
        platform = platform.lower().strip()
        login_url = PLATFORM_LOGIN_URLS.get(platform)
        if not login_url:
            return {
                "ok": False,
                "error": f"Unknown platform '{platform}'. Choose from: {', '.join(PLATFORM_LOGIN_URLS)}",
            }
        return run_async(open_browser_for_login(platform, login_url))

    @mcp.tool()
    def check_browser_sessions() -> dict:
        """
        Show which platforms have active saved sessions (logged-in cookies).
        Platforms with session=False require open_browser_session() first.
        """
        sessions = list_sessions()
        return {
            "ok": True,
            "sessions": sessions,
            "ready": [p for p, v in sessions.items() if v],
            "needs_login": [p for p, v in sessions.items() if not v],
        }

    @mcp.tool()
    def clear_browser_session(platform: str) -> dict:
        """Delete saved cookies for a platform, forcing re-login next time."""
        removed = clear_session(platform.lower().strip())
        return {"ok": True, "platform": platform, "session_cleared": removed}

    # ── Image generation → Blender ────────────────────────────────────────────

    @mcp.tool()
    def generate_image_and_build_scene(
        prompt: str,
        platform: str = "chatgpt",
        build_scene: bool = True,
        channel_url: str = "",
        wait_seconds: int = 120,
    ) -> dict:
        """
        Generate an image on a web AI platform (no API key) and optionally build
        a full Blender 3D scene from it.

        Steps:
          1. Generate image via the chosen platform.
          2. Run Gemini AI vision analysis on the result.
          3. Call build_layered_scene_from_image in Blender.

        Args:
            prompt       : What to generate (image description / scene description).
            platform     : "midjourney" | "chatgpt" | "leonardo" | "dalle" | "ideogram"
            build_scene  : If True, automatically build a Blender scene from the image.
            channel_url  : Required for Midjourney — paste your Discord channel URL here.
            wait_seconds : Seconds to wait for image generation (Midjourney needs ~300).

        Returns dict with image_path, scene_built, layers_detected, ai_scene_plan.
        """
        return run_async(
            generate_and_build_scene(
                prompt=prompt,
                platform=platform,
                build_scene=build_scene,
                channel_url=channel_url or None,
                wait_seconds=wait_seconds,
            )
        )

    @mcp.tool()
    def chatgpt_scene_planner(scene_description: str) -> dict:
        """
        Ask ChatGPT web to create a structured 3D scene plan from a description.

        ChatGPT will return a JSON object with: objects, lighting, camera, mood,
        color_palette, and environment — which you can then use to guide other
        Blender tools.

        Requires a saved ChatGPT session (call open_browser_session('chatgpt') first).

        Args:
            scene_description: e.g. "A ruined medieval castle at golden hour,
                                      misty atmosphere, lone knight in foreground"
        """
        if not has_session("chatgpt"):
            return {
                "ok": False,
                "error": "No ChatGPT session. Call open_browser_session('chatgpt') first.",
            }
        return run_async(chatgpt_plan_scene(scene_description))

    @mcp.tool()
    def generate_concept_art(
        prompt: str,
        platform: str = "leonardo",
        wait_seconds: int = 90,
    ) -> dict:
        """
        Generate concept art on a web platform without building a scene.
        Useful for getting a reference image before deciding how to build it.

        Returns: {"ok": True, "image_path": "/path/to/image.png", "platform": ...}

        Args:
            prompt       : Image description.
            platform     : "midjourney" | "chatgpt" | "leonardo" | "dalle" | "ideogram"
            wait_seconds : Max wait time for generation.
        """
        return run_async(
            generate_and_build_scene(
                prompt=prompt,
                platform=platform,
                build_scene=False,
                wait_seconds=wait_seconds,
            )
        )
