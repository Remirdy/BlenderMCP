"""Blender operators for the Remirdy MCP add-on."""
from __future__ import annotations

import bpy

from . import bridge_server, mcp_process


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


class REMIRDY_OT_start_mcp_http(bpy.types.Operator):
    bl_idname = "remirdy.start_mcp_http"
    bl_label = "Start Local HTTP MCP"
    bl_description = "Start the local streamable HTTP MCP server for local AI clients"

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        msg = mcp_process.start(
            project_path=prefs.mcp_project_path,
            python_executable=prefs.mcp_python_executable,
            transport="http",
            host="127.0.0.1",
            port=prefs.mcp_http_port,
            http_protocol="streamable-http",
        )
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class REMIRDY_OT_start_mcp_https(bpy.types.Operator):
    bl_idname = "remirdy.start_mcp_https"
    bl_label = "Start ChatGPT HTTPS"
    bl_description = "Start the MCP server and expose a ChatGPT-ready HTTPS /sse URL"

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        msg = mcp_process.start(
            project_path=prefs.mcp_project_path,
            python_executable=prefs.mcp_python_executable,
            transport="https",
            host="127.0.0.1",
            port=prefs.mcp_http_port,
            tunnel=prefs.mcp_tunnel,
            public_url=prefs.mcp_public_url,
            http_protocol="sse",
        )
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class REMIRDY_OT_stop_mcp_server(bpy.types.Operator):
    bl_idname = "remirdy.stop_mcp_server"
    bl_label = "Stop MCP Server"
    bl_description = "Stop the host-side HTTP/HTTPS MCP server"

    def execute(self, context):
        msg = mcp_process.stop()
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class REMIRDY_OT_copy_mcp_url(bpy.types.Operator):
    bl_idname = "remirdy.copy_mcp_url"
    bl_label = "Copy ChatGPT HTTPS URL"
    bl_description = "Copy the public HTTPS MCP URL required by ChatGPT"

    def execute(self, context):
        url = mcp_process.STATE.get("public_url")
        if not url:
            self.report({"WARNING"}, "No ChatGPT HTTPS URL is ready yet. Click ChatGPT HTTPS and wait for https://.../sse.")
            return {"CANCELLED"}
        context.window_manager.clipboard = url
        self.report({"INFO"}, f"Copied: {url}")
        return {"FINISHED"}


CLASSES = (
    REMIRDY_OT_start_bridge,
    REMIRDY_OT_stop_bridge,
    REMIRDY_OT_render_preview,
    REMIRDY_OT_start_mcp_http,
    REMIRDY_OT_start_mcp_https,
    REMIRDY_OT_stop_mcp_server,
    REMIRDY_OT_copy_mcp_url,
)
