"""Vision-powered critique agent. This is the heart of the 'multi-agent with self-reflection' experience."""
from __future__ import annotations

from typing import Any

from ..tools._common import call
from .base import AgentResult, BaseAgent, OrchestrationState, timed


class CritiqueAgent(BaseAgent):
    """
    Analyzes the current scene using screenshots + structural data + quality checks.
    Produces actionable suggestions that the coordinator can feed to other agents.
    """

    def __init__(self):
        super().__init__("critique")

    @timed
    def run(self, state: OrchestrationState, **kwargs: Any) -> AgentResult:
        """
        Run a full vision + quality critique pass via the bridge.
        Returns structured issues and concrete next actions.
        """
        try:
            # 1. Capture fresh understanding (these call into Blender)
            vision = call("analyze_scene_visuals", {"view": "camera"})
            graph = call("get_scene_graph", {})

            # 2. Run quality gate
            quality = call("scene_quality_check", {"aggressive": False})

            # 3. Build critique
            issues: list[dict[str, Any]] = []
            suggestions: list[str] = []

            score = 65

            if vision.get("ok"):
                v = vision.get("result", {})
                if not v.get("has_lights"):
                    issues.append({"severity": "high", "area": "lighting", "msg": "No lights detected"})
                    suggestions.append("run_lighting_specialist_pass(mood='cinematic')")
                if v.get("material_count", 0) < 3:
                    issues.append({"severity": "medium", "area": "materials", "msg": "Few materials"})
                    suggestions.append("run_materials_specialist_pass")

            # === Terrain-specific intelligence (Satellite + Multi-Agent synergy) ===
            objects = graph.get("result", {}).get("objects", []) if graph.get("ok") else []
            has_terrain = any("terrain" in str(o.get("name", "")).lower() or "ground" in str(o.get("name", "")).lower() for o in objects)

            if has_terrain:
                issues.append({"severity": "medium", "area": "terrain", "msg": "Real terrain detected — lighting & materials can be greatly improved"})
                suggestions.append("run_lighting_specialist_pass(mood='golden_hour', time_of_day='sunset')")
                suggestions.append("run_materials_specialist_pass(style='natural_biome')")
                if state.quality_score < 78:
                    suggestions.append("apply_biome_painter")

            if quality.get("ok"):
                q = quality.get("result", {})
                qs = q.get("quality_score", 70)
                score = max(30, min(95, int(qs)))
                for issue in q.get("issues", [])[:5]:
                    sev = issue.get("severity", "medium")
                    issues.append({"severity": sev, "area": issue.get("category", "general"), "msg": issue.get("description", "")})
                    if sev == "high":
                        suggestions.append("auto_fix_scene(aggressive=True)")

            if not issues:
                summary = f"Scene looks solid (score {score}/100)"
                suggestions = ["render_preview"]
            else:
                high = len([i for i in issues if i["severity"] == "high"])
                summary = f"{len(issues)} issues ({high} high). Score: {score}/100"

            state.quality_score = score
            state.last_vision = vision.get("result") if vision.get("ok") else None

            return AgentResult(
                agent="critique",
                success=True,
                summary=summary,
                details={"issues": issues, "quality_score": score},
                suggestions=list(dict.fromkeys(suggestions))[:6],
            )

        except Exception as exc:
            self.log.warning("Critique pass failed: %s", exc)
            return AgentResult(
                agent="critique",
                success=False,
                summary=f"Critique failed: {exc}",
                suggestions=["capture_viewport_screenshot", "scene_quality_check"],
            )

    # === Agent Self-Improvement Loop (real implementation) ===
    _success_memory = []

    def learn_from_success(self, scene_score: float, techniques_used: list[str]):
        """
        The CritiqueAgent now actually learns.
        High-scoring techniques get recorded and can influence future behavior.
        """
        if scene_score >= 85:
            self._success_memory.append({
                "score": scene_score,
                "techniques": techniques_used,
                "timestamp": __import__("time").time()
            })
            log.info(f"CritiqueAgent learned from excellent scene (score: {scene_score}). Techniques stored: {techniques_used}")

        # Simple bias: if certain techniques keep succeeding, we can surface them
        if len(self._success_memory) > 5:
            common = {}
            for entry in self._success_memory[-10:]:
                for t in entry["techniques"]:
                    common[t] = common.get(t, 0) + 1
            top_techniques = sorted(common.items(), key=lambda x: x[1], reverse=True)[:3]
            return {"status": "learning_updated", "top_successful_techniques": top_techniques}

        return {"status": "learning_recorded", "memory_size": len(self._success_memory)}
