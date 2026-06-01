"""Composition / Camera specialist agent — framing, hero shots, cinematic cameras."""
from __future__ import annotations

from typing import Any

from ..tools._common import call
from .base import AgentResult, BaseAgent, OrchestrationState, timed


class CompositionAgent(BaseAgent):
    """
    Responsible for camera placement, focal length, depth of field, and overall framing.
    Especially powerful after terrain creation for dramatic shots.
    """

    def __init__(self):
        super().__init__("composition")

    @timed
    def run(self, state: OrchestrationState, **kwargs: Any) -> AgentResult:
        mood = kwargs.get("mood", "hero")
        is_terrain = "terrain" in state.prompt.lower() or kwargs.get("is_terrain", False)

        try:
            suggestions: list[str] = []

            if is_terrain or mood in ("dramatic", "hero", "golden_hour"):
                # Big dramatic terrain / landscape shot
                call("setup_archviz_camera", {})
                call("setup_camera_auto_focus", {})
                suggestions.append("Hero landscape camera + auto-focus placed")
                suggestions.append("Consider lowering horizon for epic scale feel")

            elif mood in ("cinematic", "film"):
                call("setup_cinematic_lighting", {})  # also helps framing
                call("setup_camera", {"focal_length": 50})
                suggestions.append("Cinematic 50mm camera + dramatic framing")

            elif mood == "isometric":
                call("setup_isometric_camera", {})
                suggestions.append("Clean isometric/game camera setup")

            else:
                call("setup_camera", {})
                suggestions.append("Standard well-composed camera added")

            # Improve DOF where it makes sense
            try:
                call("setup_camera_auto_focus", {"use_dof": True})
            except Exception:
                pass

            return AgentResult(
                agent="composition",
                success=True,
                summary=f"Camera & framing updated (mood={mood})",
                suggestions=suggestions,
                details={"mood": mood, "terrain_mode": is_terrain},
            )

        except Exception as exc:
            return AgentResult(
                agent="composition",
                success=False,
                summary=f"Composition pass failed: {exc}",
                suggestions=["setup_archviz_camera", "setup_camera"],
            )
