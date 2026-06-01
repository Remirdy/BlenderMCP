"""Lighting specialist agent."""
from __future__ import annotations

from typing import Any

from ..tools._common import call
from .base import AgentResult, BaseAgent, OrchestrationState, timed


class LightingAgent(BaseAgent):
    """Optimizes scene lighting using existing render/lighting operations via the bridge."""

    def __init__(self):
        super().__init__("lighting")

    @timed
    def run(self, state: OrchestrationState, **kwargs: Any) -> AgentResult:
        mood = kwargs.get("mood", "balanced")
        time_of_day = kwargs.get("time_of_day", None)

        try:
            suggestions: list[str] = []

            if time_of_day == "golden_hour" or mood == "cinematic":
                call("setup_cinematic_lighting", {})
                suggestions.append("Added dramatic cinematic lighting")
            elif mood == "bright":
                call("setup_lighting", {"style": "bright"})
                suggestions.append("Applied bright even lighting")
            else:
                call("setup_three_point_lighting", {"strength": 1.15})
                call("setup_archviz_lighting", {})
                suggestions.append("Balanced three-point + environment lighting")

            call("apply_render_preset", {"preset": "portfolio_render"})

            return AgentResult(
                agent="lighting",
                success=True,
                summary=f"Lighting updated (mood={mood})",
                suggestions=suggestions,
                details={"mood": mood, "time_of_day": time_of_day},
            )

        except Exception as exc:
            return AgentResult(
                agent="lighting",
                success=False,
                summary=f"Lighting pass failed: {exc}",
                suggestions=["setup_cinematic_lighting", "setup_three_point_lighting"],
            )
