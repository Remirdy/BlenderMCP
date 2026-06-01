"""MCP tools — Automatic Sound Design for 3D scenes."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from ..utils.logging_utils import get_logger

log = get_logger("remirdy.sound_tools")


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def design_scene_audio(
        narration_text: str = "",
        duration_seconds: float = 30.0,
        output_filename: str = "scene_audio.mp3",
    ) -> dict:
        """
        Automatically design an ambient audio soundtrack for the current Blender scene.

        Pipeline:
          1. Read the scene graph (objects, biome type, weather, mood).
          2. Map scene elements to appropriate sound categories
             (forest → birds + wind, dungeon → dripping water + torch,
              sci-fi → hum + beeps, city → traffic + crowd, etc.)
          3. Download matching sounds from Freesound.org (FREESOUND_API_KEY).
          4. Optionally generate narration via ElevenLabs (ELEVENLABS_API_KEY).
          5. Mix all layers with FFmpeg into a single MP3.

        Returns: audio_path, biome, mood, downloaded layers, mix status.

        Optional env vars:
            FREESOUND_API_KEY   — ambient FX from freesound.org
            ELEVENLABS_API_KEY  — AI narration voice
            FFMPEG_PATH         — custom ffmpeg binary path

        Args:
            narration_text   : Optional narration text (read by AI voice if ElevenLabs key set).
            duration_seconds : Target audio length in seconds (default 30).
            output_filename  : Output file name (default scene_audio.mp3).
        """
        from ..tools._common import call
        from ..utils.sound_design import design_scene_audio as _design

        graph_result = call("get_scene_graph", {})
        scene_graph = graph_result if graph_result.get("ok") else {}

        return _design(
            scene_graph=scene_graph,
            narration_text=narration_text,
            output_filename=output_filename,
            duration_s=duration_seconds,
        )

    @mcp.tool()
    def generate_narration(
        text: str,
        output_path: str = "",
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",
    ) -> dict:
        """
        Generate AI narration audio from text using ElevenLabs.
        Requires ELEVENLABS_API_KEY environment variable.

        Args:
            text       : Text to speak (max ~2500 chars per call).
            output_path: Where to save the MP3 (auto-generated if empty).
            voice_id   : ElevenLabs voice ID (default: Rachel).
                         Find IDs at: https://api.elevenlabs.io/v1/voices
        """
        from ..utils.sound_design import generate_voice, _workspace
        import os
        from pathlib import Path

        if not os.environ.get("ELEVENLABS_API_KEY"):
            return {"ok": False, "error": "ELEVENLABS_API_KEY not set. Get a free key at elevenlabs.io"}

        out = output_path or _workspace("narration.mp3")
        success = generate_voice(text, out, voice_id)
        return {
            "ok": success,
            "audio_path": out if success else None,
            "error": None if success else "ElevenLabs TTS failed — check API key and quota",
        }

    @mcp.tool()
    def add_audio_to_render(
        video_path: str,
        audio_path: str,
        output_path: str = "",
    ) -> dict:
        """
        Merge an audio track into a rendered video (turntable, storyboard, etc.) using FFmpeg.
        Requires ffmpeg installed on the system.

        Args:
            video_path  : Path to the video file (MP4, AVI, etc.).
            audio_path  : Path to the audio file (MP3, WAV, etc.).
            output_path : Where to save the result (auto-generated if empty).
        """
        from ..utils.sound_design import add_audio_to_video, _workspace
        from pathlib import Path

        out = output_path or _workspace(f"with_audio_{Path(video_path).stem}.mp4")
        success = add_audio_to_video(video_path, audio_path, out)
        return {
            "ok": success,
            "output_path": out if success else None,
            "error": None if success else "FFmpeg merge failed — check that ffmpeg is installed",
        }

    @mcp.tool()
    def analyse_scene_sound_plan() -> dict:
        """
        Preview what sound layers would be chosen for the current scene,
        without downloading or mixing anything.
        Returns: biome, mood, planned sound layers, music mood suggestion,
        and which external services are configured.
        """
        from ..tools._common import call
        from ..utils.sound_design import analyse_scene_for_sounds

        graph_result = call("get_scene_graph", {})
        return analyse_scene_for_sounds(
            scene_graph=graph_result if graph_result.get("ok") else {},
        )
