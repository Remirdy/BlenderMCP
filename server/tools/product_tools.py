"""Product render asset creator tools (MVP 5)."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ._common import call

PRODUCT_TYPES = ("device", "headphones", "smartwatch", "speaker", "perfume_bottle",
                 "cosmetic", "packaging_box", "tech_accessory")


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def create_product_asset(product: str = "device", background: str = "white",
                             depth_of_field: bool = True, setup_stage: bool = True, name: str = "") -> dict:
        """Create an original premium product model on a studio stage with product camera + lighting.

        product: device | headphones | smartwatch | speaker | perfume_bottle | cosmetic | packaging_box
        background: white | gray | black | transparent
        """
        return call("create_product_asset", {"product": product, "background": background,
                                              "depth_of_field": depth_of_field, "setup_stage": setup_stage, "name": name})

    @mcp.tool()
    def create_product_variations(variants: int = 3) -> dict:
        """Create scale/finish variations of the current product."""
        return call("create_product_variations", {"variants": variants})

    @mcp.tool()
    def create_packaging_mockup(name: str = "Packaging") -> dict:
        """Create a clean packaging box mockup asset."""
        return call("create_packaging_mockup", {"name": name})

    @mcp.tool()
    def setup_product_render_stage(background: str = "white", depth_of_field: bool = True) -> dict:
        """Set up a studio stage: backdrop, product camera, three-point lighting, product render preset."""
        return call("setup_product_render_stage", {"background": background, "depth_of_field": depth_of_field})

    @mcp.tool()
    def render_product_thumbnail(size: int = 1024, transparent: bool = True) -> dict:
        """Render a hero/thumbnail still of the current product."""
        return call("render_product_thumbnail", {"size": size, "transparent": transparent})

    @mcp.tool()
    def render_product_turntable(frames: int = 48) -> dict:
        """Render a 360° turntable animation of the current product."""
        return call("render_product_turntable", {"frames": frames})

    @mcp.tool()
    def export_product_model(format: str = "glb", target: str = "generic") -> dict:
        """Export the current product model (glb | fbx)."""
        return call("export_product_model", {"format": format, "target": target})
