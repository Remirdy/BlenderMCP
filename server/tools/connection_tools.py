"""Connection, status and scene-inspection tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..bridge_client import BridgeError, get_client
from ._common import call


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def connect_blender(host: str = "127.0.0.1", port: int = 8765, token: str = "") -> dict:
        """Connect to the running Blender add-on bridge.

        Call this once before issuing scene commands. Requires Blender to be open
        with the Remirdy add-on installed and its bridge started.
        """
        try:
            result = get_client().connect(host=host, port=port, token=token or None)
            return {
                "ok": True,
                "op": "connect_blender",
                "message": f"Connected to Blender bridge at {host}:{port}.",
                **result,
            }
        except BridgeError as exc:
            return {
                "ok": False,
                "op": "connect_blender",
                "error": str(exc),
                "hint": "Open Blender, install/enable the Remirdy add-on, open the 'Remirdy MCP' sidebar and click 'Start Bridge'.",
            }

    @mcp.tool()
    def connect_remote_blender(host: str, port: int = 8765, token: str = "") -> dict:
        """Connect to a remote Blender bridge. Non-local bridges should require a token."""
        return connect_blender(host=host, port=port, token=token)

    @mcp.tool()
    def get_blender_status() -> dict:
        """Return Blender version, render engine and bridge health."""
        return call("get_blender_status")

    @mcp.tool()
    def get_scene_summary() -> dict:
        """Return a concise summary: object count, collections, camera, lights, materials."""
        return call("get_scene_summary")

    @mcp.tool()
    def inspect_scene() -> dict:
        """Return a detailed scene inventory with per-object transform, polycount and material info."""
        return call("inspect_scene")

    @mcp.tool()
    def clear_scene(keep_camera: bool = False, keep_lights: bool = False) -> dict:
        """Delete all objects to start fresh. Optionally keep the camera and/or lights."""
        return call("clear_scene", {"keep_camera": keep_camera, "keep_lights": keep_lights})
