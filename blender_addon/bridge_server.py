"""TCP bridge that runs inside Blender.

A background thread accepts socket connections and parses newline-delimited JSON
requests. Because the Blender Python API is only safe on the main thread, each
request is queued and executed by a `bpy.app.timers` callback on the main
thread; the worker thread waits for the result and writes the JSON response.
"""
from __future__ import annotations

import json
import queue
import socket
import threading
import traceback
import os

import bpy

from .blender_ops import registry

HOST = "127.0.0.1"
PORT = 8765
REQUEST_TIMEOUT = int(os.environ.get("REMIRDY_BRIDGE_REQUEST_TIMEOUT", "3900"))

# (request_dict, response_holder, event)
_job_queue: "queue.Queue" = queue.Queue()
_server_thread = None
_stop_flag = threading.Event()
_timer_registered = False

# Status surfaced in the UI panel.
STATE = {"running": False, "last_op": "—", "last_status": "idle", "host": HOST, "port": PORT, "token_required": False}


def _configured_token():
    token = os.environ.get("REMIRDY_BRIDGE_TOKEN", "")
    try:
        prefs = bpy.context.preferences.addons.get("remirdy_blender_studio")
        if prefs and getattr(prefs.preferences, "bridge_token", ""):
            token = prefs.preferences.bridge_token
    except Exception:
        pass
    return token


# --------------------------------------------------------------------------- #
# Main-thread executor (timer)
# --------------------------------------------------------------------------- #
def _process_jobs():
    processed = 0
    while not _job_queue.empty() and processed < 8:
        request, holder, event = _job_queue.get()
        op = request.get("op", "")
        try:
            result = registry.dispatch(op, request.get("params", {}))
            holder["response"] = {"ok": True, "id": request.get("id"), "result": result}
            STATE["last_status"] = "ok"
        except Exception as exc:  # noqa: BLE001 — report any failure to the client
            holder["response"] = {
                "ok": False, "id": request.get("id"),
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            }
            STATE["last_status"] = f"error: {exc}"
        STATE["last_op"] = op
        event.set()
        processed += 1
    return 0.05 if STATE["running"] else None  # reschedule interval (seconds)


# --------------------------------------------------------------------------- #
# Worker thread
# --------------------------------------------------------------------------- #
def _handle_client(conn: socket.socket):
    with conn:
        conn.settimeout(REQUEST_TIMEOUT)
        buffer = bytearray()
        try:
            while b"\n" not in buffer:
                chunk = conn.recv(65536)
                if not chunk:
                    return
                buffer.extend(chunk)
            line, _, _ = bytes(buffer).partition(b"\n")
            request = json.loads(line.decode("utf-8"))
            expected = _configured_token()
            if expected and request.get("token") != expected:
                conn.sendall((json.dumps({"ok": False, "error": "unauthorized bridge token"}) + "\n").encode())
                return
        except Exception as exc:  # malformed request
            conn.sendall((json.dumps({"ok": False, "error": f"bad request: {exc}"}) + "\n").encode())
            return

        holder: dict = {}
        event = threading.Event()
        _job_queue.put((request, holder, event))
        if not event.wait(timeout=REQUEST_TIMEOUT):
            response = {"ok": False, "id": request.get("id"), "error": "timeout waiting for Blender main thread"}
        else:
            response = holder["response"]
        conn.sendall((json.dumps(response) + "\n").encode("utf-8"))


def _serve():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((STATE["host"], STATE["port"]))
        srv.listen(5)
        srv.settimeout(1.0)
        while not _stop_flag.is_set():
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=_handle_client, args=(conn,), daemon=True).start()


# --------------------------------------------------------------------------- #
# Public start/stop
# --------------------------------------------------------------------------- #
def start(port: int = PORT, host: str = HOST, token: str = "") -> str:
    global _server_thread, _timer_registered
    if STATE["running"]:
        return f"Bridge already running on port {STATE['port']}."
    if host not in ("127.0.0.1", "localhost", "::1") and not (token or _configured_token()):
        return "Refusing remote bridge without a token. Set Remote Token first."
    STATE["host"] = host
    STATE["port"] = port
    STATE["token_required"] = bool(token or _configured_token())
    _stop_flag.clear()
    _server_thread = threading.Thread(target=_serve, daemon=True)
    _server_thread.start()
    if not _timer_registered:
        bpy.app.timers.register(_process_jobs, persistent=True)
        _timer_registered = True
    STATE["running"] = True
    STATE["last_status"] = "listening"
    return f"Remirdy bridge listening on {host}:{port}."


def stop() -> str:
    global _timer_registered
    _stop_flag.set()
    STATE["running"] = False
    STATE["last_status"] = "stopped"
    _timer_registered = False
    return "Remirdy bridge stopped."
