"""Entry point: `python -m server.main` launches the MCP server over stdio."""
from __future__ import annotations

from .mcp_server import run

if __name__ == "__main__":
    run()
