# Safety model

Remirdy is designed so an AI client gets *capabilities*, not *a Python shell*.

## No arbitrary code execution by default

- The MCP server forwards only **named operations**. Every name must exist in `blender_addon/blender_ops/registry.py`. There is no `exec`, `eval`, or "run this script" tool.
- A developer raw-Python mode is deliberately **not implemented in the request path**. The add-on exposes a preference toggle (`allow_dev_python`) as a placeholder, defaulting to **off**; enabling it does nothing until a developer explicitly wires a gated channel. This keeps the dangerous path opt-in and visible.

## Filesystem sandbox

- All server-side paths resolve through `server/utils/file_utils.py:safe_path`, which rejects traversal outside the workspace.
- All in-Blender exports resolve through `export_ops.workspace_output`, which strips directory components from filenames (`os.path.basename`) and writes only under `<workspace>/outputs/<category>/`.

## Input validation

- Tool arguments are validated against enums and ranges (`server/utils/validation.py`) before reaching Blender.
- The bridge wraps every handler in try/except and returns structured errors (with a traceback) instead of crashing Blender.

## Network surface

- The bridge binds to `127.0.0.1` only. It is not exposed to the network.
- One request per connection, newline-delimited JSON, with timeouts on both ends.

## Recommendations

- Run the MCP server with a dedicated workspace folder you are comfortable writing into.
- Review `registry.py` if you fork the project; it is the single source of truth for what the AI can do.
