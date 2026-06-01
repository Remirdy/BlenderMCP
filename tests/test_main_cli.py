"""Tests for the remirdy-mcp command-line transport helpers."""
from __future__ import annotations

import argparse

import pytest

from server import main


def test_parse_args_defaults_to_stdio():
    args = main.parse_args([])
    assert args.transport == "stdio"
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.mcp_path == "/mcp"


def test_local_mcp_url_normalizes_path():
    assert main.local_mcp_url("127.0.0.1", 9000, "mcp") == "http://127.0.0.1:9000/mcp"


def test_chatgpt_mcp_url_appends_path():
    assert (
        main.chatgpt_mcp_url("https://example.ngrok-free.app", "/mcp")
        == "https://example.ngrok-free.app/mcp"
    )


def test_chatgpt_mcp_url_does_not_duplicate_path():
    assert (
        main.chatgpt_mcp_url("https://example.ngrok-free.app/mcp", "/mcp")
        == "https://example.ngrok-free.app/mcp"
    )


def test_public_url_bypasses_tunnel_startup():
    args = argparse.Namespace(
        public_url="https://remirdy.example.com",
        tunnel="none",
        host="127.0.0.1",
        port=8000,
    )
    endpoint = main.start_public_endpoint(args)
    assert endpoint.url == "https://remirdy.example.com"
    assert endpoint.process is None


def test_https_with_no_tunnel_and_no_public_url_raises():
    args = argparse.Namespace(
        public_url=None,
        tunnel="none",
        host="127.0.0.1",
        port=8000,
    )
    with pytest.raises(RuntimeError, match="requires --public-url"):
        main.start_public_endpoint(args)
