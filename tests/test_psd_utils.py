"""Tests for server.utils.psd_utils (runnable without Blender or a real PSD)."""
from __future__ import annotations

from pathlib import Path

import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_png(path: Path, color=(100, 150, 200), mode="RGB") -> Path:
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow not installed")
    img = Image.new(mode, (64, 64), color=color)
    img.save(path)
    return path


# ── get_dominant_color ────────────────────────────────────────────────────────

class TestGetDominantColor:
    def test_returns_float_tuple(self, tmp_path):
        from PIL import Image
        from server.utils.psd_utils import get_dominant_color

        img = Image.new("RGB", (10, 10), color=(255, 0, 0))
        r, g, b = get_dominant_color(img)
        assert all(isinstance(v, float) for v in (r, g, b))

    def test_values_in_range(self, tmp_path):
        from PIL import Image
        from server.utils.psd_utils import get_dominant_color

        img = Image.new("RGB", (10, 10), color=(128, 64, 32))
        r, g, b = get_dominant_color(img)
        for v in (r, g, b):
            assert 0.0 <= v <= 1.0

    def test_red_image_dominant_is_reddish(self):
        from PIL import Image
        from server.utils.psd_utils import get_dominant_color

        img = Image.new("RGB", (10, 10), color=(255, 0, 0))
        r, g, b = get_dominant_color(img)
        assert r > g and r > b


# ── detect_visual_objects ─────────────────────────────────────────────────────

class TestDetectVisualObjects:
    def test_returns_list(self, tmp_path):
        from PIL import Image
        from server.utils.psd_utils import detect_visual_objects

        # Blue sky top, green ground bottom
        img = Image.new("RGB", (64, 64), color=(100, 150, 220))
        elements = detect_visual_objects(img)
        assert isinstance(elements, list)

    def test_elements_have_type_key(self, tmp_path):
        from PIL import Image
        from server.utils.psd_utils import detect_visual_objects

        img = Image.new("RGB", (64, 64), color=(100, 150, 220))
        elements = detect_visual_objects(img)
        for el in elements:
            assert "type" in el


# ── parse_layered_image (flat PNG path) ───────────────────────────────────────

class TestParseFlatImage:
    def test_flat_png_returns_dict(self, tmp_path):
        from server.utils.psd_utils import parse_layered_image

        png = _make_png(tmp_path / "test.png")
        result = parse_layered_image(str(png), str(tmp_path / "out"))
        assert isinstance(result, dict)

    def test_flat_png_is_not_psd(self, tmp_path):
        from server.utils.psd_utils import parse_layered_image

        png = _make_png(tmp_path / "test.png")
        result = parse_layered_image(str(png), str(tmp_path / "out"))
        assert result["is_psd"] is False

    def test_flat_png_has_layers(self, tmp_path):
        from server.utils.psd_utils import parse_layered_image

        png = _make_png(tmp_path / "test.png")
        result = parse_layered_image(str(png), str(tmp_path / "out"))
        assert len(result["layers"]) >= 1

    def test_flat_png_width_height(self, tmp_path):
        from server.utils.psd_utils import parse_layered_image

        png = _make_png(tmp_path / "test.png")
        result = parse_layered_image(str(png), str(tmp_path / "out"))
        assert result["width"] == 64
        assert result["height"] == 64

    def test_flat_png_has_visual_elements(self, tmp_path):
        from server.utils.psd_utils import parse_layered_image

        png = _make_png(tmp_path / "test.png")
        result = parse_layered_image(str(png), str(tmp_path / "out"))
        assert "visual_elements" in result
        assert isinstance(result["visual_elements"], list)

    def test_flat_png_has_sky_and_ground_color(self, tmp_path):
        from server.utils.psd_utils import parse_layered_image

        png = _make_png(tmp_path / "test.png")
        result = parse_layered_image(str(png), str(tmp_path / "out"))
        assert "sky_color" in result
        assert "ground_color" in result
        assert len(result["sky_color"]) == 3
        assert len(result["ground_color"]) == 3

    def test_missing_file_raises(self, tmp_path):
        from server.utils.psd_utils import parse_layered_image

        with pytest.raises(FileNotFoundError):
            parse_layered_image(str(tmp_path / "nonexistent.png"), str(tmp_path / "out"))

    def test_ai_scene_plan_key_present(self, tmp_path):
        """ai_scene_plan key should be in result even when AI is unavailable (it will be None)."""
        from server.utils.psd_utils import parse_layered_image

        png = _make_png(tmp_path / "test.png")
        result = parse_layered_image(str(png), str(tmp_path / "out"))
        assert "ai_scene_plan" in result

    def test_rgba_png_adds_foreground_layer(self, tmp_path):
        from server.utils.psd_utils import parse_layered_image

        png = _make_png(tmp_path / "test_rgba.png", color=(100, 150, 200, 255), mode="RGBA")
        result = parse_layered_image(str(png), str(tmp_path / "out"))
        roles = [l["role"] for l in result["layers"]]
        assert "foreground" in roles
