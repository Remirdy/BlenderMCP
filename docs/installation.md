# Installation

## Requirements

- Blender 3.6 LTS or newer (4.x supported; Eevee Next/Cycles auto-detected).
- Python 3.10+ for the MCP server.
- An MCP-capable client (Claude Desktop, Cursor, etc.).

## 1. Install the MCP server

```bash
cd remirdy-blender-studio-mcp
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Verify it imports:

```bash
python -c "import server.mcp_server as m; m.build_server(); print('server OK')"
```

## 2. Build and install the Blender add-on

```bash
python scripts/package_addon.py    # -> dist/remirdy_blender_studio.zip
```

In Blender:

1. **Edit → Preferences → Add-ons → Install…**
2. Choose `dist/remirdy_blender_studio.zip`.
3. Tick **Remirdy Blender Studio MCP**.
4. Expand the add-on to set the **Workspace Folder** (default `~/RemirdyWorkspace`) and **Bridge Port** (default `8765`).

## 3. Start the bridge

Press **N** in the 3D viewport → **Remirdy MCP** tab → **Start Bridge**. The status should read *Online*.

## 4. Register the MCP server with your client

Claude Desktop example (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "remirdy-blender-studio": {
      "command": "python",
      "args": ["-m", "server.main"],
      "cwd": "/absolute/path/to/remirdy-blender-studio-mcp",
      "env": { "REMIRDY_WORKSPACE": "/absolute/path/to/RemirdyWorkspace" }
    }
  }
}
```

Point `REMIRDY_WORKSPACE` at the **same** folder you set in the add-on so the server and Blender agree on output paths.

Restart the client, then ask it to `connect_blender`.

## Optional integrations

Set only the keys you need:

```bash
export SKETCHFAB_API_TOKEN="..."
export RODIN_API_KEY="..."
export HUNYUAN3D_API_KEY="..."
export HUNYUAN3D_ENDPOINT="..."
export REMIRDY_TELEMETRY="off"      # off | local | anonymous
export REMIRDY_BRIDGE_TOKEN="..."   # required for remote/non-local bridge access
```

For remote Blender hosts, set **Bind Host** to `0.0.0.0` in the add-on only after
setting a **Remote Token**. The bridge refuses non-local binding without a token.
