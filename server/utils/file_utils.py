"""Workspace-restricted file utilities.

All file operations performed by the MCP server are confined to a single
workspace root for safety. Paths that try to escape the workspace are rejected.
"""
from __future__ import annotations

import os
from pathlib import Path

# The workspace root can be overridden with an environment variable. By default
# it lives next to the repository in a `workspace/` folder.
DEFAULT_WORKSPACE = Path(
    os.environ.get(
        "REMIRDY_WORKSPACE",
        str(Path(__file__).resolve().parents[2] / "workspace"),
    )
).resolve()

OUTPUT_SUBDIRS = ("blends", "renders", "exports", "thumbnails")


def get_workspace() -> Path:
    """Return the workspace root, creating the standard output tree if needed."""
    root = DEFAULT_WORKSPACE
    root.mkdir(parents=True, exist_ok=True)
    outputs = root / "outputs"
    for sub in OUTPUT_SUBDIRS:
        (outputs / sub).mkdir(parents=True, exist_ok=True)
    return root


def safe_path(relative: str) -> Path:
    """Resolve `relative` inside the workspace, refusing path traversal.

    Raises:
        ValueError: if the resolved path escapes the workspace root.
    """
    root = get_workspace()
    candidate = (root / relative).resolve()
    if root not in candidate.parents and candidate != root:
        raise ValueError(
            f"Path '{relative}' escapes the workspace sandbox ({root})."
        )
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def output_path(category: str, filename: str) -> Path:
    """Return a path inside outputs/<category>/<filename>."""
    if category not in OUTPUT_SUBDIRS:
        raise ValueError(
            f"Unknown output category '{category}'. "
            f"Expected one of {OUTPUT_SUBDIRS}."
        )
    return safe_path(f"outputs/{category}/{filename}")
