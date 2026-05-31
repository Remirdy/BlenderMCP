"""Sidebar UI panel: 'Remirdy MCP'."""
from __future__ import annotations

import bpy

from . import bridge_server


class REMIRDY_PT_panel(bpy.types.Panel):
    bl_label = "Remirdy MCP"
    bl_idname = "REMIRDY_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Remirdy MCP"

    def draw(self, context):
        layout = self.layout
        prefs = context.preferences.addons[__package__].preferences
        state = bridge_server.STATE

        box = layout.box()
        row = box.row()
        running = state["running"]
        row.label(text="Bridge", icon="RADIOBUT_ON" if running else "RADIOBUT_OFF")
        row.label(text="Online" if running else "Offline")
        box.label(text=f"Host: {state['host']}")
        box.label(text=f"Port: {state['port']}")
        box.label(text=f"Token: {'Required' if state['token_required'] else 'Not required'}")

        col = layout.column(align=True)
        col.prop(prefs, "bind_host")
        col.prop(prefs, "port")
        col.prop(prefs, "bridge_token")
        col.prop(prefs, "workspace_path")

        row = layout.row(align=True)
        row.operator("remirdy.start_bridge", icon="PLAY")
        row.operator("remirdy.stop_bridge", icon="PAUSE")

        layout.separator()
        layout.operator("remirdy.render_preview", icon="RENDER_STILL")

        layout.separator()
        info = layout.box()
        info.label(text="Last command", icon="CONSOLE")
        info.label(text=f"op: {state['last_op']}")
        info.label(text=f"status: {state['last_status']}")


CLASSES = (REMIRDY_PT_panel,)
