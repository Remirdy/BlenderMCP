"""Telemetry controls."""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from ..utils.telemetry import export_report, status


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def get_telemetry_status() -> dict:
        """Return telemetry mode and privacy guarantees."""
        return {"ok": True, **status()}

    @mcp.tool()
    def set_telemetry_mode(mode: str = "off") -> dict:
        """Set telemetry mode for this MCP process: off | local | anonymous."""
        if mode not in {"off", "local", "anonymous"}:
            return {"ok": False, "error": "mode must be off, local or anonymous"}
        os.environ["REMIRDY_TELEMETRY"] = mode
        return {"ok": True, **status()}

    @mcp.tool()
    def export_local_telemetry_report(limit: int = 200) -> dict:
        """Return the latest scrubbed local telemetry events."""
        return {"ok": True, **export_report(limit)}
