"""Sidebar UI panel: 'Remirdy MCP'."""
from __future__ import annotations

import bpy

from . import bridge_server, mcp_process


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
        mcp_state = mcp_process.STATE
        mcp_box = layout.box()
        row = mcp_box.row()
        mcp_running = mcp_state["running"]
        row.label(text="AI / ChatGPT MCP", icon="URL" if mcp_running else "WORLD")
        row.label(text=mcp_state["last_status"])
        mcp_box.label(text=f"Mode: {mcp_state['mode']}")
        if mcp_state.get("pid"):
            mcp_box.label(text=f"PID: {mcp_state['pid']}")
        if mcp_state.get("local_url"):
            mcp_box.label(text=f"Local only: {mcp_state['local_url']}")
        public_url = mcp_state.get("public_url")
        if public_url:
            mcp_box.label(text="ChatGPT URL:")
            mcp_box.label(text=public_url)
        elif mcp_state.get("mode") == "https":
            mcp_box.label(text="Waiting for HTTPS tunnel URL...")
        else:
            mcp_box.label(text="ChatGPT requires an https://.../sse URL.")
        if mcp_state.get("last_line"):
            mcp_box.label(text=f"log: {mcp_state['last_line'][:80]}")

        row = layout.row(align=True)
        row.operator("remirdy.start_mcp_http", icon="NETWORK_DRIVE", text="Local HTTP")
        row.operator("remirdy.start_mcp_https", icon="URL", text="ChatGPT HTTPS")
        row.operator("remirdy.stop_mcp_server", icon="CANCEL", text="")
        layout.operator("remirdy.copy_mcp_url", icon="COPYDOWN", text="Copy ChatGPT HTTPS URL")

        layout.separator()
        layout.operator("remirdy.render_preview", icon="RENDER_STILL")

        layout.separator()
        info = layout.box()
        info.label(text="Last command", icon="CONSOLE")
        info.label(text=f"op: {state['last_op']}")
        info.label(text=f"status: {state['last_status']}")


CLASSES = (REMIRDY_PT_panel,)
