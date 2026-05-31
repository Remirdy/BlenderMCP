"""Opt-in anonymous/local telemetry for tool execution.

Telemetry never records prompts, paths, screenshots, object names or API keys.
The default mode is off. Set REMIRDY_TELEMETRY=local to write a local JSONL log,
or REMIRDY_TELEMETRY=anonymous to enable the same scrubbed payload for a future
remote collector.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any


SAFE_ERROR_LEN = 96


def _workspace() -> Path:
    root = os.environ.get("REMIRDY_WORKSPACE", os.path.join(Path.home(), "RemirdyWorkspace"))
    path = Path(root) / "outputs" / "telemetry"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _install_id() -> str:
    path = _workspace() / "install_id"
    if path.exists():
        return path.read_text().strip()
    raw = uuid.uuid4().hex
    path.write_text(raw)
    return raw


def mode() -> str:
    value = os.environ.get("REMIRDY_TELEMETRY", "off").strip().lower()
    return value if value in {"off", "local", "anonymous"} else "off"


def status() -> dict[str, Any]:
    current = mode()
    return {
        "mode": current,
        "enabled": current != "off",
        "local_log": str(_workspace() / "events.jsonl"),
        "records_prompts": False,
        "records_paths": False,
        "records_screenshots": False,
        "records_api_keys": False,
    }


def record_tool(tool: str, duration_ms: float, ok: bool, error: str | None = None) -> None:
    current = mode()
    if current == "off":
        return
    event = {
        "ts": round(time.time(), 3),
        "install": hashlib.sha256(_install_id().encode("utf-8")).hexdigest()[:16],
        "tool": tool,
        "duration_ms": round(duration_ms, 2),
        "ok": bool(ok),
        "error": (error or "")[:SAFE_ERROR_LEN] if error else None,
    }
    with (_workspace() / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, separators=(",", ":")) + "\n")


def export_report(limit: int = 200) -> dict[str, Any]:
    log = _workspace() / "events.jsonl"
    if not log.exists():
        return {"events": [], "count": 0, "path": str(log)}
    lines = log.read_text(encoding="utf-8").splitlines()[-limit:]
    events = [json.loads(line) for line in lines if line.strip()]
    return {"events": events, "count": len(events), "path": str(log)}
