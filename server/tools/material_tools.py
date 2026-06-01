"""Material and style tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ._common import call


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def create_material(
        name: str,
        base_color: list[float] | None = None,
        metallic: float = 0.0,
        roughness: float = 0.5,
        emission_strength: float = 0.0,
    ) -> dict:
        """Create a Principled BSDF material.

        base_color: RGBA list of 4 floats 0-1 (defaults to mid grey).
        """
        return call(
            "create_material",
            {
                "name": name,
                "base_color": base_color or [0.6, 0.6, 0.6, 1.0],
                "metallic": metallic,
                "roughness": roughness,
                "emission_strength": emission_strength,
            },
        )

    @mcp.tool()
    def apply_material(object_name: str, material_name: str) -> dict:
        """Assign an existing material to a named object."""
        return call("apply_material", {"object_name": object_name, "material_name": material_name})

    @mcp.tool()
    def apply_style_preset(preset: str = "stylized_cartoon") -> dict:
        """Re-skin the whole scene with a coherent style preset's material set."""
        return call("apply_style_preset", {"preset": preset})

    @mcp.tool()
    def create_stylized_materials() -> dict:
        """Create the stylized/cartoon game material library (grass, road, concrete, wood, glass, metal)."""
        return call("create_stylized_materials")

    @mcp.tool()
    def create_archviz_materials() -> dict:
        """Create the architectural material library (wood, concrete, plaster, metal, glass, marble, fabric)."""
        return call("create_archviz_materials")

    @mcp.tool()
    def create_product_materials() -> dict:
        """Create the product-render material library (studio white, matte black, brushed metal, premium glass)."""
        return call("create_product_materials")

    @mcp.tool()
    def create_emissive_materials(color: str = "blue", strength: float = 5.0) -> dict:
        """Create sci-fi emissive panel materials (blue | cyan | magenta | orange)."""
        return call("create_emissive_materials", {"color": color, "strength": strength})

    @mcp.tool()
    def apply_color_palette_from_image(reference_image: str) -> dict:
        """Extract a color palette from an image and apply it dynamically across all scene materials.

        Creates beautifully tuned harmonized material colors based on visual color analysis.
        """
        return call("apply_color_palette_from_image", {"reference_image": reference_image})

    @mcp.tool()
    def apply_cel_shading_outline(thickness: float = 0.015, selected_only: bool = False) -> dict:
        """Add a professional inverted-hull stylized outline cel-shading modifier to objects.

        This creates classic high-fidelity cartoon and anime contours dynamically.
        """
        return call("apply_cel_shading_outline", {"thickness": thickness, "selected_only": selected_only})

    @mcp.tool()
    def bake_pbr_textures(width: int = 1024, height: int = 1024) -> dict:
        """Automatically bake lighting, AO, normal and roughness maps into images using Blender's Cycles engine."""
        return call("bake_pbr_textures", {"width": width, "height": height})

    @mcp.tool()
    def generate_ai_textures(prompt: str = "stylized medieval handpainted stone tiles", target_object: str = "") -> dict:
        """Submit a text prompt to generate custom seamless textures and auto-apply them to selected UV coordinates."""
        return call("generate_ai_textures", {"prompt": prompt, "target_object": target_object})
