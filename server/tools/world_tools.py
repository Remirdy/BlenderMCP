"""
Procedural Narrative World — create_world()

Single command that coordinates terrain, city, weather, characters, lighting,
multi-agent polish, and lore generation into a complete, coherent world.

Example
-------
    create_world("fallen empire, 300 years after collapse, dark fantasy")
    create_world("neon cyberpunk mega-city during a thunderstorm", location="Tokyo")
    create_world("peaceful mediterranean fishing village at golden hour", size_km=2.0)
"""
from __future__ import annotations

import re
import time
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..agents.coordinator import SceneCoordinator
from ..utils import jobs as job_tracker
from ..utils.logging_utils import get_logger
from ..tools._common import call

log = get_logger("remirdy.world_tools")


# ── Narrative parser ──────────────────────────────────────────────────────────

_ERA_KEYWORDS = {
    "medieval":         ["medieval", "castle", "knight", "dungeon", "feudal", "kingdom"],
    "sci_fi":           ["sci-fi", "scifi", "cyberpunk", "neon", "futuristic", "space", "android"],
    "fantasy":          ["fantasy", "dragon", "magic", "elf", "dwarf", "crystal", "enchanted"],
    "post_apocalyptic": ["post-apocalyptic", "post apocalyptic", "ruins", "collapsed", "wasteland",
                         "fallout", "decay", "abandoned", "collapse"],
    "ancient":          ["ancient", "roman", "greek", "egyptian", "mesopotamian", "aztec"],
    "contemporary":     ["modern", "urban", "city", "town", "contemporary", "suburb"],
}

_MOOD_KEYWORDS = {
    "dark":    ["dark", "grim", "sinister", "horror", "haunted", "forsaken", "cursed", "dead"],
    "bright":  ["bright", "cheerful", "peaceful", "serene", "paradise", "heaven", "spring"],
    "warm":    ["warm", "golden", "cozy", "mediterranean", "tropical", "summer", "afternoon"],
    "cold":    ["cold", "winter", "frozen", "snow", "ice", "blizzard", "arctic", "steel"],
    "epic":    ["epic", "dramatic", "cinematic", "grand", "majestic", "imposing", "massive"],
    "neutral": [],
}

_WEATHER_KEYWORDS = {
    "stormy":   ["storm", "thunder", "lightning", "hurricane", "typhoon"],
    "rainy":    ["rain", "drizzle", "wet", "flood"],
    "snowy":    ["snow", "blizzard", "frozen", "ice", "winter"],
    "foggy":    ["fog", "mist", "haze", "murky"],
    "ash":      ["ash", "volcano", "apocalyptic", "collapse"],
    "clear":    ["clear", "sunny", "golden hour", "sunset", "dawn"],
    "overcast": ["overcast", "cloudy", "grey", "gray"],
}

_TIME_KEYWORDS = {
    "golden_hour": ["golden hour", "sunset", "dusk", "twilight", "evening"],
    "night":       ["night", "midnight", "dark", "neon", "stars", "moon"],
    "dawn":        ["dawn", "sunrise", "morning"],
    "midday":      ["midday", "noon", "bright", "summer day"],
    "overcast":    ["overcast", "grey", "cloudy"],
}


def _parse_narrative(prompt: str) -> dict[str, Any]:
    """Extract structured world parameters from a natural-language prompt."""
    text = prompt.lower()

    def _match(keywords: dict[str, list[str]], default: str) -> str:
        scores = {k: sum(1 for kw in kws if kw in text) for k, kws in keywords.items()}
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else default

    era = _match(_ERA_KEYWORDS, "contemporary")
    mood = _match(_MOOD_KEYWORDS, "neutral")
    weather = _match(_WEATHER_KEYWORDS, "clear")
    time_of_day = _match(_TIME_KEYWORDS, "golden_hour")

    # Settlement type
    settlement = "ruins" if era == "post_apocalyptic" else (
        "city" if era in ("sci_fi", "contemporary") else
        "village" if "village" in text or "town" in text else
        "fortress" if "castle" in text or "fortress" in text else
        "outpost"
    )

    # Character count hint
    has_npc = any(k in text for k in ("people", "crowd", "character", "npc", "soldier", "survivor"))
    npc_count = 3 if has_npc else 0

    # Size
    size_match = re.search(r"(\d+(?:\.\d+)?)\s*km", text)
    size_km = float(size_match.group(1)) if size_match else 2.0

    return {
        "era": era,
        "mood": mood,
        "weather": weather,
        "time_of_day": time_of_day,
        "settlement_type": settlement,
        "npc_count": npc_count,
        "size_km": size_km,
        "has_water": any(k in text for k in ("sea", "ocean", "lake", "river", "water", "coast", "port")),
        "has_vegetation": any(k in text for k in ("forest", "tree", "jungle", "garden", "meadow", "grass")),
        "has_snow": weather == "snowy" or "snow" in text or "frozen" in text,
    }


# ── Lore generator ────────────────────────────────────────────────────────────

def _generate_lore(narrative_prompt: str, plan: dict[str, Any]) -> dict[str, Any]:
    """Generate world lore using Gemini Vision if available, else templated text."""
    era = plan["era"]
    mood = plan["mood"]
    settlement = plan["settlement_type"]

    # Try Gemini
    try:
        from ..utils.ai_vision import is_available, analyze_image_with_gemini
        if is_available():
            lore_prompt = (
                f"Write world-building lore for a 3D game/animation scene. "
                f"Setting: {narrative_prompt}. "
                f"Return JSON with: world_name, history (2 sentences), "
                f"current_state (1 sentence), notable_locations (list of 3), "
                f"factions (list of 2 with name+description), "
                f"atmosphere_description (1 vivid sentence), "
                f"suggested_story_hook (1 sentence)."
            )
            # Text-only Gemini call (no image)
            from google import genai  # type: ignore[import-untyped]
            import os, json as _json
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_GEMINI_API_KEY")
            if api_key:
                client = genai.Client(api_key=api_key)
                from google.genai import types
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[lore_prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.8,
                        response_mime_type="application/json",
                    ),
                )
                text = resp.text.strip()
                if text.startswith("```"):
                    text = "\n".join(text.splitlines()[1:-1])
                return _json.loads(text)
    except Exception as exc:
        log.debug("Gemini lore generation failed: %s", exc)

    # Fallback: templated lore
    era_names = {
        "medieval": "The Shattered Realm",
        "sci_fi": "Nexus Grid Sector 7",
        "fantasy": "The Veiled Lands",
        "post_apocalyptic": "The Ash Fields",
        "ancient": "The Forgotten Empire",
        "contemporary": "The Forgotten District",
    }
    return {
        "world_name": era_names.get(era, "The Unknown World"),
        "history": f"This land was once a thriving {settlement}. {mood.capitalize()} times have shaped it into what it is today.",
        "current_state": f"The world stands {mood}, with traces of {era} civilization everywhere.",
        "notable_locations": [
            f"The Central {settlement.title()}",
            "The Ancient Watchtower",
            "The Hidden Sanctuary",
        ],
        "factions": [
            {"name": "The Remnants", "description": "Survivors clinging to the old ways"},
            {"name": "The New Order", "description": "Those who seek to reshape the future"},
        ],
        "atmosphere_description": f"A {mood} landscape stretches endlessly under {plan['time_of_day'].replace('_', ' ')} skies.",
        "suggested_story_hook": f"A lone traveler arrives at the {settlement} with a sealed message from a long-dead ruler.",
    }


# ── World building pipeline ───────────────────────────────────────────────────

def build_world(
    narrative_prompt: str,
    location: str | None = None,
    size_km: float | None = None,
    polish_iterations: int = 2,
    job_id: str | None = None,
) -> dict[str, Any]:
    """
    Full world-building pipeline.  Coordinates all sub-systems.
    """
    started = time.perf_counter()
    plan = _parse_narrative(narrative_prompt)
    if size_km:
        plan["size_km"] = size_km

    def _progress(pct: float, msg: str) -> None:
        if job_id:
            job_tracker.set_job_progress(job_id, pct, msg)
        log.info("[World] %.0f%% — %s", pct, msg)

    _progress(2, f"World plan parsed: era={plan['era']}, mood={plan['mood']}, weather={plan['weather']}")

    results: dict[str, Any] = {"plan": plan, "steps": {}}

    # ── Step 1: Terrain ───────────────────────────────────────────────────────
    _progress(5, "Building terrain…")
    try:
        if location:
            from .asset_source_tools import create_real_world_terrain_scene
            terrain = create_real_world_terrain_scene(
                location=location,
                radius_km=plan["size_km"],
                resolution=128,
                exaggeration=1.5 if plan["mood"] == "epic" else 1.2,
                style="stylized",
            )
        else:
            terrain = call("create_game_environment", {
                "style": _era_to_game_style(plan["era"]),
                "size": "large" if plan["size_km"] > 2 else "medium",
                "theme": _era_to_theme(plan["era"]),
                "prompt": narrative_prompt,
            })
        results["steps"]["terrain"] = terrain
        _progress(20, "Terrain ready")
    except Exception as exc:
        results["steps"]["terrain"] = {"ok": False, "error": str(exc)}
        _progress(20, f"Terrain failed: {exc}")

    # ── Step 2: Settlement ────────────────────────────────────────────────────
    _progress(22, f"Placing {plan['settlement_type']}…")
    try:
        settlement_result = call("create_procedural_city_blockout", {
            "prompt": f"{plan['era']} {plan['settlement_type']} {plan['mood']}",
            "size_km": min(plan["size_km"] * 0.4, 1.5),
            "density": "low" if plan["settlement_type"] == "ruins" else "medium",
            "style": _era_to_game_style(plan["era"]),
        })
        results["steps"]["settlement"] = settlement_result
        _progress(35, "Settlement placed")
    except Exception as exc:
        results["steps"]["settlement"] = {"ok": False, "error": str(exc)}

    # ── Step 3: Weather & atmosphere ──────────────────────────────────────────
    _progress(37, f"Setting weather: {plan['weather']}…")
    try:
        weather_result = call("spawn_weather_particles", {
            "type": "snow" if plan["has_snow"] else "rain" if plan["weather"] == "rainy" else "snow",
            "density": 200 if plan["weather"] in ("stormy", "snowy") else 80,
        }) if plan["weather"] not in ("clear",) else {"ok": True, "note": "clear weather, no particles"}
        results["steps"]["weather"] = weather_result
        _progress(42, "Weather set")
    except Exception as exc:
        results["steps"]["weather"] = {"ok": False, "error": str(exc)}

    # ── Step 4: Characters / NPCs ─────────────────────────────────────────────
    if plan["npc_count"] > 0:
        _progress(44, f"Spawning {plan['npc_count']} characters…")
        try:
            char_result = call("create_rigged_character", {
                "style": "stylized" if plan["era"] in ("fantasy", "medieval") else "realistic",
                "animation": "idle_wave",
            })
            results["steps"]["characters"] = char_result
            _progress(52, "Characters placed")
        except Exception as exc:
            results["steps"]["characters"] = {"ok": False, "error": str(exc)}

    # ── Step 5: Lighting ──────────────────────────────────────────────────────
    _progress(54, f"Setting lighting: {plan['time_of_day']}…")
    try:
        lighting_result = call("setup_cinematic_lighting", {}) if plan["mood"] in ("dark", "epic") else \
                          call("setup_archviz_lighting", {})
        results["steps"]["lighting"] = lighting_result
        _progress(60, "Lighting applied")
    except Exception as exc:
        results["steps"]["lighting"] = {"ok": False, "error": str(exc)}

    # ── Step 6: Multi-agent polish ────────────────────────────────────────────
    _progress(62, "Multi-agent polish starting…")
    try:
        coord = SceneCoordinator()
        focus = ["lighting", "materials", "critique"]
        if location:
            focus.insert(0, "composition")
        polish = coord.orchestrate(
            prompt=narrative_prompt,
            focus_areas=focus,
            max_iterations=max(1, min(polish_iterations, 3)),
            use_vision_critique=True,
        )
        results["steps"]["polish"] = polish
        final_score = polish.get("final_quality_score", 0)
        _progress(85, f"Polish complete, score={final_score}")
    except Exception as exc:
        results["steps"]["polish"] = {"ok": False, "error": str(exc)}
        final_score = 0

    # ── Step 7: Lore generation ───────────────────────────────────────────────
    _progress(87, "Generating world lore…")
    try:
        lore = _generate_lore(narrative_prompt, plan)
        results["lore"] = lore
        _progress(95, f"World '{lore.get('world_name', 'Unknown')}' lore ready")
    except Exception as exc:
        results["lore"] = {"error": str(exc)}

    # ── Finalise ──────────────────────────────────────────────────────────────
    total_time = round(time.perf_counter() - started, 1)
    _progress(100, f"World complete in {total_time}s")

    world_name = results.get("lore", {}).get("world_name", "The Unknown World")
    hook = results.get("lore", {}).get("suggested_story_hook", "")

    results.update({
        "ok": True,
        "world_name": world_name,
        "narrative_prompt": narrative_prompt,
        "location": location,
        "final_quality_score": final_score,
        "total_time_s": total_time,
        "summary": (
            f"World '{world_name}' built in {total_time}s "
            f"(era={plan['era']}, mood={plan['mood']}, score={final_score}/100). "
            f"Story hook: {hook}"
        ),
    })
    return results


def _era_to_game_style(era: str) -> str:
    return {
        "sci_fi": "sci_fi_game_level",
        "fantasy": "stylized_cartoon",
        "medieval": "low_poly",
        "post_apocalyptic": "low_poly",
        "ancient": "low_poly",
        "contemporary": "pc_game_environment",
    }.get(era, "mobile_stylized")


def _era_to_theme(era: str) -> str:
    return {
        "sci_fi": "corridor",
        "fantasy": "medieval_village",
        "medieval": "medieval_village",
        "post_apocalyptic": "campus",
        "contemporary": "campus",
    }.get(era, "campus")


# ── MCP registration ──────────────────────────────────────────────────────────

def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def create_world(
        narrative_prompt: str,
        location: str = "",
        size_km: float = 2.0,
        polish_iterations: int = 2,
    ) -> dict:
        """
        Build a complete, coherent 3D world from a single narrative description.

        Coordinates ALL sub-systems in sequence, tracked as a job:
          1. Terrain  — real elevation (if location given) or procedural
          2. Settlement — city blockout, ruins, fortress, village
          3. Weather — rain, snow, ash, fog, clear
          4. Characters — rigged NPCs placed in the world
          5. Lighting — time-of-day + mood-appropriate setup
          6. Multi-agent polish — lighting + materials + critique loop
          7. Lore — world name, history, factions, story hook (via Gemini if available)

        Args:
            narrative_prompt  : World description in plain language.
                                e.g. "fallen empire 300 years after collapse, dark fantasy"
                                     "neon cyberpunk mega-city during a thunderstorm"
                                     "peaceful mediterranean village at golden hour"
            location          : Optional real-world location for terrain
                                (e.g. "Cappadocia, Turkey", "Swiss Alps").
                                When provided, real elevation data is downloaded.
            size_km           : World radius in km (default 2.0).
            polish_iterations : Multi-agent polish cycles (1–3, default 2).

        Returns world_name, lore, quality_score, step-by-step build report,
        and a suggested story hook.
        """
        j = job_tracker.create_job("world_builder", "create_world", {
            "prompt": narrative_prompt,
            "location": location,
            "size_km": size_km,
        })
        job_tracker.update_job(j["job_id"], state="running",
                               status_message="World builder initialising…")

        try:
            result = build_world(
                narrative_prompt=narrative_prompt,
                location=location or None,
                size_km=size_km,
                polish_iterations=polish_iterations,
                job_id=j["job_id"],
            )
            job_tracker.finish_job(j["job_id"], result=result)
            return {**result, "job_id": j["job_id"]}
        except Exception as exc:
            log.exception("[create_world] Unhandled error")
            job_tracker.finish_job(j["job_id"], error=str(exc))
            return {"ok": False, "error": str(exc), "job_id": j["job_id"]}

    @mcp.tool()
    def get_world_lore(narrative_prompt: str) -> dict:
        """
        Generate world lore only — without building a 3D scene.

        Returns: world_name, history, current_state, notable_locations,
        factions, atmosphere_description, suggested_story_hook.

        Uses Gemini 2.5-flash if GEMINI_API_KEY is set, otherwise uses
        a rich templated lore system.

        Args:
            narrative_prompt: World description, e.g.
                              "ancient underwater ruins of a drowned civilization"
        """
        plan = _parse_narrative(narrative_prompt)
        lore = _generate_lore(narrative_prompt, plan)
        return {"ok": True, "narrative_prompt": narrative_prompt, "plan": plan, "lore": lore}
