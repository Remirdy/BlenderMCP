"""Reference image to 3D asset tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ._common import call


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def create_3d_asset_from_reference_image(
        reference_image: str,
        asset_type: str = "human_character",
        filename: str = "reference_matched_character",
        provider: str = "local",
        local_command: str = "",
        wait_seconds: int = 3600,
        target_polycount: int = 100000,
        auto_upright: bool = True,
        target_height: float = 2.7,
    ) -> dict:
        """Create a 3D asset matching a 2D reference image.

        Uses a real image-to-3D provider when configured. The default provider
        is local: set REMIRDY_LOCAL_IMAGE_TO_3D_COMMAND to a model runner that
        accepts {image} and writes {output}. If provider generation fails, the
        Blender add-on reports why and falls back to a procedural reference
        character so the workflow still produces debuggable artifacts.
        """
        return call(
            "create_3d_asset_from_reference_image",
            {
                "reference_image": reference_image,
                "asset_type": asset_type,
                "filename": filename,
                "provider": provider,
                "local_command": local_command,
                "wait_seconds": wait_seconds,
                "target_polycount": target_polycount,
                "auto_upright": auto_upright,
                "target_height": target_height,
            },
        )
