"""Remirdy Blender Studio — Blender add-on entry point.

Install this folder (zipped) via Edit > Preferences > Add-ons > Install, enable
"Remirdy Blender Studio MCP", then open the 'Remirdy MCP' sidebar tab in the 3D
viewport (press N) and click 'Start Bridge'.
"""
from __future__ import annotations

import os

import bpy

from . import operators, panels

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
    for cls in reversed(panels.CLASSES):
        bpy.utils.unregister_class(cls)
    for cls in reversed(operators.CLASSES):
        bpy.utils.unregister_class(cls)
    bpy.utils.unregister_class(RemirdyPreferences)
