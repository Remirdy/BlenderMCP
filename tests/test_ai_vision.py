"""Tests for server.utils.ai_vision — uses monkeypatching; no real API key needed."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import anyio
import pytest

from server.utils.ai_vision import (
    _get_api_key,
    _parse_json_response,
    analyze_flat_image_with_ai,
    analyze_image_with_host_ai,
    analyze_image_with_gemini,
    generate_scene_plan_with_host_ai,
    analyze_psd_layer,
    extract_scene_objects,
    generate_scene_plan,
    is_available,
)


# ── _get_api_key ──────────────────────────────────────────────────────────────

class TestGetApiKey:
    def test_returns_none_without_env(self):
        # clear_gemini_env fixture ensures these are unset
        assert _get_api_key() is None

    def test_reads_gemini_api_key(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "key-abc")
        assert _get_api_key() == "key-abc"

    def test_reads_google_gemini_api_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "key-xyz")
        assert _get_api_key() == "key-xyz"

    def test_prefers_gemini_api_key(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "primary")
        monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "secondary")
        assert _get_api_key() == "primary"


# ── is_available ──────────────────────────────────────────────────────────────

class TestIsAvailable:
    def test_false_without_api_key(self):
        assert is_available() is False

    def test_true_with_api_key_and_package(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        mock_client = MagicMock()
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        with patch.dict("sys.modules", {"google": MagicMock(), "google.genai": mock_genai}):
            # Force re-evaluation by patching _get_client
            with patch("server.utils.ai_vision._get_client", return_value=mock_client):
                assert is_available() is True


# ── _parse_json_response ──────────────────────────────────────────────────────

class TestParseJsonResponse:
    def test_parses_valid_json(self):
        data = _parse_json_response('{"key": "value"}')
        assert data == {"key": "value"}

    def test_returns_fallback_on_invalid_json(self):
        result = _parse_json_response("not json", fallback=[])
        assert result == []

    def test_returns_fallback_on_none(self):
        assert _parse_json_response(None, fallback="default") == "default"

    def test_strips_markdown_fences(self):
        raw = "```json\n{\"x\": 1}\n```"
        result = _parse_json_response(raw)
        assert result == {"x": 1}

    def test_strips_generic_code_fences(self):
        raw = "```\n[1, 2, 3]\n```"
        result = _parse_json_response(raw)
        assert result == [1, 2, 3]

    def test_parses_array(self):
        result = _parse_json_response('[{"name": "obj"}]')
        assert isinstance(result, list)
        assert result[0]["name"] == "obj"


# ── extract_scene_objects ─────────────────────────────────────────────────────

class TestExtractSceneObjects:
    def test_returns_none_without_api_key(self, tmp_path):
        png = tmp_path / "test.png"
        png.write_bytes(b"fake")
        result = extract_scene_objects(str(png))
        assert result is None

    def test_returns_list_with_mocked_client(self, monkeypatch, tmp_path):
        png = tmp_path / "test.png"
        png.write_bytes(b"fake")

        mock_response = json.dumps([
            {"name": "sky", "type": "sky", "position_2d": [0.5, 0.1],
             "estimated_3d": {"x": 0, "y": 0, "z": 5},
             "color": "#87CEEB", "material": "sky", "scale": 1.0}
        ])

        mock_client = MagicMock()
        with patch("server.utils.ai_vision._get_client", return_value=mock_client):
            with patch("server.utils.ai_vision._call_gemini", return_value=mock_response):
                result = extract_scene_objects(str(png))

        assert isinstance(result, list)
        assert result[0]["name"] == "sky"

    def test_handles_wrapped_object_response(self, monkeypatch, tmp_path):
        png = tmp_path / "test.png"
        png.write_bytes(b"fake")

        mock_response = json.dumps({
            "objects": [{"name": "tree", "type": "plant"}]
        })

        mock_client = MagicMock()
        with patch("server.utils.ai_vision._get_client", return_value=mock_client):
            with patch("server.utils.ai_vision._call_gemini", return_value=mock_response):
                result = extract_scene_objects(str(png))

        assert result is not None
        assert result[0]["name"] == "tree"


# ── analyze_psd_layer ─────────────────────────────────────────────────────────

class TestAnalyzePsdLayer:
    def test_returns_none_without_api_key(self, tmp_path):
        png = tmp_path / "layer.png"
        png.write_bytes(b"fake")
        result = analyze_psd_layer(str(png), "sky_layer")
        assert result is None

    def test_returns_dict_with_mock(self, tmp_path):
        png = tmp_path / "layer.png"
        png.write_bytes(b"fake")

        mock_response = json.dumps({
            "object_type": "sky gradient",
            "description": "A blue-to-orange gradient sky.",
            "suggested_3d_role": "background",
            "dominant_color": "#87CEEB",
            "material_hint": "sky",
            "scale_estimate": 1.0,
        })

        mock_client = MagicMock()
        with patch("server.utils.ai_vision._get_client", return_value=mock_client):
            with patch("server.utils.ai_vision._call_gemini", return_value=mock_response):
                result = analyze_psd_layer(str(png), "sky_layer")

        assert isinstance(result, dict)
        assert result["suggested_3d_role"] == "background"


# ── generate_scene_plan ───────────────────────────────────────────────────────

class TestGenerateScenePlan:
    def test_returns_none_without_api_key(self, tmp_path):
        png = tmp_path / "scene.png"
        png.write_bytes(b"fake")
        result = generate_scene_plan(str(png))
        assert result is None

    def test_returns_dict_with_mock(self, tmp_path):
        png = tmp_path / "scene.png"
        png.write_bytes(b"fake")

        mock_response = json.dumps({
            "objects": [],
            "scene_mood": "warm_mediterranean",
            "lighting": "golden_hour",
            "camera_angle": "slightly_elevated_3/4",
            "background_type": "sky_hdri",
            "color_palette": ["#F4A460", "#87CEEB"],
        })

        mock_client = MagicMock()
        with patch("server.utils.ai_vision._get_client", return_value=mock_client):
            with patch("server.utils.ai_vision._call_gemini", return_value=mock_response):
                result = generate_scene_plan(str(png))

        assert isinstance(result, dict)
        assert result["scene_mood"] == "warm_mediterranean"
        assert result["lighting"] == "golden_hour"

    def test_analyze_flat_image_delegates_to_generate_scene_plan(self, tmp_path):
        png = tmp_path / "flat.png"
        png.write_bytes(b"fake")

        with patch("server.utils.ai_vision.generate_scene_plan", return_value={"mocked": True}) as mock_plan:
            result = analyze_flat_image_with_ai(str(png))
            mock_plan.assert_called_once_with(str(png), layers_meta=None)
            assert result == {"mocked": True}


class TestHostAiVision:
    def test_host_ai_returns_sampling_text(self, tmp_path):
        png = tmp_path / "scene.png"
        png.write_bytes(b"fake")

        class FakeResult:
            content = type("Content", (), {"type": "text", "text": '{"ok": true}'})()

        class FakeSession:
            async def create_message(self, **kwargs):
                assert kwargs["messages"][0].content[0].type == "image"
                assert kwargs["messages"][0].content[1].type == "text"
                return FakeResult()

        ctx = type("Ctx", (), {"session": FakeSession(), "request_id": "req-1"})()
        raw = anyio.run(analyze_image_with_host_ai, ctx, str(png), "Return JSON")
        assert raw == '{"ok": true}'

    def test_host_scene_plan_parses_json(self, tmp_path):
        png = tmp_path / "scene.png"
        png.write_bytes(b"fake")

        class FakeResult:
            content = type(
                "Content",
                (),
                {
                    "type": "text",
                    "text": json.dumps({"scene_mood": "studio", "objects": []}),
                },
            )()

        class FakeSession:
            async def create_message(self, **kwargs):
                return FakeResult()

        ctx = type("Ctx", (), {"session": FakeSession(), "request_id": "req-1"})()
        plan = anyio.run(generate_scene_plan_with_host_ai, ctx, str(png))
        assert plan == {"scene_mood": "studio", "objects": []}
