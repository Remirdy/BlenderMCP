"""Natural-language prompt -> scene plan classification.

Lightweight keyword intent parser. It is intentionally transparent and
deterministic so the AI client can predict and refine results.
"""
from __future__ import annotations

import re

GAME_WORDS = ("game", "isometric", "mobile", "low poly", "low-poly", "stylized", "cartoon",
              "sci-fi", "sci fi", "scifi", "corridor", "cyberpunk", "dungeon", "level", "unity", "unreal", "modular")
ARCH_WORDS = ("villa", "house", "exterior", "facade", "building", "apartment block", "architectural", "roof", "garden", "pool")
INTERIOR_WORDS = ("interior", "living room", "bedroom", "kitchen", "office", "cafe", "apartment", "furniture", "sofa", "room")
PRODUCT_WORDS = ("product", "studio", "device", "packshot", "turntable", "showcase")
CINEMATIC_WORDS = ("cinematic", "dramatic", "film", "volumetric", "fog", "hero shot")

ROOM_WORDS = {
    "living room": "living_room", "bedroom": "bedroom", "kitchen": "kitchen",
    "office": "office", "cafe": "cafe", "apartment": "apartment",
}


def _hits(text, words):
    return sum(1 for w in words if w in text)


def classify(prompt: str) -> dict:
    text = prompt.lower()
    scores = {
        "product_render": _hits(text, PRODUCT_WORDS) * 2,
        "cinematic": _hits(text, CINEMATIC_WORDS) * 2,
        "interior_design": _hits(text, INTERIOR_WORDS),
        "architectural_exterior": _hits(text, ARCH_WORDS),
        "game_environment": _hits(text, GAME_WORDS),
    }
    # exterior keywords beat generic interior when 'exterior'/'villa' present
    kind = max(scores, key=scores.get)
    if max(scores.values()) == 0:
        kind = "game_environment"

    plan = {"kind": kind, "scores": scores}

    if kind == "interior_design":
        room = next((v for k, v in ROOM_WORDS.items() if k in text), "living_room")
        plan["room"] = room
        plan["warm_lighting"] = "warm" in text or "cozy" in text
        plan["style"] = "minimalist_interior" if "minimal" in text else "luxury_apartment"
    elif kind == "game_environment":
        if "sci" in text or "corridor" in text or "cyberpunk" in text:
            plan["style"] = "sci_fi_game_level"
        elif "low poly" in text or "low-poly" in text:
            plan["style"] = "low_poly"
        else:
            plan["style"] = "mobile_stylized"
        plan["theme"] = "campus" if "campus" in text else (
            "medieval_village" if "medieval" in text or "village" in text else "campus")
        plan["isometric_camera"] = "isometric" in text
    elif kind == "architectural_exterior":
        plan["preset"] = "modern_villa"
        m = re.search(r"(\d+)\s*(floor|stor)", text)
        plan["floors"] = int(m.group(1)) if m else 2
        plan["pool"] = "pool" in text
    elif kind == "product_render":
        plan["background"] = "matte_black" if "dark" in text or "black" in text else "studio_white"
    elif kind == "cinematic":
        plan["mood"] = "dramatic"

    # export intent
    if "unity" in text or "glb" in text:
        plan["export"] = {"format": "glb", "target": "unity" if "unity" in text else "generic"}
    elif "unreal" in text or "fbx" in text:
        plan["export"] = {"format": "fbx", "target": "unreal" if "unreal" in text else "generic"}
    return plan
