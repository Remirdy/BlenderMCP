"""CLI entrypoint for the reference-driven character generator."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender_addon.reference_generators.sprite_reference_character import main  # noqa: E402


if __name__ == "__main__":
    main()
