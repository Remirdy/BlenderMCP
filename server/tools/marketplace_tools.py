"""Asset quality scoring (MVP 6) + marketplace packaging (MVP 7) tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ._common import call


def register(mcp: FastMCP) -> None:
    # -- quality scoring --------------------------------------------------
    @mcp.tool()
    def score_asset_quality(asset_name: str = "", game: bool = True) -> dict:
        """Score a single asset (naming, material, applied scale, origin, polycount). Returns 0–100."""
        return call("score_asset_quality", {"asset_name": asset_name, "game": game})

    @mcp.tool()
    def score_asset_pack_quality(game: bool = True) -> dict:
        """Score the whole current pack with warnings and a suggested next command. Returns 0–100."""
        return call("score_asset_pack_quality", {"game": game})

    @mcp.tool()
    def check_game_readiness() -> dict:
        """Report whether the pack is game-ready (polycount, materials, applied scale)."""
        return call("check_game_readiness")

    @mcp.tool()
    def check_archviz_readiness() -> dict:
        """Report archviz readiness (materials, camera, lighting present)."""
        return call("check_archviz_readiness")

    @mcp.tool()
    def check_marketplace_readiness() -> dict:
        """Report marketplace readiness (docs, manifest, license, GLB export, thumbnails, score >= 70)."""
        return call("check_marketplace_readiness")

    @mcp.tool()
    def auto_fix_asset_pack(game: bool = True) -> dict:
        """Auto-fix the pack: apply transforms, assign missing materials, set origins, decimate high-poly, purge unused data."""
        return call("auto_fix_asset_pack", {"game": game})

    # -- marketplace packaging -------------------------------------------
    @mcp.tool()
    def package_asset_for_marketplace(holder: str = "the pack author", render_thumbnails: bool = True,
                                      fbx: bool = True, thumb_size: int = 512) -> dict:
        """Full marketplace package: source .blend, GLB/FBX exports, hero + grid renders, thumbnails,
        README, manifest, usage guide, license and HTML catalog — written under outputs/asset_packs/<pack>/."""
        return call("package_asset_for_marketplace",
                    {"holder": holder, "render_thumbnails": render_thumbnails, "fbx": fbx, "thumb_size": thumb_size})

    @mcp.tool()
    def generate_asset_pack_readme() -> dict:
        """Generate the pack README.md in the pack's documentation folder."""
        return call("generate_asset_pack_readme")

    @mcp.tool()
    def generate_asset_manifest() -> dict:
        """Generate asset_manifest.json (names, categories, polycounts, materials, thumbnails, usage)."""
        return call("generate_asset_manifest")

    @mcp.tool()
    def generate_usage_guide() -> dict:
        """Generate the Unity/Unreal/Blender usage_guide.md."""
        return call("generate_usage_guide")

    @mcp.tool()
    def generate_license_template(holder: str = "the pack author") -> dict:
        """Generate a license.txt template for the pack."""
        return call("generate_license_template", {"holder": holder})

    @mcp.tool()
    def generate_preview_renders() -> dict:
        """Render a couple of angled preview images of the pack."""
        return call("generate_preview_renders")

    @mcp.tool()
    def generate_thumbnail_sheet() -> dict:
        """Render a single contact-sheet preview of the whole pack."""
        return call("generate_thumbnail_sheet")

    @mcp.tool()
    def create_asset_catalog() -> dict:
        """Generate an HTML catalog embedding the pack thumbnails for quick browsing."""
        return call("create_asset_catalog")
