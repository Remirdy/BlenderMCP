"""Blender operators for the Remirdy MCP add-on."""
from __future__ import annotations

import bpy

from . import bridge_server


class REMIRDY_OT_start_bridge(bpy.types.Operator):
    bl_idname = "remirdy.start_bridge"
    bl_label = "Start Bridge"
    bl_description = "Start the Remirdy MCP socket bridge so the MCP server can connect"

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        msg = bridge_server.start(port=prefs.port, host=prefs.bind_host, token=prefs.bridge_token)
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class REMIRDY_OT_stop_bridge(bpy.types.Operator):
    bl_idname = "remirdy.stop_bridge"
    bl_label = "Stop Bridge"
    bl_description = "Stop the Remirdy MCP socket bridge"

    def execute(self, context):
        msg = bridge_server.stop()
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class REMIRDY_OT_render_preview(bpy.types.Operator):
    bl_idname = "remirdy.render_preview"
    bl_label = "Render Preview"
    bl_description = "Render a quick preview to the workspace outputs folder"

    def execute(self, context):
        from .blender_ops import render_ops
        result = render_ops.op_render_preview({"filename": "panel_preview.png"})
        self.report({"INFO"}, f"Rendered: {result['render_path']}")
        return {"FINISHED"}


CLASSES = (REMIRDY_OT_start_bridge, REMIRDY_OT_stop_bridge, REMIRDY_OT_render_preview)
