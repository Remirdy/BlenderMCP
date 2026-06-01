"""
Sound Design Engine — Automatic ambient audio for 3D scenes.

Pipeline
--------
1. Analyse scene graph (era, objects, biome, weather, mood).
2. Map scene elements to a curated sound layer list.
3. Download/generate audio assets:
     • ElevenLabs   — narration / character voice (ELEVENLABS_API_KEY)
     • Freesound.org — ambient FX (FREESOUND_API_KEY)
     • Local library — bundled Creative-Commons sounds (no key needed)
4. Mix layers via FFmpeg into a single audio file.
5. Return path + embed hint for Blender VSE.

Environment variables
---------------------
ELEVENLABS_API_KEY : ElevenLabs voice synthesis
FREESOUND_API_KEY  : Freesound.org ambient FX search
FFMPEG_PATH        : Override ffmpeg executable (default "ffmpeg")
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any

from ..utils.logging_utils import get_logger

log = get_logger("remirdy.sound_design")

FFMPEG = os.environ.get("FFMPEG_PATH", "ffmpeg")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
FREESOUND_API_KEY  = os.environ.get("FREESOUND_API_KEY", "")

# ── Scene → sound mapping ─────────────────────────────────────────────────────

# Each entry: (search_query_for_freesound, local_fallback_tag, volume_db, loop)
BIOME_SOUNDS: dict[str, list[tuple[str, str, float, bool]]] = {
    "forest":         [("birds forest ambiance", "nature_birds", -6, True),
                       ("wind leaves rustling", "nature_wind", -12, True)],
    "dungeon":        [("dripping water cave", "cave_drip", -8, True),
                       ("torch crackling fire", "fire_torch", -14, True)],
    "city":           [("city traffic ambiance", "city_traffic", -6, True),
                       ("crowd chatter distant", "crowd", -14, True)],
    "medieval":       [("medieval market crowd", "crowd", -8, True),
                       ("horses hooves distant", "horses", -16, True)],
    "sci_fi":         [("spaceship hum electronic", "sci_fi_hum", -6, True),
                       ("computer beeps futuristic", "sci_fi_beep", -18, True)],
    "post_apocalyptic": [("wind howling ruins", "wind_ruins", -6, True),
                          ("distant fire crackle", "fire_distant", -14, True)],
    "ocean":          [("ocean waves beach", "ocean_waves", -4, True)],
    "mountain":       [("mountain wind cold", "wind_mountain", -8, True),
                       ("eagle cry distant", "eagle", -20, False)],
    "interior":       [("indoor ambiance quiet", "indoor_hum", -14, True)],
    "default":        [("ambient nature outdoor", "nature_ambient", -8, True)],
}

WEATHER_SOUNDS: dict[str, list[tuple[str, str, float, bool]]] = {
    "rainy":   [("heavy rain ambiance", "rain_heavy", -4, True)],
    "stormy":  [("thunderstorm heavy rain thunder", "thunderstorm", -2, True)],
    "snowy":   [("blizzard wind snow", "blizzard", -6, True)],
    "foggy":   [("eerie foghorn distant", "foghorn", -16, False)],
    "clear":   [],
    "overcast": [("wind light breeze", "wind_light", -12, True)],
}

MOOD_MUSIC: dict[str, str] = {
    "dark":    "dark ambient atmospheric drone",
    "epic":    "epic orchestral cinematic adventure",
    "warm":    "warm acoustic guitar ambient",
    "cold":    "cold atmospheric minimalist piano",
    "neutral": "ambient background subtle",
    "bright":  "cheerful light acoustic uplifting",
}


# ── Workspace ─────────────────────────────────────────────────────────────────

def _workspace(*parts: str) -> str:
    root = os.environ.get("REMIRDY_WORKSPACE", str(Path.home() / "RemirdyWorkspace"))
    out = Path(root) / "outputs" / "audio"
    out.mkdir(parents=True, exist_ok=True)
    return str(out.joinpath(*parts))


# ── Freesound download ────────────────────────────────────────────────────────

def _freesound_search(query: str, limit: int = 3) -> list[dict]:
    if not FREESOUND_API_KEY:
        return []
    try:
        q = urllib.parse.quote(query)
        url = (
            f"https://freesound.org/apiv2/search/text/"
            f"?query={q}&fields=id,name,previews&page_size={limit}"
            f"&token={FREESOUND_API_KEY}&format=json"
        )
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("results", [])
    except Exception as exc:
        log.debug("Freesound search failed: %s", exc)
        return []


def _freesound_download(sound_id: int, out_path: str) -> bool:
    if not FREESOUND_API_KEY:
        return False
    try:
        url = f"https://freesound.org/apiv2/sounds/{sound_id}/?token={FREESOUND_API_KEY}&format=json"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        preview_url = data.get("previews", {}).get("preview-hq-mp3")
        if not preview_url:
            return False
        req = urllib.request.Request(preview_url, headers={"Authorization": f"Token {FREESOUND_API_KEY}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path(out_path).write_bytes(resp.read())
        return True
    except Exception as exc:
        log.debug("Freesound download failed: %s", exc)
        return False


# ── ElevenLabs voice synthesis ────────────────────────────────────────────────

def generate_voice(
    text: str,
    output_path: str,
    voice_id: str = "21m00Tcm4TlvDq8ikWAM",  # Rachel (ElevenLabs default)
    model_id: str = "eleven_monolingual_v1",
) -> bool:
    """Generate narration audio via ElevenLabs. Returns True on success."""
    if not ELEVENLABS_API_KEY:
        log.debug("ELEVENLABS_API_KEY not set")
        return False
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        payload = json.dumps({
            "text": text,
            "model_id": model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_bytes(resp.read())
        return True
    except Exception as exc:
        log.debug("ElevenLabs TTS failed: %s", exc)
        return False


# ── FFmpeg mixing ─────────────────────────────────────────────────────────────

def _ffmpeg_available() -> bool:
    return shutil.which(FFMPEG) is not None


def mix_audio_layers(
    layers: list[tuple[str, float]],  # (file_path, volume_db)
    output_path: str,
    duration_s: float = 30.0,
    loop_all: bool = True,
) -> bool:
    """
    Mix multiple audio files into one using FFmpeg.
    layers: list of (file_path, volume_db_adjustment) tuples.
    """
    if not _ffmpeg_available():
        log.warning("ffmpeg not found — cannot mix audio")
        return False

    valid_layers = [(p, v) for p, v in layers if Path(p).exists()]
    if not valid_layers:
        log.warning("No valid audio layers to mix")
        return False

    inputs = []
    filter_parts = []
    for i, (path, vol_db) in enumerate(valid_layers):
        loop_flag = ["-stream_loop", "-1"] if loop_all else []
        inputs += loop_flag + ["-i", path]
        vol = 10 ** (vol_db / 20)  # dB to linear
        filter_parts.append(f"[{i}:a]volume={vol:.4f}[a{i}]")

    mix_inputs = "".join(f"[a{i}]" for i in range(len(valid_layers)))
    filter_complex = ";".join(filter_parts) + f";{mix_inputs}amix=inputs={len(valid_layers)}:duration=longest[aout]"

    cmd = (
        [FFMPEG, "-y"]
        + inputs
        + ["-filter_complex", filter_complex, "-map", "[aout]",
           "-t", str(duration_s), "-ar", "44100", "-ac", "2",
           output_path]
    )
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            log.warning("FFmpeg mix failed: %s", result.stderr.decode()[:300])
            return False
        return True
    except Exception as exc:
        log.warning("FFmpeg mix error: %s", exc)
        return False


def add_audio_to_video(video_path: str, audio_path: str, output_path: str) -> bool:
    """Merge an audio track into an existing video using FFmpeg."""
    if not _ffmpeg_available():
        return False
    cmd = [
        FFMPEG, "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        return result.returncode == 0
    except Exception:
        return False


# ── Scene → sound plan ────────────────────────────────────────────────────────

def analyse_scene_for_sounds(scene_graph: dict, world_plan: dict | None = None) -> dict[str, Any]:
    """
    Analyse a scene graph + optional world plan and return a sound design plan.
    Returns: {layers: [(query, tag, vol, loop)], music_mood, narration_text}
    """
    objects = scene_graph.get("objects", [])
    names = " ".join(o.get("name", "").lower() for o in objects)

    # Detect biome
    biome = "default"
    if any(k in names for k in ("tree", "forest", "grass", "bush", "foliage")):
        biome = "forest"
    elif any(k in names for k in ("city", "building", "street", "road", "car")):
        biome = "city"
    elif any(k in names for k in ("ocean", "sea", "water", "wave", "coast")):
        biome = "ocean"
    elif any(k in names for k in ("dungeon", "cave", "torch", "castle_int")):
        biome = "dungeon"
    elif any(k in names for k in ("neon", "corridor", "hologram", "terminal")):
        biome = "sci_fi"
    elif any(k in names for k in ("ruin", "abandon", "collapse", "wasteland")):
        biome = "post_apocalyptic"
    elif any(k in names for k in ("medieval", "blacksmith", "tavern", "market")):
        biome = "medieval"

    plan_mood = (world_plan or {}).get("mood", "neutral")
    plan_weather = (world_plan or {}).get("weather", "clear")

    sound_layers = list(BIOME_SOUNDS.get(biome, BIOME_SOUNDS["default"]))
    sound_layers += WEATHER_SOUNDS.get(plan_weather, [])

    return {
        "biome": biome,
        "weather": plan_weather,
        "mood": plan_mood,
        "music_mood": MOOD_MUSIC.get(plan_mood, MOOD_MUSIC["neutral"]),
        "sound_layers": sound_layers,
        "has_elevenlabs": bool(ELEVENLABS_API_KEY),
        "has_freesound": bool(FREESOUND_API_KEY),
        "ffmpeg_available": _ffmpeg_available(),
    }


# ── Main pipeline ─────────────────────────────────────────────────────────────

def design_scene_audio(
    scene_graph: dict,
    world_plan: dict | None = None,
    narration_text: str = "",
    output_filename: str = "scene_audio.mp3",
    duration_s: float = 30.0,
) -> dict[str, Any]:
    """
    Full pipeline: scene analysis → download layers → mix → return path.
    """
    plan = analyse_scene_for_sounds(scene_graph, world_plan)
    out_dir = _workspace()
    layers_collected: list[tuple[str, float]] = []
    downloaded: list[str] = []
    skipped: list[str] = []

    for i, (query, tag, vol_db, loop) in enumerate(plan["sound_layers"]):
        layer_path = str(Path(out_dir) / f"layer_{i:02d}_{tag}.mp3")
        success = False

        # Try Freesound
        if FREESOUND_API_KEY:
            results = _freesound_search(query, limit=1)
            if results:
                sound_id = results[0]["id"]
                success = _freesound_download(sound_id, layer_path)
                if success:
                    layers_collected.append((layer_path, vol_db))
                    downloaded.append(tag)

        if not success:
            skipped.append(tag)

    # Narration via ElevenLabs
    narration_path = None
    if narration_text and ELEVENLABS_API_KEY:
        narration_path = str(Path(out_dir) / "narration.mp3")
        if generate_voice(narration_text, narration_path):
            layers_collected.append((narration_path, -3.0))
        else:
            narration_path = None

    # Mix
    out_path = str(Path(out_dir) / output_filename)
    mixed = False
    if layers_collected and _ffmpeg_available():
        mixed = mix_audio_layers(layers_collected, out_path, duration_s=duration_s)

    return {
        "ok": True,
        "audio_path": out_path if mixed else None,
        "mixed": mixed,
        "biome": plan["biome"],
        "mood": plan["mood"],
        "downloaded_layers": downloaded,
        "skipped_layers": skipped,
        "narration_generated": narration_path is not None,
        "ffmpeg_available": plan["ffmpeg_available"],
        "sound_plan": plan,
        "note": (
            "Set FREESOUND_API_KEY for ambient layers, "
            "ELEVENLABS_API_KEY for narration, "
            "install ffmpeg for mixing."
            if not mixed else "Audio mixed successfully."
        ),
    }
