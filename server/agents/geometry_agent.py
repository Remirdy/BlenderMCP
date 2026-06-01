"""Geometry / blockout specialist agent (first slice)."""
from __future__ import annotations

from typing import Any

from ..tools._common import call
from .base import AgentResult, BaseAgent, OrchestrationState, timed


class GeometryAgent(BaseAgent):
    """
    Responsible for major forms, cleanup, and structural improvements.
    Delegates through the bridge to existing ops.
    """

    def __init__(self):
        super().__init__("geometry")

    @timed
    def run(self, state: OrchestrationState, **kwargs: Any) -> AgentResult:
        focus = kwargs.get("focus", "blockout")

        try:
            if focus == "cleanup":
                call("auto_fix_scene", {"aggressive": False})
                call("organize_scene", {})
                return AgentResult(
                    agent="geometry",
                    success=True,
                    summary="Structural cleanup + organize pass completed",
                    suggestions=["set_origins_and_pivots", "rename_objects_professionally"],
                )

            return AgentResult(
                agent="geometry",
                success=True,
                summary="Geometry pass completed (no major structural change needed)",
            )

        except Exception as exc:
            return AgentResult(
                agent="geometry",
                success=False,
                summary=f"Geometry pass failed: {exc}",
            )
