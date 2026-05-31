"""Socket client that talks to the Blender add-on bridge.

Protocol
--------
The server and the in-Blender bridge exchange newline-delimited JSON messages
over a plain TCP socket on localhost.

Request:  {"op": "<operation>", "params": {...}, "id": "<uuid>"}\n
Response: {"ok": true, "id": "...", "result": {...}}\n
          {"ok": false, "id": "...", "error": "message"}\n

The MCP server never executes Blender Python directly; it only sends structured
operation names that the bridge validates against its own registry. This keeps
arbitrary code execution out of the default surface area.
"""
from __future__ import annotations

import json
import os
import socket
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from .utils.logging_utils import get_logger

log = get_logger("remirdy.bridge")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
RECV_CHUNK = 65536


@dataclass
class BridgeConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    timeout: float = float(os.environ.get("REMIRDY_BRIDGE_TIMEOUT", "3900"))
    token: str = ""


class BridgeError(RuntimeError):
    """Raised when the Blender bridge reports an error or is unreachable."""


class BlenderBridgeClient:
    """Thread-safe client for a single Blender bridge connection."""

    def __init__(self, config: Optional[BridgeConfig] = None) -> None:
        self.config = config or BridgeConfig()
        self._lock = threading.Lock()
        self._connected = False

    # -- connection -------------------------------------------------------
    def connect(self, host: Optional[str] = None, port: Optional[int] = None, token: Optional[str] = None) -> dict:
        if host:
            self.config.host = host
        if port:
            self.config.port = port
        if token is not None:
            self.config.token = token
        elif not self.config.token:
            self.config.token = os.environ.get("REMIRDY_BRIDGE_TOKEN", "")
        # A connection is validated by a ping rather than a persistent socket;
        # we open a fresh short-lived socket per request for robustness against
        # Blender's single-threaded main loop.
        result = self.request("ping", {})
        self._connected = True
        log.info("Connected to Blender bridge at %s:%s", self.config.host, self.config.port)
        return result

    @property
    def is_connected(self) -> bool:
        return self._connected

    # -- core request -----------------------------------------------------
    def request(self, op: str, params: Optional[dict[str, Any]] = None) -> dict:
        """Send one operation to the bridge and return its result payload."""
        message = {
            "op": op,
            "params": params or {},
            "id": uuid.uuid4().hex,
        }
        token = self.config.token or os.environ.get("REMIRDY_BRIDGE_TOKEN", "")
        if token:
            message["token"] = token
        payload = (json.dumps(message) + "\n").encode("utf-8")
        with self._lock:
            try:
                with socket.create_connection(
                    (self.config.host, self.config.port), timeout=self.config.timeout
                ) as sock:
                    sock.sendall(payload)
                    data = self._recv_line(sock)
            except (ConnectionRefusedError, socket.timeout, OSError) as exc:
                self._connected = False
                raise BridgeError(
                    f"Could not reach the Blender bridge at "
                    f"{self.config.host}:{self.config.port}. "
                    f"Is Blender running with the Remirdy add-on started? ({exc})"
                ) from exc

        try:
            response = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise BridgeError(f"Malformed response from bridge: {exc}") from exc

        if not response.get("ok", False):
            raise BridgeError(response.get("error", "Unknown bridge error"))
        return response.get("result", {})

    @staticmethod
    def _recv_line(sock: socket.socket) -> bytes:
        buffer = bytearray()
        while True:
            chunk = sock.recv(RECV_CHUNK)
            if not chunk:
                break
            buffer.extend(chunk)
            if buffer.endswith(b"\n"):
                break
        return bytes(buffer).rstrip(b"\n")


# A module-level singleton keeps connection state across tool calls.
_client: Optional[BlenderBridgeClient] = None


def get_client() -> BlenderBridgeClient:
    global _client
    if _client is None:
        _client = BlenderBridgeClient()
    return _client
