"""Tests for server.utils.validation helpers."""
from __future__ import annotations

import pytest

from server.utils.validation import (
    clamp,
    ensure_in,
    ensure_positive,
    non_empty,
    unique,
    VALID_EXPORT_FORMATS,
    VALID_RENDER_PRESETS,
    VALID_STYLE_PRESETS,
)


class TestEnsureIn:
    def test_valid_value_passes(self):
        result = ensure_in("blend", VALID_EXPORT_FORMATS, "export format")
        assert result == "blend"

    def test_all_render_presets_pass(self):
        for preset in VALID_RENDER_PRESETS:
            assert ensure_in(preset, VALID_RENDER_PRESETS, "render preset") == preset

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError, match="Invalid export format"):
            ensure_in("mp4", VALID_EXPORT_FORMATS, "export format")

    def test_error_message_lists_options(self):
        with pytest.raises(ValueError, match="blend"):
            ensure_in("bad", VALID_EXPORT_FORMATS, "export format")


class TestEnsurePositive:
    def test_positive_passes(self):
        assert ensure_positive(1.0, "scale") == 1.0

    def test_zero_raises(self):
        with pytest.raises(ValueError, match="greater than 0"):
            ensure_positive(0.0, "scale")

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            ensure_positive(-5.0, "scale")


class TestClamp:
    def test_within_range(self):
        assert clamp(0.5, 0.0, 1.0) == 0.5

    def test_below_low(self):
        assert clamp(-1.0, 0.0, 1.0) == 0.0

    def test_above_high(self):
        assert clamp(2.0, 0.0, 1.0) == 1.0

    def test_at_boundaries(self):
        assert clamp(0.0, 0.0, 1.0) == 0.0
        assert clamp(1.0, 0.0, 1.0) == 1.0


class TestNonEmpty:
    def test_valid_string_passes(self):
        assert non_empty("hello", "label") == "hello"

    def test_strips_whitespace(self):
        assert non_empty("  hello  ", "label") == "hello"

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            non_empty("", "label")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            non_empty("   ", "label")


class TestUnique:
    def test_removes_duplicates(self):
        result = unique(["a", "b", "a", "c", "b"])
        assert result == ["a", "b", "c"]

    def test_preserves_order(self):
        result = unique(["c", "a", "b"])
        assert result == ["c", "a", "b"]

    def test_empty_list(self):
        assert unique([]) == []

    def test_all_unique_unchanged(self):
        items = ["x", "y", "z"]
        assert unique(items) == items
