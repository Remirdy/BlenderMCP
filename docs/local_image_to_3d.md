# Local Image-To-3D

Remirdy can call a local image-to-3D program and bring the result back into
Blender. The model itself is not bundled with this repository. Install it next
to the repo, point Remirdy at the command, and keep the generated model files in
your local workspace.

## Command Contract

The local command receives an image path and a target GLB path:

```bash
your-command /path/to/reference.png /path/to/output.glb
```

It should:

1. Read the image.
2. Generate a mesh and texture with the local model.
3. Write a valid `.glb` to the output path.
4. Exit with `0` only after the file exists.

Remirdy then imports that GLB, normalizes the asset in Blender, saves the Blend
file, and renders a preview.

## TripoSR Helper

The repo includes a helper for TripoSR because it has a simple command-line
runner and can export GLB.

```bash
cd /path/to/remirdy-blender-studio-mcp
./scripts/install_triposr_local.sh
```

This installs TripoSR into `../ai_models/TripoSR` by default. To use a different
folder:

```bash
REMIRDY_MODELS_DIR=/Volumes/Models ./scripts/install_triposr_local.sh
```

## Environment

Set these before starting the MCP server:

```bash
export TRIPOSR_DIR="/absolute/path/to/ai_models/TripoSR"
export REMIRDY_IMAGE_TO_3D_PROVIDER=local
export REMIRDY_LOCAL_IMAGE_TO_3D_COMMAND='bash /absolute/path/to/remirdy-blender-studio-mcp/scripts/run_triposr_to_glb.sh "{image}" "{output}"'
export REMIRDY_IMAGE_TO_3D_WAIT_SECONDS=3600
export REMIRDY_BRIDGE_TIMEOUT=3900
export REMIRDY_BRIDGE_REQUEST_TIMEOUT=3900
```

Optional tuning:

```bash
export TRIPOSR_DEVICE=cpu
export TRIPOSR_MC_RESOLUTION=192
export TRIPOSR_TEXTURE_RESOLUTION=1024
```

Lower resolution is faster and lighter. Higher resolution can look better but
uses more memory.

## Manual Test

```bash
bash scripts/run_triposr_to_glb.sh /Users/you/Desktop/reference.png /tmp/reference.glb
ls -lh /tmp/reference.glb
```

If that works, the MCP tool can use the same command.

## MCP Call

```text
create_3d_asset_from_reference_image(
  reference_image="/Users/you/Desktop/reference.png",
  asset_type="human_character",
  filename="reference_character",
  provider="local",
  wait_seconds=3600
)
```

## Fallback Behavior

If the local command is not configured or fails, the tool returns
`generation_mode="procedural_reference_fallback"` and includes `fallback_reason`.
That fallback is useful for checking Blender export and rendering, but it is not
a replacement for a real image-to-3D model.
