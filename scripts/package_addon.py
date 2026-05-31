"""Package the Blender add-on into an installable zip.

The zip's top-level folder MUST be `remirdy_blender_studio` so Blender registers
the add-on preferences under that module name.

Usage:
    python scripts/package_addon.py
Produces: dist/remirdy_blender_studio.zip
"""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "blender_addon"
OUT_DIR = ROOT / "dist"
MODULE = "remirdy_blender_studio"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"{MODULE}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in SRC.rglob("*.py"):
            arc = Path(MODULE) / path.relative_to(SRC)
            zf.write(path, arc.as_posix())
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
