"""Import downloaded/generated assets into Blender."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ._common import call


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def import_asset_file(path: str, collection: str = "ImportedAssets") -> dict:
        """Import a GLB/glTF/FBX/OBJ/Blend file from inside the Remirdy workspace."""
        return call("import_asset_file", {"path": path, "collection": collection})

    @mcp.tool()
    def set_hdri_environment(path: str, strength: float = 0.8) -> dict:
        """Set a downloaded .hdr/.exr from the Remirdy workspace as the world environment."""
        return call("set_hdri_environment", {"path": path, "strength": strength})
