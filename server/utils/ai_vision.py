"""AI vision integration for scene analysis and object extraction.

Uses the MCP host model when a client supports sampling, or Google Gemini
2.5-flash when API credentials are configured. Both paths return structured
scene descriptions that replace the naive 1×1-pixel colour-sampling approach.

Environment variables
---------------------
GEMINI_API_KEY or GOOGLE_GEMINI_API_KEY
    Your Google AI Studio / Vertex AI API key.  If neither is set the module
    returns ``None`` from every public function so callers can fall back to the
    existing colour-based analysis without raising an error.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

from mcp.types import ImageContent, SamplingMessage, TextContent

log = logging.getLogger("remirdy.ai_vision")

# ── model config ──────────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.5-flash"

# ── internal helpers ──────────────────────────────────────────────────────────

def _get_api_key() -> str | None:
    """Return the Gemini API key from the environment, or None."""
    return (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_GEMINI_API_KEY")
    )


def _get_client():
    """Return an initialised google-genai client, or None if unavailable."""
    api_key = _get_api_key()
    if not api_key:
        return None
    try:
        from google import genai  # type: ignore[import-untyped]
        return genai.Client(api_key=api_key)
    except ImportError:
        log.warning(
            "google-genai package is not installed. "
            "Run: pip install google-genai"
        )
        return None
    except Exception as exc:
        log.warning("Could not initialise Gemini client: %s", exc)
        return None


def _image_to_part(image_path: str):
    """Convert a local image file to a Gemini content Part."""
    from google.genai import types  # type: ignore[import-untyped]

    path = Path(image_path)
    suffix = path.suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    mime_type = mime_map.get(suffix, "image/png")
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return types.Part.from_bytes(data=base64.standard_b64decode(data), mime_type=mime_type)


def _mime_type_for_path(image_path: str) -> str:
    suffix = Path(image_path).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "image/png")


def _image_to_content(image_path: str) -> ImageContent:
    path = Path(image_path)
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return ImageContent(type="image", data=data, mimeType=_mime_type_for_path(str(path)))


def _sampling_text(result: Any) -> str | None:
    content = getattr(result, "content", None)
    if isinstance(content, list):
        texts = [getattr(part, "text", "") for part in content if getattr(part, "type", "") == "text"]
        return "\n".join(t for t in texts if t).strip() or None
    if getattr(content, "type", "") == "text":
        return getattr(content, "text", None)
    return None


def _objects_prompt() -> str:
    return (
        "Analyse this image and identify all distinct visual objects or scene elements. "
        "For each object return a JSON array where every element is an object with these fields:\n"
        "  name (snake_case identifier),\n"
        "  type (category such as vehicle, plant, building, terrain, sky, water, character, prop),\n"
        "  position_2d ([x, y] as floats 0.0-1.0, origin top-left),\n"
        "  estimated_3d ({x, y, z} in Blender world units relative to scene centre),\n"
        "  color (dominant CSS hex string),\n"
        "  material (one of: metallic_paint, foliage, stone, wood, fabric, glass, emissive, terrain, water, plastic, other),\n"
        "  scale (float 0.1-5.0 relative to a human-height reference of 1.8 m).\n"
        "Return ONLY the JSON array, no markdown, no explanation."
    )


def _layer_prompt(layer_name: str) -> str:
    return (
        f"This image is a single PSD layer named '{layer_name}'. "
        "Describe what 3D object or environment element this layer represents. "
        "Return a JSON object with:\n"
        "  object_type (str: what this is, e.g. 'sky gradient', 'character silhouette', 'building facade'),\n"
        "  description (str: 1-2 sentence plain-language description),\n"
        "  suggested_3d_role (one of: background, midground, foreground, prop, character, vfx),\n"
        "  dominant_color (CSS hex of the most prominent colour),\n"
        "  material_hint (one of: emissive, sky, terrain, foliage, stone, wood, fabric, glass, metallic, water, plastic, other),\n"
        "  scale_estimate (float 0.1-5.0 relative to human height 1.8 m).\n"
        "Return ONLY the JSON object, no markdown."
    )


def _scene_plan_prompt(layers_meta: list[dict[str, Any]] | None = None) -> str:
    layers_context = ""
    if layers_meta:
        layer_names = [l.get("name", "unknown") for l in layers_meta[:20]]
        layers_context = (
            f" The image has {len(layers_meta)} PSD layers named: "
            + ", ".join(layer_names)
            + "."
        )
    return (
        "Analyse this reference image and generate a complete 3D scene plan for Blender."
        + layers_context
        + "\nReturn a JSON object with:\n"
        "  objects: array of scene objects (each with name, type, position_2d [x,y 0-1], "
        "estimated_3d {x,y,z}, color hex, material hint, scale float),\n"
        "  scene_mood: string (e.g. warm_mediterranean, dark_fantasy, sci_fi_industrial),\n"
        "  lighting: string (golden_hour | overcast | midday | night | studio | sunset | dawn),\n"
        "  camera_angle: string (ground_level | slightly_elevated_3/4 | bird_eye | dutch_angle | front_on),\n"
        "  background_type: string (sky_hdri | solid_color | gradient | cyclorama),\n"
        "  color_palette: array of up to 6 dominant hex color strings.\n"
        "Return ONLY the JSON object, no markdown, no explanation."
    )


def _call_gemini(client, prompt: str, image_path: str | None = None) -> str | None:
    """Send a request to Gemini and return the text response, or None on failure."""
    try:
        from google.genai import types  # type: ignore[import-untyped]

        contents = []
        if image_path:
            contents.append(_image_to_part(image_path))
        contents.append(prompt)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )
        return response.text
    except Exception as exc:
        log.warning("Gemini API call failed: %s", exc)
        return None


def _parse_json_response(raw: str | None, fallback: Any = None) -> Any:
    """Attempt to parse a JSON string; return fallback on failure."""
    if not raw:
        return fallback
    # Strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        log.warning("Could not parse AI vision JSON response: %s", exc)
        return fallback


async def analyze_image_with_host_ai(ctx: Any, image_path: str, prompt: str) -> str | None:
    """Ask the MCP host/client model to analyse an image via sampling.

    This is API-keyless from the server's perspective. It only works when the
    connected MCP client implements ``sampling/createMessage`` and accepts image
    content. Unsupported clients raise internally and this function returns None.
    """
    try:
        result = await ctx.session.create_message(
            messages=[
                SamplingMessage(
                    role="user",
                    content=[
                        _image_to_content(image_path),
                        TextContent(type="text", text=prompt),
                    ],
                )
            ],
            max_tokens=3000,
            system_prompt=(
                "You are a precise computer-vision scene planner for Blender. "
                "Always return valid JSON exactly matching the requested schema."
            ),
            include_context="none",
            temperature=0.1,
            related_request_id=getattr(ctx, "request_id", None),
        )
        return _sampling_text(result)
    except Exception as exc:
        log.debug("Host AI vision sampling unavailable or failed: %s", exc)
        return None


# ── public API ────────────────────────────────────────────────────────────────

def is_available() -> bool:
    """Return True when the Gemini client can be initialised."""
    return _get_client() is not None


def analyze_image_with_gemini(image_path: str, prompt: str) -> str | None:
    """Send an image and a freeform prompt to Gemini; return the raw text response.

    Returns ``None`` when no API key is configured or the call fails.
    """
    client = _get_client()
    if client is None:
        return None
    return _call_gemini(client, prompt, image_path)


def extract_scene_objects(image_path: str) -> list[dict[str, Any]] | None:
    """Analyse an image and return a structured list of scene objects.

    Each item has the shape::

        {
            "name": str,
            "type": str,                # e.g. "vehicle", "plant", "building"
            "position_2d": [x, y],      # normalised 0–1 within the image
            "estimated_3d": {"x": float, "y": float, "z": float},
            "color": str,               # CSS hex e.g. "#4A90A4"
            "material": str,            # hint: "metallic_paint", "foliage", …
            "scale": float,             # relative size estimate
        }

    Returns ``None`` when Gemini is not available.
    """
    client = _get_client()
    if client is None:
        return None

    raw = _call_gemini(client, _objects_prompt(), image_path)
    result = _parse_json_response(raw, fallback=None)
    if isinstance(result, list):
        return result
    # Gemini sometimes wraps the array in an object
    if isinstance(result, dict):
        for key in ("objects", "elements", "items", "scene_objects"):
            if isinstance(result.get(key), list):
                return result[key]
    log.warning("extract_scene_objects: unexpected response shape")
    return None


async def extract_scene_objects_with_host_ai(ctx: Any, image_path: str) -> list[dict[str, Any]] | None:
    """Analyse an image with the connected MCP client's model, if supported."""
    raw = await analyze_image_with_host_ai(ctx, image_path, _objects_prompt())
    result = _parse_json_response(raw, fallback=None)
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for key in ("objects", "elements", "items", "scene_objects"):
            if isinstance(result.get(key), list):
                return result[key]
    return None


def analyze_psd_layer(layer_image_path: str, layer_name: str) -> dict[str, Any] | None:
    """Analyse a single PSD layer image and return a description dict.

    Returns a dict with at minimum::

        {
            "object_type": str,
            "description": str,
            "suggested_3d_role": str,   # background | midground | foreground | prop
            "dominant_color": str,      # hex
            "material_hint": str,
            "scale_estimate": float,
        }

    Returns ``None`` when Gemini is not available.
    """
    client = _get_client()
    if client is None:
        return None

    raw = _call_gemini(client, _layer_prompt(layer_name), layer_image_path)
    result = _parse_json_response(raw, fallback=None)
    if isinstance(result, dict):
        return result
    return None


async def analyze_psd_layer_with_host_ai(
    ctx: Any,
    layer_image_path: str,
    layer_name: str,
) -> dict[str, Any] | None:
    """Analyse a single PSD layer using the connected MCP client's model."""
    raw = await analyze_image_with_host_ai(ctx, layer_image_path, _layer_prompt(layer_name))
    result = _parse_json_response(raw, fallback=None)
    if isinstance(result, dict):
        return result
    return None


def generate_scene_plan(
    image_path: str, layers_meta: list[dict[str, Any]] | None = None
) -> dict[str, Any] | None:
    """Generate a complete 3D scene plan from a reference image and optional layer metadata.

    Returns a dict::

        {
            "objects": [...],           # list of scene object dicts (same shape as extract_scene_objects)
            "scene_mood": str,
            "lighting": str,            # e.g. "golden_hour", "overcast", "studio"
            "camera_angle": str,        # e.g. "slightly_elevated_3/4", "bird_eye", "ground_level"
            "background_type": str,     # e.g. "sky_hdri", "solid_color", "gradient"
            "color_palette": [str],     # list of dominant hex colors
        }

    Returns ``None`` when Gemini is not available.
    """
    client = _get_client()
    if client is None:
        return None

    raw = _call_gemini(client, _scene_plan_prompt(layers_meta), image_path)
    result = _parse_json_response(raw, fallback=None)
    if isinstance(result, dict):
        return result
    return None


async def generate_scene_plan_with_host_ai(
    ctx: Any,
    image_path: str,
    layers_meta: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Generate a complete scene plan using the connected MCP client's model."""
    raw = await analyze_image_with_host_ai(ctx, image_path, _scene_plan_prompt(layers_meta))
    result = _parse_json_response(raw, fallback=None)
    if isinstance(result, dict):
        return result
    return None


def analyze_flat_image_with_ai(image_path: str) -> dict[str, Any] | None:
    """Convenience wrapper: run a full scene plan on a flat PNG/JPEG image.

    Returns the scene plan dict or ``None`` when Gemini is unavailable.
    """
    return generate_scene_plan(image_path, layers_meta=None)


async def analyze_flat_image_with_host_ai(ctx: Any, image_path: str) -> dict[str, Any] | None:
    """Convenience wrapper for host-model scene planning on a flat image."""
    return await generate_scene_plan_with_host_ai(ctx, image_path, layers_meta=None)
