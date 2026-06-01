"""Camera, lighting and render tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..schemas.tool_schemas import RENDER_PRESETS
from ..utils.validation import ensure_in
from ._common import call


def register(mcp: FastMCP) -> None:
    # -- cameras ----------------------------------------------------------
    @mcp.tool()
    def setup_camera(focal_length: float = 50.0, target: str = "scene_center") -> dict:
        """Create/position a general camera framing the scene at the given focal length."""
        return call("setup_camera", {"focal_length": focal_length, "target": target})

    @mcp.tool()
    def setup_isometric_camera(angle: float = 45.0, distance: float = 18.0) -> dict:
        """Create an orthographic isometric camera ideal for stylized/mobile game scenes."""
        return call("setup_isometric_camera", {"angle": angle, "distance": distance})

    @mcp.tool()
    def setup_archviz_camera(focal_length: float = 24.0, eye_level: float = 1.6) -> dict:
        """Create an architectural camera at human eye level with a wide focal length."""
        return call("setup_archviz_camera", {"focal_length": focal_length, "eye_level": eye_level})

    @mcp.tool()
    def setup_product_camera(focal_length: float = 85.0, depth_of_field: bool = True) -> dict:
        """Create a centered product camera with optional depth of field."""
        return call("setup_product_camera", {"focal_length": focal_length, "depth_of_field": depth_of_field})

    # -- lighting ---------------------------------------------------------
    @mcp.tool()
    def setup_lighting(style: str = "soft", strength: float = 1.0) -> dict:
        """Set up general scene lighting (soft | bright | moody)."""
        return call("setup_lighting", {"style": style, "strength": strength})

    @mcp.tool()
    def setup_three_point_lighting(strength: float = 1.0) -> dict:
        """Create classic key/fill/rim three-point lighting."""
        return call("setup_three_point_lighting", {"strength": strength})

    @mcp.tool()
    def setup_archviz_lighting(time_of_day: str = "midday", interior: bool = False) -> dict:
        """Set up natural sun/sky lighting balanced for interior or exterior archviz."""
        return call("setup_archviz_lighting", {"time_of_day": time_of_day, "interior": interior})

    @mcp.tool()
    def setup_cinematic_lighting(mood: str = "dramatic", volumetrics: bool = False) -> dict:
        """Set up dramatic cinematic lighting with optional volumetric fog."""
        return call("setup_cinematic_lighting", {"mood": mood, "volumetrics": volumetrics})

    # -- render -----------------------------------------------------------
    @mcp.tool()
    def apply_render_preset(preset: str = "portfolio_render") -> dict:
        """Configure the render engine and quality from a preset.

        preset: fast_preview | portfolio_render | archviz_render | product_render | cinematic_render
        """
        ensure_in(preset, tuple(RENDER_PRESETS), "preset")
        return call("apply_render_preset", {"preset": preset})

    @mcp.tool()
    def render_preview(width: int = 960, height: int = 540, filename: str = "preview.png") -> dict:
        """Render a fast preview image to outputs/renders and return its path."""
        return call("render_preview", {"width": width, "height": height, "filename": filename})

    @mcp.tool()
    def render_final(
        width: int = 1920, height: int = 1080, samples: int = 128, filename: str = "final.png"
    ) -> dict:
        """Render a high-quality final image to outputs/renders and return its path."""
        return call("render_final", {"width": width, "height": height, "samples": samples, "filename": filename})

    @mcp.tool()
    def setup_camera_auto_focus(target_name: str = "", fstop: float = 2.0) -> dict:
        """Enable camera Depth of Field (lens blur) and lock focus onto a specific rig or object.

        Locks target focus onto character or environment landmark, making rendering look extremely professional.
        """
        return call("setup_camera_auto_focus", {"target_name": target_name, "fstop": fstop})
