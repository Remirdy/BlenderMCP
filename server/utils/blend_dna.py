"""
.blend DNA — Style Fingerprint Extractor.

Analyses the currently open Blender scene (via the bridge) and extracts a
"style DNA" dict that captures its aesthetic identity: palette, lighting,
materials, camera, geometry density, mood.

This DNA can then drive a "sequel scene" — a new scene that's in the same
fictional universe but a different location / time.
"""
from __future__ import annotations

import json
import math
from typing import Any

from ..utils.logging_utils import get_logger

log = get_logger("remirdy.blend_dna")


# ── DNA schema ────────────────────────────────────────────────────────────────

EMPTY_DNA: dict[str, Any] = {
    "color_palette": [],          # list of hex strings from dominant materials
    "avg_roughness": 0.5,
    "avg_metallic": 0.0,
    "material_style": "unknown",  # metallic | organic | stone | stylized | mixed
    "light_temperature": 5500,    # Kelvin estimate
    "light_style": "unknown",     # cinematic | golden_hour | overcast | studio | neon
    "camera_focal_length": 50,
    "camera_angle": "unknown",    # eye_level | elevated | bird_eye | dutch
    "avg_polycount": 0,
    "geometry_density": "medium", # sparse | medium | dense | ultra
    "dominant_scale": 1.0,        # avg object scale
    "scene_mood": "unknown",      # dark | bright | warm | cold | neutral
    "object_count": 0,
    "has_characters": False,
    "has_terrain": False,
    "has_water": False,
    "has_vegetation": False,
    "collections": [],
    "era_hint": "contemporary",   # medieval | sci_fi | contemporary | fantasy | post_apocalyptic
    "raw_graph": {},
}


# ── bridge-based extraction ───────────────────────────────────────────────────

def extract_dna_from_bridge() -> dict[str, Any]:
    """
    Extract style DNA from the currently open Blender scene via the bridge.
    Calls get_scene_graph and analyze_scene_visuals, then distils into DNA.
    """
    try:
        from ..tools._common import call
    except ImportError:
        return {**EMPTY_DNA, "error": "bridge not available"}

    dna = dict(EMPTY_DNA)

    # 1. Scene graph
    graph_result = call("get_scene_graph", {})
    if not graph_result.get("ok"):
        return {**EMPTY_DNA, "error": "Could not read scene graph from Blender bridge"}

    graph = graph_result.get("result") or graph_result
    objects = graph.get("objects", [])
    dna["raw_graph"] = {
        "object_count": len(objects),
        "collections": [c["name"] for c in graph.get("collections", [])],
    }
    dna["object_count"] = len(objects)
    dna["collections"] = [c["name"] for c in graph.get("collections", [])]

    mesh_objects = [o for o in objects if o.get("type") == "MESH"]
    light_objects = [o for o in objects if o.get("type") == "LIGHT"]
    camera_objects = [o for o in objects if o.get("type") == "CAMERA"]

    # Geometry density
    polycounts = [o.get("polygons", 0) for o in mesh_objects if o.get("polygons")]
    if polycounts:
        avg_poly = sum(polycounts) / len(polycounts)
        dna["avg_polycount"] = int(avg_poly)
        if avg_poly < 500:
            dna["geometry_density"] = "sparse"
        elif avg_poly < 5000:
            dna["geometry_density"] = "medium"
        elif avg_poly < 30000:
            dna["geometry_density"] = "dense"
        else:
            dna["geometry_density"] = "ultra"

    # Scale
    scales = [
        sum(o.get("scale", [1, 1, 1])) / 3
        for o in mesh_objects
        if o.get("scale")
    ]
    if scales:
        dna["dominant_scale"] = round(sum(scales) / len(scales), 2)

    # Object name heuristics
    names_lower = [o.get("name", "").lower() for o in objects]
    dna["has_characters"] = any(
        k in n for n in names_lower
        for k in ("chr_", "character", "player", "npc", "humanoid", "armature")
    )
    dna["has_terrain"] = any(
        k in n for n in names_lower
        for k in ("terrain", "ground", "landscape", "heightmap", "earth")
    )
    dna["has_water"] = any(
        k in n for n in names_lower
        for k in ("water", "ocean", "lake", "river", "sea")
    )
    dna["has_vegetation"] = any(
        k in n for n in names_lower
        for k in ("tree", "bush", "grass", "foliage", "plant", "forest")
    )

    # Camera analysis
    if camera_objects:
        cam = camera_objects[0]
        loc = cam.get("location", [0, 0, 0])
        z = loc[2] if len(loc) > 2 else 0
        if z > 20:
            dna["camera_angle"] = "bird_eye"
        elif z > 5:
            dna["camera_angle"] = "elevated"
        elif z < 0:
            dna["camera_angle"] = "worm_eye"
        else:
            dna["camera_angle"] = "eye_level"

    # Material style via name heuristics
    mat_names_lower = []
    for o in mesh_objects:
        mat_names_lower.extend([m.lower() for m in o.get("materials", [])])

    metal_count = sum(1 for m in mat_names_lower if any(k in m for k in ("metal", "steel", "chrome", "iron")))
    organic_count = sum(1 for m in mat_names_lower if any(k in m for k in ("wood", "fabric", "leather", "grass", "soil")))
    stone_count = sum(1 for m in mat_names_lower if any(k in m for k in ("stone", "concrete", "brick", "rock", "marble")))
    stylized_count = sum(1 for m in mat_names_lower if any(k in m for k in ("stylized", "cartoon", "low_poly", "flat")))

    dominant_type = max(
        [("metallic", metal_count), ("organic", organic_count),
         ("stone", stone_count), ("stylized", stylized_count)],
        key=lambda x: x[1],
    )
    dna["material_style"] = dominant_type[0] if dominant_type[1] > 0 else "mixed"

    # Light style from light count + names
    if light_objects:
        light_names = [o.get("name", "").lower() for o in light_objects]
        if any("sun" in n or "env" in n for n in light_names):
            dna["light_style"] = "golden_hour"
        elif any("spot" in n for n in light_names) and len(light_objects) >= 3:
            dna["light_style"] = "studio"
        elif len(light_objects) == 1:
            dna["light_style"] = "cinematic"
        else:
            dna["light_style"] = "balanced"

    # Era hint from collection / object names
    all_names = " ".join(names_lower)
    if any(k in all_names for k in ("medieval", "castle", "sword", "knight", "dungeon")):
        dna["era_hint"] = "medieval"
    elif any(k in all_names for k in ("sci_fi", "scifi", "cyberpunk", "neon", "corridor", "tech")):
        dna["era_hint"] = "sci_fi"
    elif any(k in all_names for k in ("ruin", "abandon", "decay", "post_apocalyptic", "wasteland")):
        dna["era_hint"] = "post_apocalyptic"
    elif any(k in all_names for k in ("fantasy", "dragon", "magic", "crystal", "elf", "dwarf")):
        dna["era_hint"] = "fantasy"
    else:
        dna["era_hint"] = "contemporary"

    # 2. Visual snapshot for mood / palette
    try:
        vis_result = call("analyze_scene_visuals", {"view": "camera"})
        if vis_result.get("ok"):
            vis = vis_result.get("result") or vis_result
            screenshot = vis.get("screenshot", {})
            screenshot_path = screenshot.get("screenshot_path") if isinstance(screenshot, dict) else None

            if screenshot_path:
                _enrich_from_screenshot(dna, screenshot_path)
    except Exception as exc:
        log.debug("Visual enrichment failed: %s", exc)

    # Mood from light + material
    _infer_mood(dna)

    log.info(
        "[DNA] Extracted: era=%s style=%s light=%s density=%s mood=%s",
        dna["era_hint"], dna["material_style"], dna["light_style"],
        dna["geometry_density"], dna["scene_mood"],
    )
    return dna


def _enrich_from_screenshot(dna: dict[str, Any], screenshot_path: str) -> None:
    """Extract colour palette and temperature from a screenshot using Pillow."""
    try:
        from PIL import Image
        import colorsys

        img = Image.open(screenshot_path).convert("RGB")
        img_small = img.resize((64, 64))
        pixels = list(img_small.getdata())

        # Average colour
        avg_r = sum(p[0] for p in pixels) / len(pixels)
        avg_g = sum(p[1] for p in pixels) / len(pixels)
        avg_b = sum(p[2] for p in pixels) / len(pixels)

        # Dominant palette: cluster into 5 buckets by hue
        hues: dict[int, list] = {}
        for r, g, b in pixels:
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            bucket = int(h * 5)
            hues.setdefault(bucket, []).append((r, g, b))

        palette = []
        for bucket in sorted(hues, key=lambda k: len(hues[k]), reverse=True)[:5]:
            group = hues[bucket]
            mr = int(sum(p[0] for p in group) / len(group))
            mg = int(sum(p[1] for p in group) / len(group))
            mb = int(sum(p[2] for p in group) / len(group))
            palette.append(f"#{mr:02X}{mg:02X}{mb:02X}")

        dna["color_palette"] = palette

        # Rough colour temperature estimate
        if avg_r > avg_b * 1.2:
            dna["light_temperature"] = 3200  # warm
            dna["scene_mood"] = "warm"
        elif avg_b > avg_r * 1.15:
            dna["light_temperature"] = 7500  # cool
            dna["scene_mood"] = "cold"
        else:
            dna["light_temperature"] = 5500
    except Exception as exc:
        log.debug("Colour extraction from screenshot failed: %s", exc)


def _infer_mood(dna: dict[str, Any]) -> None:
    if dna["scene_mood"] != "unknown":
        return
    light = dna.get("light_style", "")
    era = dna.get("era_hint", "")
    mat = dna.get("material_style", "")

    if light in ("golden_hour",) or era == "fantasy":
        dna["scene_mood"] = "warm"
    elif era in ("sci_fi", "post_apocalyptic"):
        dna["scene_mood"] = "cold"
    elif mat == "metallic":
        dna["scene_mood"] = "neutral"
    elif light == "cinematic":
        dna["scene_mood"] = "dark"
    else:
        dna["scene_mood"] = "neutral"


# ── sequel scene prompt builder ───────────────────────────────────────────────

def dna_to_sequel_prompt(dna: dict[str, Any], original_prompt: str = "") -> str:
    """
    Build a natural-language prompt for a "sequel scene" derived from a DNA dict.

    The sequel is in the same universe (era, style, mood) but a different
    location and situation.
    """
    era_map = {
        "medieval": "in a medieval world",
        "sci_fi": "in a sci-fi / cyberpunk setting",
        "fantasy": "in a high-fantasy world",
        "post_apocalyptic": "in a post-apocalyptic wasteland",
        "contemporary": "in a contemporary / modern setting",
    }
    light_map = {
        "golden_hour": "at golden hour with warm light",
        "cinematic": "with dramatic cinematic lighting",
        "studio": "under controlled studio lighting",
        "overcast": "under overcast grey skies",
        "neon": "lit by neon signs and artificial light",
        "balanced": "with balanced natural lighting",
    }
    density_map = {
        "sparse": "minimalist, few objects",
        "medium": "moderately detailed",
        "dense": "richly detailed",
        "ultra": "extremely detailed",
    }

    era_phrase = era_map.get(dna.get("era_hint", "contemporary"), "")
    light_phrase = light_map.get(dna.get("light_style", "balanced"), "")
    density_phrase = density_map.get(dna.get("geometry_density", "medium"), "")
    mood = dna.get("scene_mood", "neutral")
    mat_style = dna.get("material_style", "mixed")

    location_variants = {
        "medieval": ["a village market square", "a forest clearing near a ruined tower",
                     "a cliff-side fortress overlooking a valley", "a tavern interior"],
        "sci_fi": ["a neon-lit back alley", "a space station observation deck",
                   "a server farm deep underground", "a megacity rooftop"],
        "fantasy": ["a dragon's mountain lair", "an enchanted forest glade",
                    "a floating island temple", "an underground crystal cavern"],
        "post_apocalyptic": ["a rusted highway overpass", "a collapsed skyscraper interior",
                              "an overgrown stadium", "a survivor's underground bunker"],
        "contemporary": ["a rooftop terrace at night", "a foggy industrial port",
                         "a quiet suburban street at dusk", "a glass office atrium"],
    }
    import random
    rng = random.Random(hash(original_prompt) & 0xFFFF)
    era = dna.get("era_hint", "contemporary")
    new_location = rng.choice(location_variants.get(era, location_variants["contemporary"]))

    parts = [
        f"A {density_phrase} scene set {era_phrase},",
        f"located at {new_location}.",
        f"Lighting: {light_phrase}.",
        f"Overall mood: {mood}.",
        f"Material style: {mat_style}.",
    ]
    if dna.get("has_characters"):
        parts.append("Include at least one character appropriate to the setting.")
    if dna.get("has_vegetation"):
        parts.append("Include natural vegetation consistent with the biome.")

    return " ".join(parts)
