"""Materials specialist agent — handles PBR assignment, style application, and biome-aware texturing."""
from __future__ import annotations

from typing import Any

from ..tools._common import call
from .base import AgentResult, BaseAgent, OrchestrationState, timed


class MaterialsAgent(BaseAgent):
    """
    Applies and refines materials.
    Supports style hints and special awareness for terrain/biome scenes.
    """

    def __init__(self):
        super().__init__("materials")

    @timed
    def run(self, state: OrchestrationState, **kwargs: Any) -> AgentResult:
        style = kwargs.get("style", "balanced")
        is_terrain = kwargs.get("is_terrain", False) or "terrain" in state.prompt.lower()

        try:
            suggestions: list[str] = []

            if is_terrain or "biome" in style.lower():
                # Terrain / nature specific
                call("create_stylized_materials", {})
                call("apply_style_preset", {"preset": "natural"})
                suggestions.append("Applied biome-aware stylized materials + grass/rock variation")
                suggestions.append("Consider apply_biome_painter for scattering")

            elif style in ("rich", "cinematic", "dramatic"):
                call("create_archviz_materials", {})
                call("apply_style_preset", {"preset": "dramatic"})
                suggestions.append("Rich cinematic/archviz material palette applied")

            elif style in ("stylized", "game", "cartoon"):
                call("create_stylized_materials", {})
                call("apply_style_preset", {"preset": "stylized"})
                suggestions.append("Clean stylized material set applied")

            else:
                # Default balanced approach
                call("apply_style_preset", {"preset": "balanced"})
                suggestions.append("Balanced PBR material treatment applied")

            # Try to repair any broken materials as a safety net
            try:
                call("repair_materials", {})
            except Exception:
                pass

            return AgentResult(
                agent="materials",
                success=True,
                summary=f"Materials updated (style={style})",
                suggestions=suggestions,
                details={"style": style, "terrain_mode": is_terrain},
            )

        except Exception as exc:
            return AgentResult(
                agent="materials",
                success=False,
                summary=f"Materials pass failed: {exc}",
                suggestions=["create_stylized_materials", "apply_style_preset"],
            )
