# Remirdy Blender MCP

Remirdy Blender MCP is a local bridge between an MCP client and Blender. It lets
the client ask Blender for structured work: create scenes, build simple assets,
inspect the current file, render previews, export GLB/FBX/OBJ files, and run a
local image-to-3D pipeline when one is installed.

This repository intentionally keeps Blender control and model generation
separate:

- The MCP server speaks to Blender through a small socket bridge.
- Blender only runs named operations that are registered in the add-on.
- Local image-to-3D is an optional dependency. The model weights are not stored
  in this repo.
- If no local image-to-3D runner is configured, the reference-image tool falls
  back to a procedural character generator and reports why the local runner was
  skipped.

The goal is a workflow that is honest and easy to debug. If a model is missing,
the tool says so. If a render fails, the file paths and logs stay local. Nothing
tries to hide a placeholder behind a big claim.

## What This Can Do

- Start a Blender bridge and receive MCP tool calls.
- Build procedural game scenes, interiors, architecture blockouts, products and
  stylized props.
- Build a playable game-environment blockout from a reference image by sampling
  its palette and inferring a broad theme.
- Create a rigged starter humanoid character with named parts and simple
  animation clips.
- Import local generated models, auto-upright them, normalize their scale, and
  frame a clean preview camera.
- Render preview images.
- Export `.blend`, `.glb`, `.fbx` and `.obj` files under a workspace folder.
- Run a local image-to-3D command, wait for it to finish, import the returned
  GLB into Blender, save the `.blend`, and render a preview.

## What This Does Not Bundle

This repo does not include TripoSR, InstantMesh, TRELLIS, Hunyuan3D, Rodin, or
any other model weights. Those projects are large, change independently, and may
have their own licenses and hardware requirements.

For the local image-to-3D path, this repo ships two helper scripts:

- `scripts/install_triposr_local.sh`: clones and installs TripoSR beside the
  repo.
- `scripts/run_triposr_to_glb.sh`: runs TripoSR for one image and copies the
  generated `mesh.glb` to the output path expected by the MCP tool.

TripoSR is a good first local backend because it is open source and has a simple
command-line runner. On a Mac it will usually run on CPU unless you customize the
PyTorch setup, so expect it to be much slower than a hosted GPU service.

Important: TripoSR is not a magic "concept art to production character" button.
It can produce useful rough meshes from clean single-object images, but anime
sprites, multi-pose sheets, weapons, loose coats, hair spikes, and black
backgrounds are hard cases. For production-level characters, use this MCP as the
orchestrator and plug in a stronger backend such as TRELLIS, Hunyuan3D,
InstantMesh, Rodin, or another service with multi-view generation, texture
baking, retopo and rigging.

## Repository Layout

```text
blender_addon/                Blender add-on and in-Blender operation registry
blender_addon/blender_ops/    Scene, asset, render, export and image-to-3D ops
server/                       MCP server and tool definitions
scripts/                      Packaging, local TripoSR install and wrapper scripts
docs/                         Setup notes, safety notes and tool reference
examples/                     Prompt examples for common workflows
```

Generated files are written under `REMIRDY_WORKSPACE`, which defaults to
`~/RemirdyWorkspace`.

## Requirements

- Python 3.10 or newer for the MCP server.
- Blender 3.6 or newer. The current local test was done with Blender 5.1.2.
- An MCP-capable client such as Claude Desktop, Cursor, ChatGPT/Codex, or any
  client that can start a stdio MCP server.
- Optional: TripoSR for local image-to-3D.

## Install The MCP Server

```bash
cd /path/to/remirdy-blender-studio-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Install The Blender Add-On

Package the add-on:

```bash
python scripts/package_addon.py
```

Then in Blender:

1. Open `Edit -> Preferences -> Add-ons`.
2. Click `Install...`.
3. Select `dist/remirdy_blender_studio.zip`.
4. Enable `Remirdy Blender Studio MCP`.
5. In the 3D viewport, press `N`.
6. Open the `Remirdy MCP` sidebar tab.
7. Set the workspace folder if you want a custom location.
8. Click `Start Bridge`.

The default bridge is local only: `127.0.0.1:8765`.

## Connect An MCP Client

Example MCP config:

```json
{
  "mcpServers": {
    "remirdy-blender": {
      "command": "python",
      "args": ["-m", "server.main"],
      "cwd": "/absolute/path/to/remirdy-blender-studio-mcp",
      "env": {
        "REMIRDY_WORKSPACE": "/Users/you/RemirdyWorkspace"
      }
    }
  }
}
```

After the client starts the server, call:

```text
connect_blender
```

If Blender is open and the bridge is running, the tool should return a small
`pong` response.

## Local Image-To-3D Setup

The image-to-3D tool needs a local command that follows this contract:

```text
command /path/to/input-image.png /path/to/output.glb
```

The command must write a valid GLB to the second path and exit with code `0`.

### Option A: Use The TripoSR Helper

From the repo root:

```bash
./scripts/install_triposr_local.sh
```

This clones TripoSR into a sibling folder:

```text
../ai_models/TripoSR
```

It also creates a Python virtual environment inside the TripoSR folder and
installs the dependencies listed by that project.

Then export these environment variables before starting the MCP server:

```bash
export TRIPOSR_DIR="/absolute/path/to/ai_models/TripoSR"
export REMIRDY_IMAGE_TO_3D_PROVIDER=local
export REMIRDY_LOCAL_IMAGE_TO_3D_COMMAND='bash /absolute/path/to/remirdy-blender-studio-mcp/scripts/run_triposr_to_glb.sh "{image}" "{output}"'
export REMIRDY_IMAGE_TO_3D_WAIT_SECONDS=3600
export REMIRDY_BRIDGE_TIMEOUT=3900
export REMIRDY_BRIDGE_REQUEST_TIMEOUT=3900
```

Then start your MCP client and Blender bridge normally.

### Test TripoSR By Hand

```bash
cd /absolute/path/to/remirdy-blender-studio-mcp
bash scripts/run_triposr_to_glb.sh /Users/you/Desktop/reference.png /tmp/reference.glb
```

If the script works, `/tmp/reference.glb` should exist.

### Use It Through MCP

Call:

```text
create_3d_asset_from_reference_image(
  reference_image="/Users/you/Desktop/reference.png",
  asset_type="human_character",
  filename="reference_character",
  provider="local",
  wait_seconds=3600
)
```

The tool will:

1. Ask the configured local command to generate a GLB.
2. Wait for the command to finish.
3. Import the GLB into Blender.
4. Auto-upright the imported mesh when the longest axis is horizontal.
5. Normalize the imported model scale.
6. Save a `.blend`.
7. Frame a dedicated preview camera around the actual mesh bounds.
8. Render a preview image.
9. Return paths to the `.blend`, `.glb` and preview.

If the local command is missing or fails, the response includes
`fallback_reason`. The tool then creates a procedural reference character so
there is still something to inspect in Blender.

### Create A Game Environment From An Image

Use:

```text
create_game_environment_from_reference_image(
  reference_image="/Users/you/Desktop/environment.png",
  style="mobile_stylized",
  size="medium",
  isometric_camera=true
)
```

The tool reads the reference palette, infers a broad theme such as `nature`,
`urban`, `waterfront`, `sci_fi`, `desert`, or `stylized`, then creates a
playable procedural blockout with lighting, materials, camera, and an optional
in-scene reference billboard. This is meant for game-ready starting layouts and
art direction, not photogrammetry.

## Notes About Quality

Single-image reconstruction is still guesswork. A sprite sheet, front view, or
clean concept image will usually work better than a dark, cropped or heavily
stylized action pose. For characters, a neutral standing reference is easier for
the model than a fighting pose with motion effects.

If you want the best result:

- Use a high-resolution PNG.
- Keep the character fully visible.
- Avoid black-on-black edges.
- Prefer a clean background or transparent background.
- Give the model time; CPU generation can be slow.
- After generation, use Blender cleanup tools for rigging, retopo and material
  fixes.

## Common Commands

```text
connect_blender
get_scene_summary
create_scene_from_prompt
create_3d_asset_from_reference_image
scene_quality_check
auto_fix_scene
render_preview
export_glb
```

Example:

```text
Create a small stylized workshop scene with a wooden desk, tools, shelves,
warm lighting, a camera, and export it as a Unity-ready GLB.
```

## Safety Model

The default bridge does not expose arbitrary Python execution. The MCP server
sends operation names and parameters. Blender dispatches those names through
`blender_addon/blender_ops/registry.py`.

File output is kept under the configured workspace. Imports are expected to come
from trusted local paths. If you expose the bridge outside localhost, set a
bridge token first.

See `docs/safety.md` for more detail.

## Troubleshooting

| Problem | What to check |
|---|---|
| `Could not reach the Blender bridge` | Blender is open, the add-on is enabled, and `Start Bridge` was clicked. |
| Local image-to-3D falls back | Check `fallback_reason`, `TRIPOSR_DIR`, and `REMIRDY_LOCAL_IMAGE_TO_3D_COMMAND`. |
| TripoSR is very slow | You are probably running on CPU. Lower `TRIPOSR_MC_RESOLUTION` or use a GPU machine. |
| No GLB appears | Run `scripts/run_triposr_to_glb.sh` by hand and inspect its terminal output. |
| Render is empty | Run `setup_camera` or `auto_fix_scene`, then render again. |
| Export fails | Confirm Blender's glTF/FBX/OBJ import-export add-ons are available. |

## Environment Variables

| Variable | Purpose |
|---|---|
| `REMIRDY_WORKSPACE` | Output folder for blends, renders, exports and temp files. |
| `REMIRDY_IMAGE_TO_3D_PROVIDER` | Use `local` for the local runner. |
| `REMIRDY_LOCAL_IMAGE_TO_3D_COMMAND` | Command template called by Blender. Supports `{image}`, `{output}`, `{workdir}`. |
| `REMIRDY_IMAGE_TO_3D_WAIT_SECONDS` | Max time to wait for image-to-3D generation. |
| `REMIRDY_BRIDGE_TIMEOUT` | MCP server socket timeout. |
| `REMIRDY_BRIDGE_REQUEST_TIMEOUT` | Blender bridge request timeout. |
| `TRIPOSR_DIR` | Path to the local TripoSR checkout. |
| `TRIPOSR_PYTHON` | Optional path to the Python executable used for TripoSR. |
| `TRIPOSR_DEVICE` | `cpu`, `cuda:0`, or another PyTorch device string. |
| `TRIPOSR_MC_RESOLUTION` | Marching-cubes resolution. Lower is faster, higher is heavier. |
| `TRIPOSR_TEXTURE_RESOLUTION` | Texture atlas size for TripoSR's baked texture path. |

## Development

Run a quick syntax check:

```bash
python3 -m py_compile \
  blender_addon/blender_ops/image_to_3d_ai.py \
  blender_addon/blender_ops/reference_asset_ops.py \
  blender_addon/reference_generators/sprite_reference_character.py \
  server/tools/reference_asset_tools.py
```

Build the add-on zip:

```bash
python scripts/package_addon.py
```

Run the procedural reference-character generator directly:

```bash
/Applications/Blender.app/Contents/MacOS/Blender \
  --background \
  --python scripts/create_sprite_reference_3d_character.py
```

## License

MIT. Check the licenses of any local image-to-3D model you install beside this
repo before using its output commercially.
