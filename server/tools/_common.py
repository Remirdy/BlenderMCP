"""Shared helpers for tool modules."""
from __future__ import annotations

import time
from typing import Any

from ..bridge_client import BridgeError, get_client
from ..utils.logging_utils import get_logger
from ..utils.telemetry import record_tool

log = get_logger("remirdy.tools")


def call(op: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Forward a structured operation to the Blender bridge.

    Returns a uniform envelope so the AI client always gets a predictable shape,
    even on failure.
    """
    started = time.perf_counter()
    try:
        result = get_client().request(op, params or {})
        record_tool(op, (time.perf_counter() - started) * 1000, True)
        return {"ok": True, "op": op, **result}
    except BridgeError as exc:
        log.warning("Bridge op '%s' failed: %s", op, exc)
        record_tool(op, (time.perf_counter() - started) * 1000, False, type(exc).__name__)
        return {
            "ok": False,
            "op": op,
            "error": str(exc),
            "hint": "Run connect_blender and ensure the Remirdy add-on bridge is started in Blender.",
        }
