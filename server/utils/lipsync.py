"""
Lip Sync Engine — Text → Voice → Blender Keyframes.

Pipeline
--------
1. Generate audio from text via ElevenLabs (or accept a pre-recorded file).
2. Analyse phoneme/viseme timing from the audio.
3. Map visemes to Blender shape key values.
4. Send keyframe animation data to Blender via the bridge.

Shape keys used (auto-created on the character head mesh)
---------------------------------------------------------
  Basis         — neutral
  Smile         — already created by op_create_facial_blendshapes
  Blink         — already created by op_create_facial_blendshapes
  Mouth_Open    — jaw drop (A/E sounds)
  Lips_Pucker   — puckered lips (O/U sounds)
  Mouth_Closed  — lips pressed together (M/B/P sounds)
  Mouth_Wide    — wide open (AH sound)

Phoneme → Viseme mapping (Preston Blair simplified)
----------------------------------------------------
  rest     → Basis
  MBP      → Mouth_Closed
  FSTH     → Mouth_Open (teeth visible, slight)
  AH       → Mouth_Wide
  OO       → Lips_Pucker
  EE       → Mouth_Open (smile-ish)
  default  → Mouth_Open (mid)

Environment variables
---------------------
ELEVENLABS_API_KEY — for voice synthesis
LIPSYNC_BACKEND    — "elevenlabs" | "local_tts" | "wav_only"
"""
from __future__ import annotations

import json
import os
import struct
import wave
from pathlib import Path
from typing import Any

from ..utils.logging_utils import get_logger

log = get_logger("remirdy.lipsync")

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")


# ── Phoneme → viseme mapping ──────────────────────────────────────────────────

VISEME_SHAPES: dict[str, dict[str, float]] = {
    "rest":   {"Mouth_Open": 0.0, "Lips_Pucker": 0.0, "Mouth_Wide": 0.0, "Mouth_Closed": 0.0},
    "MBP":    {"Mouth_Open": 0.0, "Lips_Pucker": 0.0, "Mouth_Wide": 0.0, "Mouth_Closed": 1.0},
    "FSTH":   {"Mouth_Open": 0.3, "Lips_Pucker": 0.0, "Mouth_Wide": 0.2, "Mouth_Closed": 0.0},
    "AH":     {"Mouth_Open": 0.8, "Lips_Pucker": 0.0, "Mouth_Wide": 1.0, "Mouth_Closed": 0.0},
    "OO":     {"Mouth_Open": 0.5, "Lips_Pucker": 1.0, "Mouth_Wide": 0.0, "Mouth_Closed": 0.0},
    "EE":     {"Mouth_Open": 0.4, "Lips_Pucker": 0.0, "Mouth_Wide": 0.6, "Mouth_Closed": 0.0, "Smile": 0.4},
    "default":{"Mouth_Open": 0.5, "Lips_Pucker": 0.0, "Mouth_Wide": 0.3, "Mouth_Closed": 0.0},
}

# Simple text-to-phoneme mapping (no Praat/Aligner needed — works offline)
CHAR_TO_VISEME: dict[str, str] = {
    "a": "AH", "e": "EE", "i": "EE", "o": "OO", "u": "OO",
    "m": "MBP", "b": "MBP", "p": "MBP",
    "f": "FSTH", "v": "FSTH", "s": "FSTH", "z": "FSTH",
    "t": "FSTH", "h": "default",
    " ": "rest", ".": "rest", ",": "rest", "!": "rest", "?": "rest",
}


def text_to_viseme_timeline(
    text: str, fps: int = 24, words_per_minute: int = 130
) -> list[dict[str, Any]]:
    """
    Convert text to a list of viseme keyframes using a simple phoneme approximation.
    No external tools needed — works fully offline.

    Returns list of: {frame: int, viseme: str, shape_keys: {name: value}}
    """
    # Average duration per character in frames
    chars_per_minute = words_per_minute * 5  # ~5 chars per word
    frames_per_char = (fps * 60) / chars_per_minute
    frames_per_char = max(1.0, frames_per_char)

    keyframes = []
    current_frame = 1

    for char in text.lower():
        viseme = CHAR_TO_VISEME.get(char, "default")
        shapes = VISEME_SHAPES.get(viseme, VISEME_SHAPES["default"])
        keyframes.append({
            "frame": int(current_frame),
            "viseme": viseme,
            "shape_keys": dict(shapes),
            "char": char,
        })
        current_frame += frames_per_char

    # End with rest pose
    keyframes.append({
        "frame": int(current_frame + fps * 0.3),
        "viseme": "rest",
        "shape_keys": dict(VISEME_SHAPES["rest"]),
        "char": "_end",
    })

    return keyframes


def audio_to_viseme_timeline(
    audio_path: str, fps: int = 24
) -> list[dict[str, Any]]:
    """
    Approximate viseme timeline from audio amplitude (RMS per frame).
    Uses Python's built-in wave module — no dependencies needed.

    Opens a WAV file and maps amplitude → mouth openness.
    """
    try:
        with wave.open(audio_path, "r") as wf:
            n_frames = wf.getnframes()
            framerate = wf.getframerate()
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            raw = wf.readframes(n_frames)

        # Parse samples
        fmt = {1: "B", 2: "h", 4: "i"}.get(sampwidth, "h")
        samples = list(struct.unpack(f"{n_frames * n_channels}{fmt}", raw))
        if n_channels > 1:
            samples = samples[::n_channels]  # take first channel

        # Normalise
        max_val = 2 ** (sampwidth * 8 - 1) if sampwidth > 1 else 128
        samples_norm = [s / max_val for s in samples]

        # RMS per video frame
        audio_fps = framerate
        samples_per_frame = int(audio_fps / fps)
        keyframes = []

        for frame_idx in range(0, len(samples_norm), samples_per_frame):
            chunk = samples_norm[frame_idx: frame_idx + samples_per_frame]
            if not chunk:
                break
            rms = (sum(s * s for s in chunk) / len(chunk)) ** 0.5
            # Map RMS → mouth open (0.0–1.0)
            mouth_open = min(1.0, rms * 8.0)
            viseme = "AH" if mouth_open > 0.6 else ("default" if mouth_open > 0.2 else "rest")
            shapes = {**VISEME_SHAPES[viseme]}
            shapes["Mouth_Open"] = mouth_open
            keyframes.append({
                "frame": (frame_idx // samples_per_frame) + 1,
                "viseme": viseme,
                "shape_keys": shapes,
                "rms": round(rms, 4),
            })

        return keyframes
    except Exception as exc:
        log.warning("[LipSync] Audio analysis failed: %s — falling back to text timeline", exc)
        return []


# ── ElevenLabs voice generation ───────────────────────────────────────────────

def generate_voice_for_lipsync(
    text: str,
    output_path: str,
    voice_id: str = "21m00Tcm4TlvDq8ikWAM",
) -> bool:
    """Generate MP3 audio from text via ElevenLabs. Returns True on success."""
    if not ELEVENLABS_API_KEY:
        return False
    try:
        import urllib.request
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
        payload = json.dumps({
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            "output_format": "pcm_44100",  # WAV-compatible PCM
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw_pcm = resp.read()

        # Wrap PCM in WAV container so wave module can read it
        wav_path = output_path.replace(".mp3", ".wav").replace(".MP3", ".wav")
        if not wav_path.endswith(".wav"):
            wav_path = output_path + ".wav"

        with wave.open(wav_path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(44100)
            wf.writeframes(raw_pcm)

        Path(output_path).write_bytes(raw_pcm)  # also save raw
        return True
    except Exception as exc:
        log.debug("[LipSync] ElevenLabs voice failed: %s", exc)
        return False


# ── Main pipeline ─────────────────────────────────────────────────────────────

def _workspace(*parts: str) -> str:
    root = os.environ.get("REMIRDY_WORKSPACE", str(Path.home() / "RemirdyWorkspace"))
    out = Path(root) / "outputs" / "lipsync"
    out.mkdir(parents=True, exist_ok=True)
    return str(out.joinpath(*parts))


def create_lipsync_animation(
    text: str,
    character_object: str = "CHR_Head",
    voice_id: str = "21m00Tcm4TlvDq8ikWAM",
    fps: int = 24,
    words_per_minute: int = 130,
    audio_output_path: str | None = None,
) -> dict[str, Any]:
    """
    Full lip sync pipeline:
      1. Generate voice audio (ElevenLabs if key available, else text timeline).
      2. Analyse audio → viseme keyframes.
      3. Return keyframe data for Blender.

    The caller must send the keyframes to Blender via the bridge.
    """
    audio_path = audio_output_path or _workspace("lipsync_audio.wav")

    # Step 1: Generate voice
    audio_generated = False
    if ELEVENLABS_API_KEY:
        audio_generated = generate_voice_for_lipsync(text, audio_path, voice_id)

    # Step 2: Build timeline
    keyframes: list[dict[str, Any]] = []
    if audio_generated and Path(audio_path + ".wav").exists():
        keyframes = audio_to_viseme_timeline(audio_path + ".wav", fps)
    if not keyframes:
        log.info("[LipSync] Using text-based timeline (no audio analysis)")
        keyframes = text_to_viseme_timeline(text, fps, words_per_minute)

    total_frames = keyframes[-1]["frame"] if keyframes else fps * 5

    # Required shape keys list
    required_shapes = ["Mouth_Open", "Lips_Pucker", "Mouth_Wide", "Mouth_Closed", "Smile", "Blink"]

    return {
        "ok": True,
        "text": text,
        "character_object": character_object,
        "audio_path": audio_path if audio_generated else None,
        "audio_generated": audio_generated,
        "total_frames": total_frames,
        "fps": fps,
        "keyframe_count": len(keyframes),
        "keyframes": keyframes,
        "required_shape_keys": required_shapes,
        "timeline_source": "audio_rms" if (audio_generated and keyframes and "rms" in keyframes[0]) else "text_phoneme",
    }
