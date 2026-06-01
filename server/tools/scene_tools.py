"""High-level scene creation tools (prompt + category presets + parallel image-to-3D assets)."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..schemas.tool_schemas import RENDER_PRESETS
from ..utils import jobs
from ..utils.validation import ensure_in
from ._common import call


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def create_scene_from_prompt(
        prompt: str,
        render_preset: str = "portfolio_render",
        auto_fix: bool = True,
        render_after: bool = True,
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
        render_after: bool = True,
    ) -> dict:
        """Create a highly styled, colored game environment based on a text prompt or theme.

        Creates terrain, modular elements, styling, lights, isometric camera, and applies textures.
        style: mobile_stylized | pc_game_environment | low_poly | stylized_cartoon | sci_fi_game_level
        theme: free text such as 'campus', 'medieval_village', 'cyberpunk_alley', 'sci_fi_corridor'.
        """
        return call(
            "create_game_environment",
            {
                "style": style,
                "theme": theme,
                "size": size,
                "isometric_camera": isometric_camera,
                "render_after": render_after,
            },
        )

    @mcp.tool()
    def create_game_environment_from_reference_image(
        reference_image: str,
        style: str = "mobile_stylized",
        theme: str = "",
        size: str = "medium",
        isometric_camera: bool = True,
        add_reference_billboard: bool = True,
        use_ai_assets: bool = True,  # Generate central 3D assets in parallel using AI
        provider: str = "parallel",
        seed: int = 11,
        render_after: bool = True,
    ) -> dict:
        """Create a beautiful, fully textured game environment from a reference image.

        The bridge extracts the palette, infers the theme (nature/urban/waterfront/sci-fi/desert),
        and dynamically creates a colored 3D scene.
        If `use_ai_assets` is true, the pipeline runs parallel AI image-to-3D on the reference image
        to construct a high-fidelity central prop or monument to place at the heart of the environment.
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
                "use_ai_assets": use_ai_assets,
                "provider": provider,
                "seed": seed,
                "render_after": render_after,
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

    @mcp.tool()
    def create_scene_from_video_reference(
        video_or_frames_path: str,
        num_keyframes: int = 4,
        style: str = "cinematic",
        auto_polish_with_agents: bool = True,
        run_optimization: bool = True,
        run_as_job: bool = True,
    ) -> dict:
        """
        Professional-grade Video / Image Sequence to 3D Reconstruction.

        Features:
        - Keyframe reference planes
        - Full multi-agent reconstruction (geometry, materials, lighting, composition, critique)
        - Optional Optimization & Delivery Agent
        - Full job tracking for professional pipelines
        """
        job = None
        if run_as_job:
            job = jobs.create_job("remirdy", "video_to_3d", {
                "video_path": video_or_frames_path,
                "num_keyframes": num_keyframes
            })
            jobs.update_job(job["job_id"], state="running", status_message="Extracting references from video...")

        try:
            base = call(
                "create_scene_from_video_reference",
                {
                    "video_or_frames_path": video_or_frames_path,
                    "num_keyframes": num_keyframes,
                    "style": style,
                },
            )

            if not auto_polish_with_agents:
                if run_as_job and job:
                    jobs.finish_job(job["job_id"], result=base)
                return base

            if run_as_job and job:
                jobs.set_job_progress(job["job_id"], 40, "Running professional multi-agent reconstruction...")

            from ..agents.coordinator import SceneCoordinator
            coord = SceneCoordinator()

            focus = ["lighting", "materials", "composition", "critique"]
            if run_optimization:
                focus.append("optimization")

            polish = coord.orchestrate(
                prompt=f"professional reconstruction and polish of scene from video reference: {video_or_frames_path}",
                focus_areas=focus,
                max_iterations=3,
                use_vision_critique=True,
            )

            final = {
                "ok": True,
                "video_path": video_or_frames_path,
                "initial_creation": base,
                "agent_polish": polish,
                "combined_summary": f"Professional video-to-3D + {polish.get('iterations_run', 0)} iterations",
            }

            if run_as_job and job:
                jobs.finish_job(job["job_id"], result=final)
                final["job_id"] = job["job_id"]

            return final

        except Exception as exc:
            if run_as_job and job:
                jobs.finish_job(job["job_id"], error=str(exc))
            return {"ok": False, "error": str(exc)}

    @mcp.tool()
    def create_procedural_city_blockout(
        prompt: str,
        size_km: float = 1.5,
        density: str = "medium",
        style: str = "modern",
    ) -> dict:
        """
        Prompt'tan prosedürel şehir blockout üretir (Tier 3 fikir).
        Örnek: "neo-Tokyo gece, 2 km² cyberpunk"
        """
        return call(
            "create_procedural_city_blockout",
            {
                "prompt": prompt,
                "size_km": size_km,
                "density": density,
                "style": style,
            },
        )
