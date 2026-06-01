"""MCP tools for ComfyUI / Stable Diffusion Local backend."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from ..utils.logging_utils import get_logger

log = get_logger("remirdy.comfyui_tools")


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def check_sd_backend() -> dict:
        """
        Check if a local Stable Diffusion backend is running and ready.
        Returns which backend is active (ComfyUI or Automatic1111) and URLs.
        """
        from ..providers.comfyui_sd import status
        return status()

    @mcp.tool()
    def generate_texture(
        description: str,
        resolution: int = 512,
        seamless: bool = True,
        output_path: str = "",
    ) -> dict:
        """
        Generate a seamless PBR-ready texture using local Stable Diffusion.
        Zero cost — runs entirely on your local GPU.

        Args:
            description : What the texture should look like.
                          e.g. "weathered stone bricks, mossy, medieval"
                               "polished wood planks, oak, warm tone"
                               "sci-fi metal panel, blue glow, scratched"
            resolution  : Texture resolution in pixels (256/512/1024, default 512).
            seamless    : Make the texture tileable (default True).
            output_path : Optional custom save path.

        Returns image_path to the generated PNG texture.
        Requires ComfyUI (port 8188) or Automatic1111 (port 7860) running locally.
        """
        from ..providers.comfyui_sd import texture_synthesis
        return texture_synthesis(description, output_path or None, resolution, seamless)

    @mcp.tool()
    def generate_concept_art_local(
        prompt: str,
        negative_prompt: str = "ugly, blurry, bad anatomy, watermark",
        width: int = 768,
        height: int = 512,
        steps: int = 30,
        cfg_scale: float = 7.5,
        seed: int = -1,
        output_path: str = "",
    ) -> dict:
        """
        Generate concept art / reference images using local SD — no API key, no cost.
        Feeds directly into generate_image_and_build_scene for a full pipeline.

        Args:
            prompt        : Image description.
            negative_prompt: What to avoid.
            width/height  : Output dimensions.
            steps         : Sampling steps (more = better quality, slower).
            cfg_scale     : Prompt adherence (7–12 typical).
            seed          : Fixed seed for reproducibility (-1 = random).
        """
        from ..providers.comfyui_sd import txt2img
        return txt2img(prompt, output_path or None, negative_prompt, width, height, steps, cfg_scale, seed)

    @mcp.tool()
    def restyle_render(
        render_path: str,
        style_prompt: str,
        strength: float = 0.55,
        output_path: str = "",
    ) -> dict:
        """
        Apply an artistic style to an existing Blender render using SD img2img.
        Transform a photorealistic render into Ghibli, oil painting, cel-shaded, etc.

        Args:
            render_path  : Path to an existing render PNG (from render_preview).
            style_prompt : Style description, e.g.
                           "Studio Ghibli watercolor animation style"
                           "90s low-poly video game screenshot"
                           "oil painting, impressionist brushstrokes"
                           "cel-shaded cartoon, black outlines, flat colors"
            strength     : How much to change (0.3 = subtle, 0.8 = dramatic, default 0.55).
            output_path  : Optional custom save path.
        """
        from ..providers.comfyui_sd import style_transfer_render
        return style_transfer_render(render_path, style_prompt, output_path or None, strength)

    @mcp.tool()
    def generate_and_apply_texture(
        object_name: str,
        texture_description: str,
        resolution: int = 512,
    ) -> dict:
        """
        Generate a texture with local SD and apply it to a Blender object's material.

        Steps:
          1. Generate seamless texture via local SD.
          2. Apply it to the named object in Blender as a base color texture.

        Args:
            object_name         : Name of the Blender object to texture.
            texture_description : e.g. "rusty iron plates, orange, industrial"
            resolution          : Texture size in pixels (default 512).
        """
        from ..providers.comfyui_sd import texture_synthesis
        from ..tools._common import call

        tex_result = texture_synthesis(texture_description, resolution=resolution)
        if not tex_result.get("ok"):
            return tex_result

        tex_path = tex_result["image_path"]
        mat_result = call("apply_material_from_image", {
            "object_name": object_name,
            "image_path": tex_path,
            "texture_type": "albedo",
        })

        return {
            "ok": True,
            "object": object_name,
            "texture_path": tex_path,
            "material_result": mat_result,
            "backend": tex_result.get("backend"),
        }

    @mcp.tool()
    def img2img_pipeline(
        init_image_path: str,
        prompt: str,
        denoising_strength: float = 0.65,
        output_path: str = "",
    ) -> dict:
        """
        General-purpose img2img: feed any image through local SD with a new prompt.
        Useful for concept art refinement, style transfer, or filling in details.

        Args:
            init_image_path    : Source image path.
            prompt             : What you want the output to look like.
            denoising_strength : 0.3 = minor changes, 0.8 = heavy restyle.
            output_path        : Optional save path.
        """
        from ..providers.comfyui_sd import img2img
        return img2img(init_image_path, prompt, output_path or None,
                       denoising_strength=denoising_strength)
