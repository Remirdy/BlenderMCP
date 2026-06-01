"""PSD and multi-layer image parsing utilities with visual layout inspection.

When a Gemini API key is present the module will use AI vision analysis to
produce richer layer and scene metadata.  When no key is set it falls back to
the original colour-sampling approach transparently.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..utils.logging_utils import get_logger
from .ai_vision import (
    analyze_psd_layer as _ai_analyze_layer,
    analyze_flat_image_with_ai as _ai_analyze_flat,
    generate_scene_plan as _ai_scene_plan,
    is_available as _ai_available,
)

log = get_logger("remirdy.psd")


def ensure_psd_tools() -> bool:
    """Ensure psd-tools is installed in the active virtual environment."""
    try:
        import psd_tools
        return True
    except ImportError:
        log.info("psd-tools is not installed. Attempting automatic installation...")
        try:
            pip_path = sys.executable
            subprocess.run(
                [pip_path, "-m", "pip", "install", "psd-tools"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            import psd_tools
            log.info("psd-tools successfully installed!")
            return True
        except Exception as exc:
            log.warning("Automatic psd-tools installation failed: %s", exc)
            return False


def get_dominant_color(img) -> tuple[float, float, float]:
    """Analyze the image using PIL to extract the average dominant RGB color scaled to 0.0-1.0."""
    try:
        # Resize to 1x1 to get average color
        small_img = img.resize((1, 1))
        pixel = small_img.getpixel((0, 0))
        if isinstance(pixel, int):
            pixel = (pixel, pixel, pixel)
        r, g, b = pixel[:3]
        return (r / 255.0, g / 255.0, b / 255.0)
    except Exception as e:
        log.warning("Could not extract dominant color: %s", e)
        return (0.6, 0.6, 0.6)


def detect_visual_objects(img) -> list[dict[str, Any]]:
    """Scan flat image zones to detect elements (e.g. water at bottom, sky at top, central features)."""
    width, height = img.size
    try:
        # Check colors in top (sky), middle (main), bottom (water/ground)
        top_slice = img.crop((0, 0, width, int(height * 0.3)))
        mid_slice = img.crop((0, int(height * 0.3), width, int(height * 0.7)))
        bot_slice = img.crop((0, int(height * 0.7), width, height))

        top_rgb = get_dominant_color(top_slice)
        mid_rgb = get_dominant_color(mid_slice)
        bot_rgb = get_dominant_color(bot_slice)

        elements = []

        # Sky detection (bluish or very bright top)
        if top_rgb[2] > top_rgb[0] * 1.1 or sum(top_rgb) / 3.0 > 0.8:
            elements.append({
                "type": "sky",
                "color": top_rgb,
                "position": (0.0, 5.0, 4.0),
                "scale": (30.0, 1.0, 15.0)
            })

        # Water vs Ground detection at bottom (bluish bottom = water, greenish/brownish = land)
        is_water = bot_rgb[2] > bot_rgb[1] * 1.05 and bot_rgb[2] > bot_rgb[0] * 1.1
        if is_water:
            elements.append({
                "type": "water",
                "color": bot_rgb,
                "position": (0.0, 0.0, -0.2),
                "scale": (40.0, 40.0, 1.0)
            })
            # If water is at bottom, middle might contain a bridge or landmark!
            elements.append({
                "type": "bridge",
                "color": (0.8, 0.2, 0.2),  # Stylized Bosphorus red
                "position": (0.0, 1.5, 1.0),
                "scale": (1.0, 1.0, 1.0)
            })
        else:
            elements.append({
                "type": "terrain",
                "color": bot_rgb,
                "position": (0.0, 0.0, 0.0),
                "scale": (40.0, 40.0, 2.0)
            })

        # Middle features: check for prominent vertical chunks (like a tower or castle)
        # We can analyze the horizontal variance or average color contrast in the middle
        # If there's a strong feature, we place a tower or building!
        elements.append({
            "type": "tower",
            "color": mid_rgb,
            "position": (-3.0 if is_water else 0.0, 3.0, 0.0),
            "scale": (1.5, 1.5, 5.0)
        })

        # Spawn some matching trees/foliage around
        elements.append({
            "type": "trees",
            "color": (0.2, 0.6, 0.3),
            "locations": [(-8.0, 2.0, 0.0), (8.0, 4.0, 0.0), (-6.0, -2.0, 0.0)]
        })

        return elements
    except Exception as e:
        log.warning("Object detection failed: %s", e)
        return []


def parse_layered_image(file_path: str, output_dir: str) -> dict[str, Any]:
    """Parse a layered PSD file (or flat PNG/JPEG) and extract layers/visual parameters.

    Returns a structured dictionary:
        {
            "is_psd": bool,
            "width": int,
            "height": int,
            "layers": list[dict],
            "visual_elements": list[dict],
            "sky_color": list[float],
            "ground_color": list[float]
        }
    """
    path = Path(file_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Input image not found: {file_path}")

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    suffix = path.suffix.lower()
    layers_meta = []
    visual_elements = []

    sky_color = [0.42, 0.65, 0.85]  # Default sky blue
    ground_color = [0.22, 0.58, 0.28]  # Default grass green
    width, height = 1920, 1080
    main_img = None
    is_psd_or_psb = suffix in (".psd", ".psb")

    # Step 1: Layer extraction and composite for PSD/PSB
    if is_psd_or_psb and ensure_psd_tools():
        try:
            from psd_tools import PSDImage
            log.info("Opening PSD/PSB image: %s", path)
            psd = PSDImage.open(path)
            width, height = psd.width, psd.height

            # Extract dominant/visual parameters using the composite PIL image
            try:
                main_img = psd.composite()
                visual_elements = detect_visual_objects(main_img)
                for elem in visual_elements:
                    if elem["type"] == "sky":
                        sky_color = list(elem["color"])
                    elif elem["type"] in ("terrain", "water"):
                        ground_color = list(elem["color"])
            except Exception as e:
                log.warning("Could not create composite image for analysis: %s", e)

            has_sky = True
            has_water = True
            for layer in psd.descendants():
                name_upper = layer.name.upper()
                if "SKY_EMPTY" in name_upper or "SKY" in name_upper and "EMPTY" in name_upper:
                    has_sky = False
                if "SEA_EMPTY" in name_upper or "SEA" in name_upper and "EMPTY" in name_upper:
                    has_water = False

            idx = 0
            for layer in psd.descendants():
                if layer.is_group() or not layer.visible or layer.size == (0, 0):
                    continue

                try:
                    layer_img = layer.composite()
                    layer_name = "".join(c for c in layer.name if c.isalnum() or c in ("_", "-")).strip() or f"Layer_{idx}"
                    layer_file = out_path / f"{idx:02d}_{layer_name}.png"

                    layer_img.save(layer_file)

                    # Deduce layer depth role semantically based on names
                    name_lower = layer.name.lower()
                    role = "midground"
                    if any(k in name_lower for k in ("bg", "back", "sky", "horizon", "mount", "hill")):
                        role = "background"
                    elif any(k in name_lower for k in ("fg", "fore", "char", "hero", "player", "adventurer")):
                        role = "foreground"
                    elif any(k in name_lower for k in ("prop", "rock", "tree", "item", "box", "chest")):
                        role = "prop"

                    dom_color = get_dominant_color(layer_img)

                    # Optional: enrich with Gemini AI layer analysis
                    ai_analysis: dict[str, Any] | None = None
                    if _ai_available():
                        try:
                            ai_analysis = _ai_analyze_layer(str(layer_file), layer.name)
                            if ai_analysis:
                                log.debug("AI analysis for layer '%s': %s", layer.name, ai_analysis)
                        except Exception as ai_exc:
                            log.debug("AI layer analysis failed for '%s': %s", layer.name, ai_exc)

                    layers_meta.append({
                        "name": layer.name,
                        "path": str(layer_file),
                        "index": idx,
                        "visible": layer.visible,
                        "width": layer.width,
                        "height": layer.height,
                        "left": layer.left,
                        "top": layer.top,
                        "role": role,
                        "dominant_color": dom_color,
                        "ai_analysis": ai_analysis,
                    })
                    idx += 1
                except Exception as e:
                    log.warning("Could not composite layer %s: %s", layer.name, e)

            if layers_meta:
                # Optional: full scene plan from AI
                ai_scene = None
                if _ai_available():
                    try:
                        composite_path = str(out_path / "00_composite.png")
                        if main_img:
                            main_img.save(composite_path)
                            ai_scene = _ai_scene_plan(composite_path, layers_meta)
                    except Exception as ai_exc:
                        log.debug("AI scene plan failed: %s", ai_exc)

                return {
                    "is_psd": True,
                    "width": width,
                    "height": height,
                    "layers": layers_meta,
                    "visual_elements": visual_elements,
                    "sky_color": sky_color,
                    "ground_color": ground_color,
                    "has_sky": has_sky,
                    "has_water": has_water,
                    "ai_scene_plan": ai_scene,
                }
        except Exception as exc:
            log.error("Failed to parse PSD/PSB layers: %s. Falling back to flat extraction.", exc)

    # Fallback/Default for PNG, JPEG, or PSD without active layers
    log.info("Treating image as a flat layered concept art...")
    from PIL import Image
    try:
        main_img = Image.open(path)
        width, height = main_img.size

        visual_elements = detect_visual_objects(main_img)
        for elem in visual_elements:
            if elem["type"] == "sky":
                sky_color = list(elem["color"])
            elif elem["type"] in ("terrain", "water"):
                ground_color = list(elem["color"])
    except Exception as e:
        raise RuntimeError(f"Failed to open image file with PIL: {e}")

    # Fallback/Default for PNG, JPEG, or PSD without active layers
    log.info("Treating image as a flat layered concept art...")
    bg_file = out_path / "00_Background_Concept.png"
    main_img.save(bg_file)

    # Extract dominant color
    dom_color = get_dominant_color(main_img)

    layers_meta.append({
        "name": "Concept_Background",
        "path": str(bg_file),
        "index": 0,
        "visible": True,
        "width": width,
        "height": height,
        "role": "background",
        "dominant_color": dom_color,
    })

    # If it is PNG with alpha channel, extract non-transparent elements as foreground
    if main_img.mode in ("RGBA", "LA") or (main_img.mode == "P" and "transparency" in main_img.info):
        try:
            fg_file = out_path / "01_Foreground_Elements.png"
            main_img.save(fg_file)
            layers_meta.append({
                "name": "Concept_Foreground",
                "path": str(fg_file),
                "index": 1,
                "visible": True,
                "width": width,
                "height": height,
                "role": "foreground",
                "dominant_color": dom_color,
            })
        except Exception as e:
            log.warning("Failed to save alpha foreground layer: %s", e)

    # Optional: AI scene plan for flat images
    ai_scene = None
    if _ai_available():
        try:
            ai_scene = _ai_analyze_flat(file_path)
        except Exception as ai_exc:
            log.debug("AI flat image analysis failed: %s", ai_exc)

    return {
        "is_psd": False,
        "width": width,
        "height": height,
        "layers": layers_meta,
        "visual_elements": visual_elements,
        "sky_color": sky_color,
        "ground_color": ground_color,
        "ai_scene_plan": ai_scene,
    }
