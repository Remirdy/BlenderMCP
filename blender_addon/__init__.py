"""Remirdy Blender Studio — Blender add-on entry point.

Install this folder (zipped) via Edit > Preferences > Add-ons > Install, enable
"Remirdy Blender Studio MCP", then open the 'Remirdy MCP' sidebar tab in the 3D
viewport (press N) and click 'Start Bridge'.
"""
from __future__ import annotations

import os
import sys

import bpy

from . import mcp_process, operators, panels

bl_info = {
    "name": "Remirdy Blender Studio MCP",
    "author": "Remirdy",
    "version": (0, 1, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Remirdy MCP",
    "description": "Local MCP bridge for Blender scene tools, asset export, and optional image-to-3D imports.",
    "category": "3D View",
}

ADDON_ID = __name__


class RemirdyPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    port: bpy.props.IntProperty(
        name="Bridge Port", default=8765, min=1024, max=65535,
        description="TCP port the MCP server connects to",
    )
    bind_host: bpy.props.StringProperty(
        name="Bind Host", default="127.0.0.1",
        description="Use 127.0.0.1 for local use. Use 0.0.0.0 only for token-protected remote access.",
    )
    bridge_token: bpy.props.StringProperty(
        name="Remote Token", default="", subtype="PASSWORD",
        description="Required token for remote/non-local bridge access",
    )
    workspace_path: bpy.props.StringProperty(
        name="Workspace Folder", subtype="DIR_PATH",
        default=os.path.join(os.path.expanduser("~"), "RemirdyWorkspace"),
        description="All renders and exports are written under this folder's outputs/ tree",
    )
    mcp_project_path: bpy.props.StringProperty(
        name="MCP Project Folder",
        subtype="DIR_PATH",
        default="",
        description="Folder containing server/main.py. Needed for the ChatGPT HTTPS MCP button.",
    )
    mcp_python_executable: bpy.props.StringProperty(
        name="Python",
        subtype="FILE_PATH",
        default="",
        description="Python executable used to start the host MCP server.",
    )
    mcp_http_port: bpy.props.IntProperty(
        name="MCP HTTP Port",
        default=8000,
        min=1024,
        max=65535,
        description="Local HTTP port for ChatGPT/HTTPS MCP mode.",
    )
    mcp_tunnel: bpy.props.EnumProperty(
        name="HTTPS Tunnel",
        default="auto",
        items=[
            ("auto", "Auto", "Use ngrok if available, otherwise cloudflared"),
            ("ngrok", "ngrok", "Use ngrok"),
            ("cloudflared", "cloudflared", "Use cloudflared quick tunnel"),
            ("none", "None", "Do not start a tunnel; use Public URL"),
        ],
        description="Tunnel provider for ChatGPT HTTPS MCP mode.",
    )
    mcp_public_url: bpy.props.StringProperty(
        name="Public URL",
        default="",
        description="Optional existing public HTTPS base URL. /mcp is appended by the MCP server.",
    )
    allow_dev_python: bpy.props.BoolProperty(
        name="Enable Developer Raw-Python Mode (UNSAFE)", default=False,
        description="Disabled by default. Raw Python execution is NOT exposed to the MCP unless explicitly enabled here.",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "port")
        layout.prop(self, "bind_host")
        layout.prop(self, "bridge_token")
        layout.prop(self, "workspace_path")
        layout.separator()
        layout.label(text="ChatGPT / HTTPS MCP")
        layout.prop(self, "mcp_project_path")
        layout.prop(self, "mcp_python_executable")
        layout.prop(self, "mcp_http_port")
        layout.prop(self, "mcp_tunnel")
        layout.prop(self, "mcp_public_url")
        box = layout.box()
        box.label(text="Safety", icon="LOCKED")
        box.prop(self, "allow_dev_python")
        box.label(text="Raw Python is never exposed by default; only structured ops run.")


def register():
    bpy.utils.register_class(RemirdyPreferences)
    for cls in operators.CLASSES:
        bpy.utils.register_class(cls)
    for cls in panels.CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    from . import bridge_server
    try:
        bridge_server.stop()
    except Exception:
        pass
    try:
        mcp_process.stop()
    except Exception:
        pass
    for cls in reversed(panels.CLASSES):
        bpy.utils.unregister_class(cls)
    for cls in reversed(operators.CLASSES):
        bpy.utils.unregister_class(cls)
    bpy.utils.unregister_class(RemirdyPreferences)
