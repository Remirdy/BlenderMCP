"""Professional asset-pack generation tools (MVP 1 + MVP 3 + MVP 7 entry points)."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ._common import call

ASSET_THEMES = "medieval_market | low_poly_city | cozy_cafe | modern_living_room (aliases: medieval, city, cafe, interior, mobile)"


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def create_asset_pack(theme: str = "medieval_market", count: int = 20, name: str = "") -> dict:
        """Generate a complete, original, game/render-ready prop pack.

        Builds `count` consistent assets for the theme, names them professionally,
        assigns materials, sets clean bottom-center pivots and organizes them into a
        pack collection. Returns a manifest summary.

        theme: {themes}
        """
        return call("create_asset_pack", {"theme": theme, "count": count, "name": name})

    @mcp.tool()
    def create_game_prop_pack(theme: str = "medieval_market", count: int = 20, name: str = "") -> dict:
        """Create a game-ready prop pack (e.g. stylized medieval market props)."""
        return call("create_game_prop_pack", {"theme": theme, "count": count, "name": name})

    @mcp.tool()
    def create_stylized_prop_set(theme: str = "cozy_cafe", count: int = 12, name: str = "") -> dict:
        """Create a stylized prop set (e.g. a cozy cafe set with tables, counter, cups, decor)."""
        return call("create_stylized_prop_set", {"theme": theme, "count": count, "name": name})

    @mcp.tool()
    def create_low_poly_asset_pack(count: int = 24, name: str = "") -> dict:
        """Create an original low-poly asset pack (houses, cars, trees, lamps, fences, shops…)."""
        return call("create_low_poly_asset_pack", {"count": count, "name": name})

    @mcp.tool()
    def create_mobile_game_asset_pack(count: int = 30, name: str = "") -> dict:
        """Create an optimized low-poly mobile-game city asset pack."""
        return call("create_mobile_game_asset_pack", {"count": count, "name": name})

    @mcp.tool()
    def create_interior_asset_pack(count: int = 12, style: str = "modern_living_room", name: str = "") -> dict:
        """Create an interior furniture asset pack (sofa, armchair, tables, lamps, decor, plants)."""
        return call("create_interior_asset_pack", {"count": count, "style": style, "name": name})

    @mcp.tool()
    def generate_asset_variations(asset_name: str = "", variants: int = 2) -> dict:
        """Create scale/tint variations of pack assets (or all recent pack assets if no name)."""
        return call("generate_asset_variations", {"asset_name": asset_name, "variants": variants})

    @mcp.tool()
    def create_asset_pack_thumbnails(size: int = 512, limit: int = 0) -> dict:
        """Render an isolated transparent-background thumbnail for each asset in the current pack."""
        params = {"size": size}
        if limit:
            params["limit"] = limit
        return call("create_asset_pack_thumbnails", params)

    @mcp.tool()
    def create_preview_grid(width: int = 1600, height: int = 1000) -> dict:
        """Render the whole pack laid out in its grid (isometric) as a single preview image."""
        return call("create_preview_grid", {"width": width, "height": height})

    @mcp.tool()
    def export_asset_pack_for_unity(name: str = "") -> dict:
        """Export the current pack as a Unity-ready combined GLB (meters, +Y up, applied transforms)."""
        return call("export_asset_pack_for_unity", {"name": name})

    @mcp.tool()
    def export_asset_pack_for_unreal(name: str = "") -> dict:
        """Export the current pack as an Unreal-ready combined FBX (baked space transform)."""
        return call("export_asset_pack_for_unreal", {"name": name})
