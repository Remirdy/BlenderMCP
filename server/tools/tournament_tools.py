"""MCP tools for the Agent Tournament — Genetic Algorithm for Optimal Scenes."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..utils.logging_utils import get_logger

log = get_logger("remirdy.tournament_tools")

_tournament: "TournamentOrchestrator | None" = None  # lazy singleton


def _get_tournament():
    global _tournament
    if _tournament is None:
        from ..agents.tournament_agent import TournamentOrchestrator
        from ..agents.coordinator import SceneCoordinator
        _tournament = TournamentOrchestrator(SceneCoordinator())
    return _tournament


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def run_scene_tournament(
        prompt: str,
        population: int = 3,
        generations: int = 3,
        seeds: list[int] | None = None,
    ) -> dict:
        """
        Run a genetic-algorithm tournament to find the optimal Blender scene for a prompt.

        How it works:
          1. Generate ``population`` scene candidates with different random traits.
          2. CritiqueAgent scores each (0–100) based on lighting, materials, composition.
          3. Top-2 candidates are crossbred: best lighting from one, best materials
             from the other → child candidate.
          4. Repeat for ``generations`` cycles.
          5. Return the winner (highest score), full lineage, and what made it win.

        Args:
            prompt      : Scene description to optimise, e.g.
                          "gothic cathedral interior at golden hour".
            population  : Candidates per generation (2–6, default 3).
            generations : Evolution cycles (1–5, default 3).
            seeds       : Optional fixed seed list for reproducibility.

        Returns dict with winner (seed, score, lighting, materials), all_individuals,
        generation_scores, and a plain-English summary.
        """
        return _get_tournament().run_tournament_as_job(
            prompt=prompt,
            population=max(2, min(population, 6)),
            generations=max(1, min(generations, 5)),
            seeds=seeds,
        )

    @mcp.tool()
    def run_quick_tournament(prompt: str) -> dict:
        """
        Fast 2-candidate, 2-generation tournament. Results in ~30 s vs ~2 min for full.
        Good for quick experimentation before committing to a full tournament.
        """
        return _get_tournament().run_tournament_as_job(
            prompt=prompt, population=2, generations=2
        )

    @mcp.tool()
    def apply_tournament_winner(
        prompt: str,
        winner_seed: int,
        winner_lighting: str = "balanced",
        winner_materials: str = "balanced",
        winner_composition: str = "hero",
    ) -> dict:
        """
        Apply the winning traits from a previous tournament to build the final scene.

        Use this after run_scene_tournament: take the winner's seed/lighting/materials
        and build the definitive version with full multi-agent polish.

        Args:
            prompt             : Original scene prompt.
            winner_seed        : Seed from the tournament winner.
            winner_lighting    : Lighting mood from the winner.
            winner_materials   : Materials style from the winner.
            winner_composition : Composition mood from the winner.
        """
        from ..agents.coordinator import SceneCoordinator
        from ..agents.lighting_agent import LightingAgent
        from ..agents.materials_agent import MaterialsAgent
        from ..agents.composition_agent import CompositionAgent
        from ..agents.base import OrchestrationState

        log.info("[Tournament] Applying winner traits: seed=%d", winner_seed)

        coord = SceneCoordinator()
        state = OrchestrationState(
            prompt=prompt,
            focus_areas=["lighting", "materials", "composition", "critique"],
        )

        try:
            LightingAgent().run(state, mood=winner_lighting)
            MaterialsAgent().run(state, style=winner_materials)
            CompositionAgent().run(state, mood=winner_composition)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        polish = coord.orchestrate(
            prompt=prompt,
            focus_areas=["lighting", "materials", "critique"],
            max_iterations=2,
            use_vision_critique=True,
        )

        return {
            "ok": True,
            "prompt": prompt,
            "applied_seed": winner_seed,
            "applied_traits": {
                "lighting": winner_lighting,
                "materials": winner_materials,
                "composition": winner_composition,
            },
            "polish_result": polish,
            "final_score": polish.get("final_quality_score", 0),
        }
