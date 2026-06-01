"""Shared fixtures for the Remirdy Blender Studio MCP test suite."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest


# ── temp directory fixture ────────────────────────────────────────────────────

@pytest.fixture
def tmp_work_dir(tmp_path: Path) -> Path:
    """Return a clean temporary directory for a single test."""
    return tmp_path


# ── minimal PNG fixture ───────────────────────────────────────────────────────

@pytest.fixture
def small_png(tmp_path: Path) -> Path:
    """Write a tiny 4×4 RGBA PNG to tmp_path and return its path."""
    try:
        from PIL import Image  # type: ignore[import-untyped]
    except ImportError:
        pytest.skip("Pillow not installed")

    img = Image.new("RGBA", (4, 4), color=(100, 150, 200, 255))
    out = tmp_path / "test_image.png"
    img.save(out)
    return out


# ── mock bridge response helpers ─────────────────────────────────────────────

def make_bridge_response(ok: bool, result=None, error: str = "") -> str:
    """Serialise a bridge response the same way the Blender add-on would."""
    payload: dict = {"ok": ok, "id": "test-id-123"}
    if ok:
        payload["result"] = result or {}
    else:
        payload["error"] = error
    return json.dumps(payload) + "\n"


@pytest.fixture
def bridge_ok_response():
    return make_bridge_response(ok=True, result={"message": "success"})


@pytest.fixture
def bridge_error_response():
    return make_bridge_response(ok=False, error="Operation failed in Blender")


# ── environment isolation ─────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_gemini_env(monkeypatch):
    """Ensure Gemini env vars are unset by default so tests don't need an API key."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
