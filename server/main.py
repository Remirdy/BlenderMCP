"""CLI entry point for Remirdy Blender Studio MCP."""
from __future__ import annotations

import argparse
import atexit
import json
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass
from typing import Sequence

from .mcp_server import build_server

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_MCP_PATH = "/mcp"
DEFAULT_SSE_PATH = "/sse"


@dataclass(frozen=True)
class PublicEndpoint:
    url: str
    process: subprocess.Popen[str] | None = None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="remirdy-mcp",
        description="Run the Remirdy Blender Studio MCP server.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http", "https"),
        default="stdio",
        help=(
            "stdio for desktop MCP clients, http for local streamable HTTP, "
            "or https to expose a ChatGPT-ready public MCP URL through a tunnel."
        ),
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="HTTP bind host.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="HTTP bind port.")
    parser.add_argument(
        "--mcp-path",
        default=DEFAULT_MCP_PATH,
        help="Streamable HTTP MCP path. ChatGPT should receive this path.",
    )
    parser.add_argument(
        "--http-protocol",
        choices=("streamable-http", "sse"),
        default="streamable-http",
        help="Remote MCP HTTP protocol. ChatGPT supports both; SSE is useful for compatibility.",
    )
    parser.add_argument(
        "--tunnel",
        choices=("auto", "ngrok", "cloudflared", "none"),
        default="auto",
        help="Tunnel provider for --transport https.",
    )
    parser.add_argument(
        "--public-url",
        help=(
            "Use an already-public HTTPS base URL instead of starting a tunnel. "
            "The MCP path is appended automatically."
        ),
    )
    return parser.parse_args(argv)


def _normalize_path(path: str) -> str:
    if not path.startswith("/"):
        path = f"/{path}"
    return path.rstrip("/") or "/"


def local_mcp_url(host: str, port: int, mcp_path: str) -> str:
    return f"http://{host}:{port}{_normalize_path(mcp_path)}"


def chatgpt_mcp_url(base_url: str, mcp_path: str) -> str:
    base = base_url.rstrip("/")
    path = _normalize_path(mcp_path)
    if base.endswith(path):
        return base
    return f"{base}{path}"


def _read_ngrok_public_url(timeout: float = 10.0) -> str | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=1) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception:
            time.sleep(0.4)
            continue
        for tunnel in data.get("tunnels", []):
            public_url = tunnel.get("public_url", "")
            if public_url.startswith("https://"):
                return public_url
        time.sleep(0.4)
    return None


def _read_cloudflared_public_url(
    process: subprocess.Popen[str],
    timeout: float = 15.0,
) -> str | None:
    if not process.stderr:
        return None

    lines: queue.Queue[str] = queue.Queue()

    def read_stderr() -> None:
        for line in process.stderr or []:
            lines.put(line)

    threading.Thread(target=read_stderr, daemon=True).start()
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            line = lines.get(timeout=0.4)
        except queue.Empty:
            line = ""
        if "https://" in line and "trycloudflare.com" in line:
            for part in line.split():
                if part.startswith("https://") and "trycloudflare.com" in part:
                    return part.strip()
        if process.poll() is not None:
            return None
    return None


def _start_ngrok(port: int) -> PublicEndpoint:
    ngrok = shutil.which("ngrok")
    if not ngrok:
        raise RuntimeError("ngrok is not installed or not in PATH.")
    process = subprocess.Popen(
        [ngrok, "http", str(port), "--log=stdout"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    public_url = _read_ngrok_public_url()
    if not public_url:
        process.terminate()
        raise RuntimeError("ngrok started, but no HTTPS tunnel URL was discovered.")
    return PublicEndpoint(public_url, process)


def _start_cloudflared(host: str, port: int) -> PublicEndpoint:
    cloudflared = shutil.which("cloudflared")
    if not cloudflared:
        raise RuntimeError("cloudflared is not installed or not in PATH.")
    process = subprocess.Popen(
        [cloudflared, "tunnel", "--url", f"http://{host}:{port}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    public_url = _read_cloudflared_public_url(process)
    if not public_url:
        process.terminate()
        raise RuntimeError("cloudflared started, but no HTTPS tunnel URL was discovered.")
    return PublicEndpoint(public_url, process)


def start_public_endpoint(args: argparse.Namespace) -> PublicEndpoint:
    if args.public_url:
        return PublicEndpoint(args.public_url)
    if args.tunnel == "none":
        raise RuntimeError("--transport https requires --public-url when --tunnel none is used.")

    providers = ("ngrok", "cloudflared") if args.tunnel == "auto" else (args.tunnel,)
    errors: list[str] = []
    for provider in providers:
        try:
            if provider == "ngrok":
                return _start_ngrok(args.port)
            if provider == "cloudflared":
                return _start_cloudflared(args.host, args.port)
        except RuntimeError as exc:
            errors.append(f"{provider}: {exc}")

    joined = "; ".join(errors) if errors else "no tunnel providers attempted"
    raise RuntimeError(
        "Could not create a public HTTPS tunnel. Install ngrok or cloudflared, "
        "or pass --public-url with your own HTTPS endpoint. "
        f"Details: {joined}"
    )


def _register_cleanup(process: subprocess.Popen[str] | None) -> None:
    if process is None:
        return

    def cleanup() -> None:
        if process.poll() is None:
            process.terminate()

    atexit.register(cleanup)


def _print_http_banner(*, local_url: str, chatgpt_url: str | None = None) -> None:
    print("", file=sys.stderr)
    print("Remirdy Blender Studio MCP is running.", file=sys.stderr)
    print(f"Local MCP URL: {local_url}", file=sys.stderr)
    if chatgpt_url:
        print("", file=sys.stderr)
        print("ChatGPT custom MCP URL:", file=sys.stderr)
        print(chatgpt_url, file=sys.stderr)
        print("", file=sys.stderr)
        print("Paste this URL in ChatGPT Apps -> Create app -> MCP server endpoint.", file=sys.stderr)
    print("", file=sys.stderr)


def run(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    if args.transport == "stdio":
        build_server().run("stdio")
        return

    mcp_path = _normalize_path(DEFAULT_SSE_PATH if args.http_protocol == "sse" else args.mcp_path)
    local_url = local_mcp_url(args.host, args.port, mcp_path)
    chatgpt_url = None

    if args.transport == "https":
        try:
            endpoint = start_public_endpoint(args)
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc
        _register_cleanup(endpoint.process)
        chatgpt_url = chatgpt_mcp_url(endpoint.url, mcp_path)

    _print_http_banner(local_url=local_url, chatgpt_url=chatgpt_url)
    server = build_server(host=args.host, port=args.port, mcp_path=mcp_path)
    if args.http_protocol == "sse":
        server.run("sse", mount_path=mcp_path)
    else:
        server.run("streamable-http")


if __name__ == "__main__":
    run()
