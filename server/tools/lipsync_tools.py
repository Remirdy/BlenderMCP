"""MCP tools — Lip Sync animation for Blender characters."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from ..utils.logging_utils import get_logger

log = get_logger("remirdy.lipsync_tools")


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def animate_lip_sync(
        text: str,
        character_object: str = "CHR_Head",
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",
        fps: int = 24,
        words_per_minute: int = 130,
    ) -> dict:
        """
        Animate a character's mouth to match spoken dialogue.

        Pipeline:
          1. Generate voice audio via ElevenLabs (if ELEVENLABS_API_KEY set).
          2. Analyse audio amplitude per frame → map to mouth shape keys.
          3. Create extended facial shape keys on the character (Mouth_Open,
             Lips_Pucker, Mouth_Wide, Mouth_Closed, Smile).
          4. Insert keyframes in Blender for each viseme at the correct frame.

        Works without ElevenLabs — falls back to text-phoneme approximation
        (reads the text, estimates timing from words-per-minute).

        Args:
            text             : Dialogue to speak (max ~500 chars for best results).
            character_object : Blender object name of the head mesh (default CHR_Head).
            voice_id         : ElevenLabs voice ID (default Rachel).
                               Find more at: https://api.elevenlabs.io/v1/voices
            fps              : Frames per second (must match Blender scene, default 24).
            words_per_minute : Speaking pace for text-phoneme mode (default 130).

        Returns: audio_path, keyframe_count, total_frames, timeline_source.
        Requires ELEVENLABS_API_KEY for voice generation (optional but recommended).
        """
        from ..utils.lipsync import create_lipsync_animation
        from ..tools._common import call

        # Step 1: Build lipsync data
        lipsync = create_lipsync_animation(
            text=text,
            character_object=character_object,
            voice_id=voice_id,
            fps=fps,
            words_per_minute=words_per_minute,
        )
        if not lipsync.get("ok"):
            return lipsync

        # Step 2: Ensure extended shape keys exist in Blender
        call("create_facial_blendshapes", {"head_object": character_object})

        # Step 3: Apply keyframes via bridge
        anim_result = call("apply_lipsync_keyframes", {
            "object_name": character_object,
            "keyframes": lipsync["keyframes"],
            "fps": fps,
            "total_frames": lipsync["total_frames"],
        })

        return {
            **lipsync,
            "blender_result": anim_result,
            "ready_to_render": True,
            "next_steps": [
                "render_preview to see the animation",
                "export_glb to export with shape key animation",
            ],
        }

    @mcp.tool()
    def preview_lipsync_timeline(
        text: str,
        fps: int = 24,
        words_per_minute: int = 130,
    ) -> dict:
        """
        Preview the viseme/keyframe timeline for a text without applying it to Blender.
        Useful for checking timing before committing to the full animation.

        Returns the full keyframe list with viseme names and shape key values per frame.
        """
        from ..utils.lipsync import text_to_viseme_timeline
        keyframes = text_to_viseme_timeline(text, fps, words_per_minute)
        return {
            "ok": True,
            "text": text,
            "total_frames": keyframes[-1]["frame"] if keyframes else 0,
            "keyframe_count": len(keyframes),
            "fps": fps,
            "estimated_duration_s": round(keyframes[-1]["frame"] / fps if keyframes else 0, 1),
            "keyframes": keyframes[:30],  # show first 30 only to keep response short
            "note": "First 30 keyframes shown. Use animate_lip_sync to apply to Blender.",
        }

    @mcp.tool()
    def setup_lipsync_shape_keys(character_object: str = "CHR_Head") -> dict:
        """
        Add all required lip sync shape keys to a character head mesh.
        Creates: Mouth_Open, Lips_Pucker, Mouth_Wide, Mouth_Closed (+ Smile, Blink if missing).

        Run this once before animate_lip_sync if shape keys are missing.
        """
        from ..tools._common import call
        return call("create_facial_blendshapes", {"head_object": character_object})
