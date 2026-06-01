"""Scene Optimization & Delivery Agent — Professional post-processing for production.

This agent runs after scene creation (terrain, city, video reconstruction, etc.)
and prepares the scene for real delivery to game engines or other DCCs.
"""
from __future__ import annotations

from typing import Any

from ..tools._common import call
from .base import AgentResult, BaseAgent, OrchestrationState, timed


class OptimizationAgent(BaseAgent):
    """
    Professional optimization and delivery preparation.

    Responsibilities:
    - LOD generation
    - Material cleanup and optimization
    - UV / Lightmap preparation
    - Collision proxies
    - Engine readiness checks and reports
    - One-click preparation for Unity / Unreal / Web
    """

    def __init__(self):
        super().__init__("optimization")

    @timed
    def run(self, state: OrchestrationState, **kwargs: Any) -> AgentResult:
        target_engine = kwargs.get("target_engine", "generic")  # unity | unreal | web | generic
        aggressive = kwargs.get("aggressive", False)

        try:
            suggestions: list[str] = []
            actions_taken: list[str] = []

            # 1. Basic quality cleanup (always useful)
            try:
                call("organize_scene", {})
                call("set_origins_and_pivots", {"mode": "bottom_center"})
                actions_taken.append("Organized scene + fixed pivots")
            except Exception:
                pass

            # 2. Material optimization
            try:
                call("repair_materials", {})
                actions_taken.append("Repaired and consolidated materials")
            except Exception:
                pass

            # 3. Professional LOD generation
            try:
                summary = call("get_scene_summary", {})
                total_polys = summary.get("result", {}).get("total_polygons", 0)

                if total_polys > 80000:
                    call("generate_lods_advanced", {"ratios": [0.5, 0.25, 0.1]})
                    actions_taken.append("Generated 3-level LODs for heavy scene")
            except Exception:
                pass

            # 4. Lightmap UV preparation (very useful for baked lighting)
            try:
                call("prepare_lightmap_uvs", {"margin": 0.01})
                actions_taken.append("Prepared Lightmap UV channel")
            except Exception:
                pass

            # 5. Engine-specific preparation
            if target_engine == "unity":
                try:
                    call("prepare_for_unity_export", {})
                    actions_taken.append("Prepared for Unity (scale, materials, collisions)")
                except Exception:
                    pass
                suggestions.append("export_glb with unity target")

            elif target_engine == "unreal":
                try:
                    call("prepare_for_unreal_export", {})
                    actions_taken.append("Prepared for Unreal")
                except Exception:
                    pass
                suggestions.append("export_fbx with unreal target")

            else:
                try:
                    call("check_engine_readiness", {"target": target_engine})
                    actions_taken.append(f"Ran engine readiness check for {target_engine}")
                except Exception:
                    pass

            # 5. Collision proxies for gameplay scenes
            if target_engine in ("unity", "unreal", "generic"):
                try:
                    call("create_collision_proxies", {"mode": "convex"})
                    actions_taken.append("Generated collision proxies")
                except Exception:
                    pass

            summary_text = f"Optimization pass completed for {target_engine}"
            if actions_taken:
                summary_text += f" ({len(actions_taken)} actions)"

            return AgentResult(
                agent="optimization",
                success=True,
                summary=summary_text,
                suggestions=suggestions[:6],
                details={
                    "target_engine": target_engine,
                    "actions_taken": actions_taken,
                },
            )

        except Exception as exc:
            return AgentResult(
                agent="optimization",
                success=False,
                summary=f"Optimization pass failed: {exc}",
                suggestions=["scene_quality_check", "auto_fix_scene"],
            )
