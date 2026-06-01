"""
Agent Tournament — Genetic Algorithm for Optimal Scenes.

Runs the same prompt through multiple seeds, scores each result with
CritiqueAgent, then crossbreeds the best elements across generations.

Algorithm
---------
Generation 0  : Generate N scenes with different random seeds.
                CritiqueAgent scores each (0–100).

Crossbreeding  : Take top-2 parents.  Extract their best-scoring
                 specialist passes (lighting, materials, composition).
                 Apply parent-1's lighting + parent-2's materials to a
                 new child scene generated from a blended seed.

Repeat for G generations.  Return the overall winner + full lineage.

Usage
-----
    from server.agents.tournament_agent import TournamentOrchestrator
    from server.agents.coordinator import SceneCoordinator

    t = TournamentOrchestrator(SceneCoordinator())
    result = t.run_tournament("gothic cathedral at sunset", population=3, generations=3)
"""
from __future__ import annotations

import random
import time
from typing import Any

from ..utils.logging_utils import get_logger
from ..utils import jobs as job_tracker
from .base import AgentResult, OrchestrationState
from .coordinator import SceneCoordinator
from .critique_agent import CritiqueAgent
from .lighting_agent import LightingAgent
from .materials_agent import MaterialsAgent
from .composition_agent import CompositionAgent

log = get_logger("remirdy.agents.tournament")


# ── Individual ────────────────────────────────────────────────────────────────

class Individual:
    """One scene candidate in the tournament population."""

    def __init__(
        self,
        prompt: str,
        seed: int,
        generation: int,
        parent_seeds: list[int] | None = None,
    ):
        self.prompt = prompt
        self.seed = seed
        self.generation = generation
        self.parent_seeds = parent_seeds or []
        self.score: float = 0.0
        self.history: list[dict[str, Any]] = []
        self.lighting_mood: str = "balanced"
        self.materials_style: str = "balanced"
        self.composition_mood: str = "hero"
        self.result: dict[str, Any] = {}

    def as_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "generation": self.generation,
            "score": round(self.score, 1),
            "parent_seeds": self.parent_seeds,
            "lighting_mood": self.lighting_mood,
            "materials_style": self.materials_style,
            "composition_mood": self.composition_mood,
        }


# ── Crossbreed logic ──────────────────────────────────────────────────────────

_LIGHTING_MOODS = ["balanced", "cinematic", "bright", "golden_hour", "overcast", "neon"]
_MATERIAL_STYLES = ["balanced", "natural_biome", "stylized", "industrial", "warm_organic"]
_COMPOSITION_MOODS = ["hero", "cinematic", "product", "epic", "intimate"]


def _crossbreed(parent1: Individual, parent2: Individual, generation: int) -> Individual:
    """Create a child by mixing the best genes of two parents."""
    # Blend seed: arithmetic mean with slight mutation
    rng = random.Random(parent1.seed ^ parent2.seed ^ generation)
    child_seed = (parent1.seed + parent2.seed) // 2 + rng.randint(-50, 50)

    child = Individual(
        prompt=parent1.prompt,
        seed=child_seed,
        generation=generation,
        parent_seeds=[parent1.seed, parent2.seed],
    )

    # Inherit best trait per category from whichever parent scored higher
    if parent1.score >= parent2.score:
        child.lighting_mood = parent1.lighting_mood
        child.composition_mood = parent1.composition_mood
        child.materials_style = parent2.materials_style  # diversify
    else:
        child.lighting_mood = parent2.lighting_mood
        child.composition_mood = parent2.composition_mood
        child.materials_style = parent1.materials_style

    # Small mutation: randomly swap one trait
    if rng.random() < 0.3:
        child.lighting_mood = rng.choice(_LIGHTING_MOODS)
    if rng.random() < 0.2:
        child.materials_style = rng.choice(_MATERIAL_STYLES)

    log.info(
        "[Tournament] Crossbreed gen%d: seed=%d, lighting=%s, materials=%s",
        generation, child_seed, child.lighting_mood, child.materials_style,
    )
    return child


# ── Tournament Orchestrator ───────────────────────────────────────────────────

class TournamentOrchestrator:
    """Runs a multi-generation tournament to find the optimal scene for a prompt."""

    def __init__(self, coordinator: SceneCoordinator | None = None):
        self.coordinator = coordinator or SceneCoordinator()
        self.critique = CritiqueAgent()
        self.lighting = LightingAgent()
        self.materials = MaterialsAgent()
        self.composition = CompositionAgent()

    # ── fitness evaluation ────────────────────────────────────────────────────

    def _evaluate(self, individual: Individual) -> float:
        """
        Build a scene for this individual, apply its gene traits, score it.
        Returns the quality score (0–100).
        """
        state = OrchestrationState(
            prompt=individual.prompt,
            focus_areas=["lighting", "materials", "composition", "critique"],
        )

        # Apply gene traits
        try:
            self.lighting.run(state, mood=individual.lighting_mood)
        except Exception as exc:
            log.debug("[Tournament] Lighting pass failed: %s", exc)

        try:
            self.materials.run(state, style=individual.materials_style)
        except Exception as exc:
            log.debug("[Tournament] Materials pass failed: %s", exc)

        try:
            self.composition.run(state, mood=individual.composition_mood)
        except Exception as exc:
            log.debug("[Tournament] Composition pass failed: %s", exc)

        # Score
        try:
            critique_result = self.critique.run(state)
            score = state.quality_score or critique_result.details.get("quality_score", 60)
        except Exception as exc:
            log.debug("[Tournament] Critique failed: %s", exc)
            score = 60.0

        individual.score = float(score)
        individual.history = state.history
        return individual.score

    def _initial_traits(self, seed: int) -> tuple[str, str, str]:
        """Assign random initial traits based on seed."""
        rng = random.Random(seed)
        return (
            rng.choice(_LIGHTING_MOODS),
            rng.choice(_MATERIAL_STYLES),
            rng.choice(_COMPOSITION_MOODS),
        )

    # ── main tournament loop ──────────────────────────────────────────────────

    def run_tournament(
        self,
        prompt: str,
        population: int = 3,
        generations: int = 3,
        seeds: list[int] | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Run a full genetic-algorithm tournament.

        Parameters
        ----------
        prompt      : The scene description to optimise.
        population  : Number of candidates per generation (default 3).
        generations : Number of evolution cycles (default 3).
        seeds       : Optional fixed seed list for reproducibility.
        job_id      : Optional job ID for progress tracking.

        Returns
        -------
        dict with winner, all_individuals, lineage, generation_scores, total_time_s.
        """
        started = time.perf_counter()
        population = max(2, min(population, 6))
        generations = max(1, min(generations, 5))

        log.info(
            "[Tournament] Starting: prompt=%s, pop=%d, gen=%d",
            prompt[:60], population, generations,
        )

        if seeds is None:
            rng = random.Random(hash(prompt) & 0xFFFF)
            seeds = [rng.randint(1, 9999) for _ in range(population)]
        seeds = seeds[:population]

        all_individuals: list[Individual] = []
        generation_scores: list[dict[str, Any]] = []

        # ── Generation 0: initial population ─────────────────────────────────
        current_pop: list[Individual] = []
        for i, seed in enumerate(seeds):
            ind = Individual(prompt=prompt, seed=seed, generation=0)
            ind.lighting_mood, ind.materials_style, ind.composition_mood = self._initial_traits(seed)
            current_pop.append(ind)

        _progress_step = 100.0 / (generations * population + 1)
        _progress = 0.0

        for gen in range(generations):
            log.info("[Tournament] === Generation %d ===", gen)
            gen_results: list[dict[str, Any]] = []

            for ind in current_pop:
                log.info("[Tournament] Evaluating seed=%d gen=%d", ind.seed, gen)
                score = self._evaluate(ind)
                gen_results.append({"seed": ind.seed, "score": round(score, 1)})
                all_individuals.append(ind)
                _progress += _progress_step
                if job_id:
                    job_tracker.set_job_progress(
                        job_id, _progress,
                        f"Gen {gen + 1}/{generations}: seed={ind.seed} → score {round(score, 1)}"
                    )

            generation_scores.append({"generation": gen, "results": gen_results})
            current_pop.sort(key=lambda x: x.score, reverse=True)
            best = current_pop[0]
            log.info(
                "[Tournament] Gen %d best: seed=%d score=%.1f",
                gen, best.seed, best.score,
            )

            # ── Crossbreed for next generation (except last) ──────────────────
            if gen < generations - 1:
                parent1, parent2 = current_pop[0], current_pop[1]
                child = _crossbreed(parent1, parent2, gen + 1)
                # Replace worst individual with child
                current_pop[-1] = child

        # ── Pick overall winner ───────────────────────────────────────────────
        winner = max(all_individuals, key=lambda x: x.score)

        # Record in CritiqueAgent's self-learning memory
        try:
            techniques = [winner.lighting_mood, winner.materials_style, winner.composition_mood]
            self.critique.learn_from_success(winner.score, techniques)
        except Exception:
            pass

        total_time = round(time.perf_counter() - started, 1)
        log.info(
            "[Tournament] Complete. Winner: seed=%d score=%.1f in %.1fs",
            winner.seed, winner.score, total_time,
        )

        return {
            "ok": True,
            "prompt": prompt,
            "winner": winner.as_dict(),
            "winner_score": round(winner.score, 1),
            "all_individuals": [ind.as_dict() for ind in all_individuals],
            "generation_scores": generation_scores,
            "total_time_s": total_time,
            "total_candidates_evaluated": len(all_individuals),
            "summary": (
                f"Tournament complete ({len(all_individuals)} candidates, "
                f"{generations} generations). "
                f"Best score: {round(winner.score, 1)}/100 "
                f"(seed={winner.seed}, lighting={winner.lighting_mood}, "
                f"materials={winner.materials_style})."
            ),
        }

    def run_tournament_as_job(
        self,
        prompt: str,
        population: int = 3,
        generations: int = 3,
        seeds: list[int] | None = None,
    ) -> dict[str, Any]:
        """Run the tournament as a tracked job with progress updates."""
        j = job_tracker.create_job("tournament", "scene_tournament", {
            "prompt": prompt,
            "population": population,
            "generations": generations,
        })
        job_tracker.update_job(j["job_id"], state="running", status_message="Tournament starting...")

        try:
            result = self.run_tournament(
                prompt=prompt,
                population=population,
                generations=generations,
                seeds=seeds,
                job_id=j["job_id"],
            )
            job_tracker.finish_job(j["job_id"], result=result)
            return {**result, "job_id": j["job_id"]}
        except Exception as exc:
            job_tracker.finish_job(j["job_id"], error=str(exc))
            return {"ok": False, "error": str(exc), "job_id": j["job_id"]}
