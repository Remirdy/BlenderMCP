"""
Multi-LLM Orchestration — Parallel Claude + ChatGPT + Gemini.

Sends the same scene-planning prompt to multiple LLMs simultaneously,
collects their structured responses, then uses CritiqueAgent logic to
select the best scene plan.

Supported backends
------------------
  claude   — Anthropic API (ANTHROPIC_API_KEY)
  openai   — OpenAI API (OPENAI_API_KEY)
  gemini   — Google Gemini API (GEMINI_API_KEY)
  chatgpt  — ChatGPT web via browser automation (no API key, session required)

Strategy options
----------------
  "best"     — Run all, CritiqueAgent scores each scene plan, return winner.
  "fastest"  — Return whichever responds first (race mode).
  "consensus"— All must agree on key elements; merge their outputs.
  "ensemble" — Return all responses for the caller to compare.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import time
from typing import Any

from ..utils.logging_utils import get_logger

log = get_logger("remirdy.multi_llm")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY", "")
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_GEMINI_API_KEY", "")


# ── individual LLM callers ────────────────────────────────────────────────────

SCENE_PLAN_SCHEMA = (
    "Return ONLY a JSON object with these fields: "
    "objects (array of {name, type, position_3d:{x,y,z}, material, scale}), "
    "lighting ({style, temperature_kelvin, direction}), "
    "camera ({angle, focal_length}), "
    "mood (string), "
    "color_palette (array of hex strings), "
    "environment ({sky, ground}), "
    "suggested_blender_tools (array of tool name strings)."
)


def _parse_json_safe(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON block
        import re
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return None


def _call_claude(prompt: str, scene_description: str) -> dict[str, Any]:
    """Call Anthropic Claude API."""
    if not ANTHROPIC_API_KEY:
        return {"ok": False, "provider": "claude", "error": "ANTHROPIC_API_KEY not set"}
    try:
        import urllib.request
        payload = json.dumps({
            "model": "claude-opus-4-6",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": f"{prompt}\n\nScene: {scene_description}"}],
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        text = data["content"][0]["text"] if data.get("content") else ""
        plan = _parse_json_safe(text)
        return {"ok": True, "provider": "claude", "raw": text, "plan": plan}
    except Exception as exc:
        return {"ok": False, "provider": "claude", "error": str(exc)}


def _call_openai(prompt: str, scene_description: str) -> dict[str, Any]:
    """Call OpenAI GPT-4 API."""
    if not OPENAI_API_KEY:
        return {"ok": False, "provider": "openai", "error": "OPENAI_API_KEY not set"}
    try:
        import urllib.request
        payload = json.dumps({
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are a professional 3D scene planning AI for Blender."},
                {"role": "user", "content": f"{prompt}\n\nScene: {scene_description}"},
            ],
            "max_tokens": 1024,
            "response_format": {"type": "json_object"},
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        text = data["choices"][0]["message"]["content"] if data.get("choices") else ""
        plan = _parse_json_safe(text)
        return {"ok": True, "provider": "openai", "raw": text, "plan": plan}
    except Exception as exc:
        return {"ok": False, "provider": "openai", "error": str(exc)}


def _call_gemini(prompt: str, scene_description: str) -> dict[str, Any]:
    """Call Google Gemini API."""
    if not GEMINI_API_KEY:
        return {"ok": False, "provider": "gemini", "error": "GEMINI_API_KEY not set"}
    try:
        from google import genai  # type: ignore[import-untyped]
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[f"{prompt}\n\nScene: {scene_description}"],
            config=types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json",
            ),
        )
        text = resp.text or ""
        plan = _parse_json_safe(text)
        return {"ok": True, "provider": "gemini", "raw": text, "plan": plan}
    except Exception as exc:
        return {"ok": False, "provider": "gemini", "error": str(exc)}


def _call_chatgpt_browser(scene_description: str) -> dict[str, Any]:
    """Call ChatGPT via browser automation (no API key needed)."""
    try:
        from ..utils.browser_automation import chatgpt_plan_scene, run_async, has_session
        if not has_session("chatgpt"):
            return {"ok": False, "provider": "chatgpt_browser", "error": "No ChatGPT browser session. Call open_browser_session('chatgpt') first."}
        result = run_async(chatgpt_plan_scene(scene_description))
        plan = _parse_json_safe(result.get("response_text", ""))
        return {"ok": result.get("ok", False), "provider": "chatgpt_browser", "raw": result.get("response_text"), "plan": plan}
    except Exception as exc:
        return {"ok": False, "provider": "chatgpt_browser", "error": str(exc)}


# ── provider registry ─────────────────────────────────────────────────────────

PROVIDERS: dict[str, Any] = {
    "claude":         _call_claude,
    "openai":         _call_openai,
    "gemini":         _call_gemini,
    "chatgpt_browser": lambda p, s: _call_chatgpt_browser(s),
}


def available_providers() -> list[str]:
    avail = []
    if ANTHROPIC_API_KEY: avail.append("claude")
    if OPENAI_API_KEY:    avail.append("openai")
    if GEMINI_API_KEY:    avail.append("gemini")
    try:
        from ..utils.browser_automation import has_session
        if has_session("chatgpt"): avail.append("chatgpt_browser")
    except Exception:
        pass
    return avail


# ── scene plan scorer (heuristic) ─────────────────────────────────────────────

def _score_plan(plan: dict | None) -> float:
    """Heuristically score a scene plan dict. Higher = more useful."""
    if not plan or not isinstance(plan, dict):
        return 0.0
    score = 0.0
    if isinstance(plan.get("objects"), list) and plan["objects"]:
        score += min(len(plan["objects"]) * 5, 40)
    if plan.get("lighting"):
        score += 15
    if plan.get("camera"):
        score += 10
    if plan.get("mood"):
        score += 5
    if isinstance(plan.get("color_palette"), list):
        score += min(len(plan["color_palette"]) * 2, 10)
    if isinstance(plan.get("suggested_blender_tools"), list):
        score += min(len(plan["suggested_blender_tools"]) * 3, 15)
    if plan.get("environment"):
        score += 5
    return score


# ── main orchestration ────────────────────────────────────────────────────────

def orchestrate_llms(
    scene_description: str,
    providers: list[str] | None = None,
    strategy: str = "best",
    timeout_s: float = 45.0,
) -> dict[str, Any]:
    """
    Send the same scene-planning prompt to multiple LLMs in parallel.

    Parameters
    ----------
    scene_description : Natural language scene description.
    providers         : Which providers to call. None = all available.
    strategy          : "best" | "fastest" | "ensemble"
    timeout_s         : Max wait per provider (default 45s).

    Returns
    -------
    dict with winner (best strategy), all_responses, scores, provider_status.
    """
    prompt = (
        "You are a professional 3D scene planning assistant for Blender. "
        "Given this scene description, generate a structured scene plan. "
        + SCENE_PLAN_SCHEMA
    )

    selected = providers or available_providers()
    if not selected:
        return {"ok": False, "error": "No LLM providers configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY."}

    log.info("[MultiLLM] Calling providers in parallel: %s (strategy=%s)", selected, strategy)
    started = time.perf_counter()

    results: dict[str, dict] = {}

    if strategy == "fastest":
        # Race: return first successful response
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(selected)) as ex:
            futures = {ex.submit(PROVIDERS[p], prompt, scene_description): p for p in selected if p in PROVIDERS}
            for fut in concurrent.futures.as_completed(futures, timeout=timeout_s):
                pname = futures[fut]
                try:
                    res = fut.result()
                    results[pname] = res
                    if res.get("ok") and res.get("plan"):
                        # Cancel remaining
                        for f in futures:
                            f.cancel()
                        break
                except Exception as exc:
                    results[pname] = {"ok": False, "provider": pname, "error": str(exc)}
    else:
        # All providers in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(selected)) as ex:
            futures = {ex.submit(PROVIDERS[p], prompt, scene_description): p for p in selected if p in PROVIDERS}
            for fut in concurrent.futures.as_completed(futures, timeout=timeout_s):
                pname = futures[fut]
                try:
                    results[pname] = fut.result()
                except Exception as exc:
                    results[pname] = {"ok": False, "provider": pname, "error": str(exc)}

    total_time = round(time.perf_counter() - started, 2)

    # Score each result
    scored = {p: _score_plan(r.get("plan")) for p, r in results.items()}
    successful = {p: r for p, r in results.items() if r.get("ok") and r.get("plan")}

    winner_provider = None
    winner_plan = None
    if successful:
        winner_provider = max(scored, key=scored.get) if strategy != "fastest" else next(iter(successful))
        winner_plan = results[winner_provider].get("plan")

    return {
        "ok": bool(successful),
        "strategy": strategy,
        "providers_called": selected,
        "providers_succeeded": list(successful.keys()),
        "scores": {p: round(s, 1) for p, s in scored.items()},
        "winner_provider": winner_provider,
        "winner_plan": winner_plan,
        "all_responses": {
            p: {"ok": r.get("ok"), "plan": r.get("plan"), "error": r.get("error")}
            for p, r in results.items()
        },
        "total_time_s": total_time,
        "summary": (
            f"Asked {len(selected)} LLMs, {len(successful)} succeeded in {total_time}s. "
            f"Winner: {winner_provider} (score={round(scored.get(winner_provider, 0), 1)}/100)."
        ) if successful else "All LLM providers failed or timed out.",
    }
