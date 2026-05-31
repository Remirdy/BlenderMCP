"""High-level scene creation tools (prompt + category presets)."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..schemas.tool_schemas import RENDER_PRESETS
from ..utils.validation import ensure_in
from ._common import call


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def create_scene_from_prompt(
        prompt: str,
        render_preset: str = "portfolio_render",
        auto_fix: bool = True,
        render_after: bool = False,
    ) -> dict:
        """Parse a natural-language prompt, pick the right preset and build a complete scene.

        The bridge classifies the intent (game / architecture / interior / product /
        cinematic), creates geometry, materials, camera, lighting and render
        settings, then optionally auto-fixes issues and renders a preview.

        Args:
            prompt: e.g. "Create a stylized mobile game campus with canteen, library, trees, isometric camera, Unity GLB."
            render_preset: one of fast_preview, portfolio_render, archviz_render, product_render, cinematic_render.
            auto_fix: run the quality auto-fixer after generation.
            render_after: render a preview image when finished.
        """
        ensure_in(render_preset, tuple(RENDER_PRESETS), "render_preset")
        return call(
            "create_scene_from_prompt",
            {
                "prompt": prompt,
                "render_preset": render_preset,
                "auto_fix": auto_fix,
                "render_after": render_after,
            },
        )

    @mcp.tool()
    def create_game_environment(
        style: str = "mobile_stylized",
        theme: str = "campus",
        size: str = "medium",
        isometric_camera: bool = True,
    ) -> dict:
        """Create a stylized game environment (campus, village, city block, sci-fi, etc.).

        style: mobile_stylized | pc_game_environment | low_poly | stylized_cartoon | sci_fi_game_level
        theme: free text such as 'campus', 'medieval_village', 'cyberpunk_alley', 'sci_fi_corridor'.
        """
        return call(
            "create_game_environment",
            {"style": style, "theme": theme, "size": size, "isometric_camera": isometric_camera},
        )

    @mcp.tool()
    def create_game_environment_from_reference_image(
        reference_image: str,
        style: str = "mobile_stylized",
        theme: str = "",
        size: str = "medium",
        isometric_camera: bool = True,
        add_reference_billboard: bool = True,
        seed: int = 11,
    ) -> dict:
        """Create a game-environment blockout from a reference image.

        The bridge samples the image palette, infers a broad theme
        (nature/urban/waterfront/sci-fi/desert/stylized), builds a playable
        procedural scene, adds lighting/camera, and can include the reference
        image as an in-scene billboard for art direction.
        """
        return call(
            "create_game_environment_from_reference_image",
            {
                "reference_image": reference_image,
                "style": style,
                "theme": theme,
                "size": size,
                "isometric_camera": isometric_camera,
                "add_reference_billboard": add_reference_billboard,
                "seed": seed,
            },
        )

    @mcp.tool()
    def create_architectural_exterior(
        preset: str = "modern_villa", floors: int = 2, landscaping: bool = True
    ) -> dict:
        """Create an architectural exterior with facade, windows, doors, roof, paths and landscaping."""
        return call(
            "create_architectural_exterior",
            {"preset": preset, "floors": floors, "landscaping": landscaping},
        )

    @mcp.tool()
    def create_interior_design_scene(
        room: str = "living_room", style: str = "luxury_apartment", warm_lighting: bool = True
    ) -> dict:
        """Create an interior scene with walls, floor, ceiling, furniture layout and material palette.

        room: living_room | bedroom | kitchen | office | cafe | apartment
        """
        return call(
            "create_interior_design_scene",
            {"room": room, "style": style, "warm_lighting": warm_lighting},
        )

    @mcp.tool()
    def create_product_render_scene(product: str = "device", background: str = "studio_white") -> dict:
        """Create a studio product-render setup: turntable plinth, studio lighting, clean backdrop, product camera."""
        return call("create_product_render_scene", {"product": product, "background": background})

    @mcp.tool()
    def create_cinematic_scene(subject: str = "hero_prop", mood: str = "dramatic") -> dict:
        """Create a cinematic composition with dramatic lighting, optional fog and filmic color."""
        return call("create_cinematic_scene", {"subject": subject, "mood": mood})
