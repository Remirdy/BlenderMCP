"""Scene Coordinator — the multi-agent orchestrator.

This is the main entry point for 'orchestrate_scene_with_agents'.
It follows the same spirit as server/providers/registry.py (parallel + intelligent passes).
"""
from __future__ import annotations

from typing import Any

from ..utils.logging_utils import get_logger
from .base import AgentName, OrchestrationState
from .composition_agent import CompositionAgent
from .critique_agent import CritiqueAgent
from .geometry_agent import GeometryAgent
from .lighting_agent import LightingAgent
from .materials_agent import MaterialsAgent
from .narrative_agent import NarrativeAgent
from .optimization_agent import OptimizationAgent

log = get_logger("remirdy.agents.coordinator")


class SceneCoordinator:
    """
    Runs a sequence of specialist agents with optional vision critique loops.

    Example:
        coord = SceneCoordinator()
        result = coord.orchestrate(
            prompt="dramatic Kapadokya terrain at sunset",
            focus_areas=["lighting", "critique"],
            max_iterations=3
        )
    """

    def __init__(self):
        self.agents: dict[AgentName, Any] = {
            "geometry": GeometryAgent(),
            "materials": MaterialsAgent(),
            "lighting": LightingAgent(),
            "composition": CompositionAgent(),
            "critique": CritiqueAgent(),
            "optimization": OptimizationAgent(),
            "narrative": NarrativeAgent(),
        }

    def orchestrate(
        self,
        prompt: str,
        focus_areas: list[AgentName] | None = None,
        max_iterations: int = 3,
        use_vision_critique: bool = True,
    ) -> dict[str, Any]:
        """
        Main high-level entry point.
        Returns a rich report with history, final score, and what was done.
        """
        if focus_areas is None:
            focus_areas = ["lighting", "critique"]

        state = OrchestrationState(
            prompt=prompt,
            focus_areas=focus_areas,
            max_iterations=max(1, min(max_iterations, 6)),
        )

        log.info("Starting multi-agent orchestration | prompt=%s | focus=%s", prompt[:60], focus_areas)

        for iteration in range(1, state.max_iterations + 1):
            state.iteration = iteration
            log.info("=== Iteration %d/%d ===", iteration, state.max_iterations)

            # Run requested specialists first
            for area in focus_areas:
                if area == "critique":
                    continue
                agent = self.agents.get(area)
                if agent:
                    result = agent.run(state)
                    agent._record(state, result)

            # Run critique (vision self-reflection)
            if use_vision_critique and "critique" in self.agents:
                critique = self.agents["critique"]
                c_result = critique.run(state)
                critique._record(state, c_result)

                # === Smart auto-execution of critique suggestions (Goal 3) ===
                auto_triggered = []
                for suggestion in c_result.suggestions:
                    suggestion_lower = suggestion.lower()

                    if "lighting" in suggestion_lower and "lighting" in self.agents:
                        mood = "cinematic" if "cinematic" in suggestion_lower or "dramatic" in suggestion_lower else "balanced"
                        tod = "golden_hour" if "golden" in suggestion_lower or "sunset" in suggestion_lower else None
                        res = self.agents["lighting"].run(state, mood=mood, time_of_day=tod)
                        self.agents["lighting"]._record(state, res)
                        auto_triggered.append(f"lighting({mood})")

                    elif "materials" in suggestion_lower and "materials" in self.agents:
                        style = "natural_biome" if "biome" in suggestion_lower or "terrain" in suggestion_lower else "balanced"
                        res = self.agents["materials"].run(state, style=style)
                        self.agents["materials"]._record(state, res)
                        auto_triggered.append(f"materials({style})")

                    elif "composition" in suggestion_lower and "composition" in self.agents:
                        res = self.agents["composition"].run(state, mood="hero")
                        self.agents["composition"]._record(state, res)
                        auto_triggered.append("composition(hero)")

                    elif "geometry" in suggestion_lower or "cleanup" in suggestion_lower:
                        if "geometry" in self.agents:
                            res = self.agents["geometry"].run(state, focus="cleanup")
                            self.agents["geometry"]._record(state, res)
                            auto_triggered.append("geometry(cleanup)")

                    elif "optimize" in suggestion_lower or "delivery" in suggestion_lower or "export" in suggestion_lower:
                        if "optimization" in self.agents:
                            engine = "unity" if "unity" in suggestion_lower else ("unreal" if "unreal" in suggestion_lower else "generic")
                            res = self.agents["optimization"].run(state, target_engine=engine)
                            self.agents["optimization"]._record(state, res)
                            auto_triggered.append(f"optimization({engine})")

                if auto_triggered:
                    log.info("Auto-triggered from critique: %s", ", ".join(auto_triggered))

                # Smart early exit on high quality
                if c_result.success and state.quality_score >= 82:
                    log.info("High quality score reached (%.0f) — early exit", state.quality_score)
                    break

        final_score = state.quality_score or 70

        return {
            "ok": True,
            "prompt": prompt,
            "iterations_run": state.iteration,
            "final_quality_score": final_score,
            "focus_areas": focus_areas,
            "history": state.history,
            "last_vision": state.last_vision,
            "summary": self._build_summary(state, final_score),
        }

    def _build_summary(self, state: OrchestrationState, score: float) -> str:
        passes = len(state.history)
        return (
            f"Multi-agent run completed after {state.iteration} iteration(s) "
            f"({passes} specialist passes). Final score: {score}/100."
        )
