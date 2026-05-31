"""Lightweight validation helpers used by the MCP tools."""
from __future__ import annotations

from typing import Iterable, Sequence

VALID_RENDER_PRESETS = (
    "fast_preview",
    "portfolio_render",
    "archviz_render",
    "product_render",
    "cinematic_render",
)

VALID_STYLE_PRESETS = (
    "mobile_stylized",
    "pc_game_environment",
    "low_poly",
    "stylized_cartoon",
    "sci_fi_game_level",
    "modern_villa",
    "luxury_apartment",
    "minimalist_interior",
    "office_interior",
    "retail_store",
)

VALID_EXPORT_FORMATS = ("blend", "glb", "fbx", "obj")


def ensure_in(value: str, allowed: Sequence[str], label: str) -> str:
    """Validate that `value` is one of `allowed`, raising a helpful error."""
    if value not in allowed:
        raise ValueError(
            f"Invalid {label} '{value}'. Choose one of: {', '.join(allowed)}."
        )
    return value


def ensure_positive(value: float, label: str) -> float:
    if value <= 0:
        raise ValueError(f"{label} must be greater than 0 (got {value}).")
    return value


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def non_empty(value: str, label: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{label} must not be empty.")
    return value.strip()


def unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
