# Contributing to Remirdy Blender Studio MCP

Thank you for your interest in contributing! This guide covers the dev setup, code structure, and how to add new capabilities.

---

## Dev environment setup

```bash
# 1. Clone the repo
git clone https://github.com/remirdy/remirdy-blender-studio-mcp.git
cd remirdy-blender-studio-mcp

# 2. Create a virtual environment (Python 3.10+)
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install in editable mode with dev deps
pip install -e ".[dev]"

# 4. Copy .env.example and add your API keys
cp .env.example .env
```

---

## Running the tests

```bash
python -m pytest tests/ -v
```

All tests in `tests/` run without Blender — they cover the MCP server side only. Blender-specific ops are tested manually by loading the add-on.

---

## Code structure

```
remirdy-blender-studio-mcp/
├── server/                  # MCP server (runs on the host)
│   ├── main.py              # Entry point (remirdy-mcp CLI)
│   ├── mcp_server.py        # MCP tool registration
│   ├── bridge_client.py     # TCP socket client → Blender bridge
│   ├── tools/               # One module per tool category
│   ├── providers/           # Image-to-3D provider adapters
│   └── utils/               # Shared helpers (psd_utils, ai_vision, …)
├── blender_addon/           # Blender add-on (runs inside Blender)
│   ├── bridge_server.py     # TCP socket server inside Blender
│   └── blender_ops/         # Operation implementations (uses bpy)
│       └── registry.py      # Maps op names → handler functions
├── tests/                   # Server-side pytest suite
├── examples/                # Example prompts and workflows
└── docs/                    # Extended documentation
```

---

## How to add a new MCP tool

1. **Add a Blender operation** in the appropriate `blender_addon/blender_ops/` module (e.g. `scene_ops.py`).
2. **Register it** in `blender_addon/blender_ops/registry.py` — add an entry mapping the op name string to your handler function.
3. **Add a server-side tool** in `server/tools/` (pick the matching category file or create a new one).
4. **Register the tool** in `server/mcp_server.py` using the `@mcp.tool()` decorator pattern.
5. **Write a test** in `tests/test_registry_completeness.py` to verify the module imports.
6. **Document it** in `docs/tool_reference.md` and optionally add an example to `examples/prompts/`.

### Minimal server tool example

```python
# server/tools/my_tools.py
from ._common import send_op

async def my_new_tool(param_a: str, param_b: float = 1.0) -> dict:
    """One-line description of what this tool does."""
    return await send_op("my_new_operation", {"param_a": param_a, "param_b": param_b})
```

```python
# server/mcp_server.py — add inside the server setup block:
@mcp.tool()
async def my_new_tool(param_a: str, param_b: float = 1.0) -> str:
    """One-line description shown in the MCP client."""
    result = await tools.my_tools.my_new_tool(param_a, param_b)
    return json.dumps(result)
```

---

## How to add a new image-to-3D provider

1. Create a class in `server/providers/image_to_3d.py` that subclasses `ImageTo3DProvider`.
2. Implement `name`, `is_configured()`, `missing_config()`, and `generate()`.
3. Instantiate it in `server/providers/registry.py` and add it to `_PROVIDERS_LIST`.
4. Add its API key env var to `.env.example` and `docs/`.

---

## Testing guidelines

- Keep tests in `tests/` runnable without Blender (`bpy` unavailable).
- Mock all external API calls (Gemini, Meshy, etc.) — never make real network requests in tests.
- Use `monkeypatch` to control environment variables; the `clear_gemini_env` autouse fixture handles Gemini keys automatically.
- Aim for tests that verify behaviour, not implementation details.

---

## Pull request process

1. Fork the repo and create a feature branch: `git checkout -b feature/my-feature`.
2. Make your changes and add/update tests.
3. Run `python -m pytest tests/ -v` — all tests must pass.
4. Run `python -m py_compile` on any new Python files to catch syntax errors.
5. Open a PR against `main` with a clear description of what changed and why.

---

## Questions?

Open an [issue](https://github.com/remirdy/remirdy-blender-studio-mcp/issues) — we're happy to help.
