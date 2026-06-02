"""Manage the host-side MCP server process from the Blender add-on."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
from pathlib import Path


URL_RE = re.compile(r"https://[^\s]+/(?:mcp|sse)\b")

STATE = {
    "running": False,
    "mode": "off",
    "local_url": "",
    "public_url": "",
    "last_status": "stopped",
    "last_line": "",
    "pid": None,
}

_PROCESS: subprocess.Popen[str] | None = None


def default_project_path() -> str:
    """Return the repo root when running from a source checkout, otherwise empty."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "server" / "main.py").exists() and (parent / "pyproject.toml").exists():
            return str(parent)
    known = Path.home() / "Desktop" / "Blender_MCP" / "remirdy-blender-studio-mcp"
    if (known / "server" / "main.py").exists():
        return str(known)
    return ""


def default_python_executable() -> str:
    """Prefer the project virtualenv Python because Blender's Python lacks MCP deps."""
    project = default_project_path()
    if project:
        root = Path(project)
        candidates = [
            root / ".venv" / "bin" / "python",
            root / ".venv" / "Scripts" / "python.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
    return sys.executable


def _python_can_import_mcp(python_bin: str) -> tuple[bool, str]:
    check = (
        "import pathlib, sys, sysconfig\n"
        "purelib = pathlib.Path(sysconfig.get_paths().get('purelib', ''))\n"
        "platlib = pathlib.Path(sysconfig.get_paths().get('platlib', ''))\n"
        "paths = [purelib / 'mcp', platlib / 'mcp']\n"
        "sys.exit(0 if any(path.is_dir() for path in paths) else 1)\n"
    )
    try:
        result = subprocess.run(
            [python_bin, "-c", check],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        return False, str(exc)
    if result.returncode == 0:
        return True, ""
    return False, (result.stderr or result.stdout or "mcp package is not installed").strip()


def _with_tool_path(env: dict[str, str]) -> dict[str, str]:
    """Add common CLI install locations missing from Blender's GUI environment."""
    extra_paths = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
    ]
    current = env.get("PATH", "")
    parts = current.split(os.pathsep) if current else []
    for path in reversed(extra_paths):
        if path not in parts:
            parts.insert(0, path)
    env["PATH"] = os.pathsep.join(parts)
    return env


def _set_stopped(status: str) -> None:
    STATE.update({
        "running": False,
        "mode": "off",
        "last_status": status,
        "pid": None,
    })


def _watch_output(process: subprocess.Popen[str]) -> None:
    stream = process.stderr or process.stdout
    if stream:
        for line in stream:
            text = line.strip()
            if not text:
                continue
            STATE["last_line"] = text[-240:]
            match = URL_RE.search(text)
            if match:
                STATE["public_url"] = match.group(0)
                STATE["last_status"] = "ready"
            elif "Uvicorn running on" in text:
                STATE["last_status"] = "listening"
    code = process.wait()
    if _PROCESS is process:
        _set_stopped(f"exited ({code})")


def start(
    *,
    project_path: str,
    python_executable: str,
    transport: str,
    host: str,
    port: int,
    tunnel: str = "auto",
    public_url: str = "",
    http_protocol: str = "streamable-http",
) -> str:
    """Start the host MCP server process."""
    global _PROCESS
    if _PROCESS and _PROCESS.poll() is None:
        return f"MCP server already running (pid {_PROCESS.pid})."

    project = project_path.strip() or default_project_path()
    root = Path(project).expanduser().resolve()
    if not (root / "server" / "main.py").exists():
        return f"Invalid MCP project folder: {root}"

    python_bin = python_executable.strip() or default_python_executable()
    can_import, import_error = _python_can_import_mcp(python_bin)
    if not can_import:
        fallback_python = default_python_executable()
        if fallback_python != python_bin:
            can_import, import_error = _python_can_import_mcp(fallback_python)
            if can_import:
                python_bin = fallback_python
        if not can_import:
            STATE["last_line"] = "Selected Python cannot import mcp."
            return (
                "Selected Python cannot import 'mcp'. Set Python to the project "
                ".venv/bin/python, or run: pip install -e . "
                f"Details: {import_error[-160:]}"
            )
    args = [
        python_bin,
        "-m",
        "server.main",
        "--transport",
        transport,
        "--host",
        host,
        "--port",
        str(port),
        "--http-protocol",
        http_protocol,
    ]
    if transport == "https":
        args.extend(["--tunnel", tunnel])
        if public_url.strip():
            args.extend(["--public-url", public_url.strip()])

    env = _with_tool_path(os.environ.copy())
    env.setdefault("PYTHONUNBUFFERED", "1")

    try:
        process = subprocess.Popen(
            args,
            cwd=str(root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except Exception as exc:
        return f"Could not start MCP server: {exc}"

    _PROCESS = process
    mcp_path = "/sse" if http_protocol == "sse" else "/mcp"
    local_url = f"http://{host}:{port}{mcp_path}"
    STATE.update({
        "running": True,
        "mode": transport,
        "local_url": local_url,
        "public_url": "",
        "last_status": "starting",
        "last_line": "",
        "pid": process.pid,
    })
    threading.Thread(target=_watch_output, args=(process,), daemon=True).start()
    return f"MCP server starting ({transport}, pid {process.pid})."


def stop() -> str:
    """Stop the host MCP server process."""
    global _PROCESS
    if not _PROCESS or _PROCESS.poll() is not None:
        _set_stopped("stopped")
        _PROCESS = None
        return "MCP server is not running."
    pid = _PROCESS.pid
    _PROCESS.terminate()
    _set_stopped("stopping")
    return f"MCP server stopping (pid {pid})."
