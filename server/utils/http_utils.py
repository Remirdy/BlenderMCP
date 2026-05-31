"""Small stdlib HTTP helpers."""
from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_HEADERS = {"User-Agent": "Remirdy-Blender-Studio-MCP/0.1"}


def _ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 30) -> dict[str, Any] | list[Any]:
    req = urllib.request.Request(url, headers={**DEFAULT_HEADERS, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download(url: str, path: str | Path, headers: dict[str, str] | None = None, timeout: int = 120) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={**DEFAULT_HEADERS, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        path.write_bytes(resp.read())
    return str(path)


def qs(params: dict[str, Any]) -> str:
    return urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
