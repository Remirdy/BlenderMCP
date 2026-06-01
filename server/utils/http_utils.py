"""Small stdlib HTTP helpers."""
from __future__ import annotations

import json
import ssl
import urllib.error
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


def request_json(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 60,
) -> dict[str, Any] | list[Any]:
    """Generic JSON request supporting GET/POST/PUT/DELETE.

    Raises HTTPError with the decoded body attached so callers can surface
    provider-specific error messages instead of an opaque 4xx/5xx.
    """
    data = None
    req_headers = {**DEFAULT_HEADERS, **(headers or {})}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:  # type: ignore[attr-defined]
        detail = exc.read().decode("utf-8", errors="replace")
        raise urllib.error.HTTPError(  # type: ignore[attr-defined]
            exc.url, exc.code, f"{exc.reason}: {detail}", exc.headers, None
        ) from exc


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None, timeout: int = 60):
    return request_json(url, "POST", headers, payload, timeout)


def qs(params: dict[str, Any]) -> str:
    return urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
