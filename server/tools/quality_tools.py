"""Scene organization and quality-control tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ._common import call


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def create_collection(name: str) -> dict:
        """Create a new named collection for scene organization."""
        return call("create_collection", {"name": name})

    @mcp.tool()
    def organize_scene() -> dict:
        """Sort objects into logical collections (Architecture, Furniture, Props, Lights, Cameras, etc.)."""
        return call("organize_scene")

    @mcp.tool()
    def rename_objects_professionally(prefix: str = "") -> dict:
        """Rename objects with a clean, consistent professional naming convention."""
        return call("rename_objects_professionally", {"prefix": prefix})

    @mcp.tool()
    def set_origins_and_pivots(mode: str = "bottom_center") -> dict:
        """Set sensible object origins (bottom_center | geometry | base_pivot)."""
        return call("set_origins_and_pivots", {"mode": mode})

    @mcp.tool()
    def fix_transforms() -> dict:
        """Clean up transforms: remove NaNs, snap near-zero rotations, recenter strays."""
        return call("fix_transforms")

    @mcp.tool()
    def apply_scale_rotation() -> dict:
        """Apply scale and rotation to all mesh objects (transforms baked, scale = 1)."""
        return call("apply_scale_rotation")

    @mcp.tool()
    def scene_quality_check() -> dict:
        """Audit the scene for missing camera/lights/materials, unnamed objects, bad origins, high polycount, scale and organization issues. Returns a report with severities."""
        return call("scene_quality_check")

    @mcp.tool()
    def auto_fix_scene(aggressive: bool = False) -> dict:
        """Automatically fix common issues found by scene_quality_check (add camera/lights, assign materials, rename, set origins, organize)."""
        return call("auto_fix_scene", {"aggressive": aggressive})

    @mcp.tool()
    def normalize_imported_asset(target_size: float = 2.0, selected_only: bool = False) -> dict:
        """Normalize selected/all imported meshes to a target max dimension and ground them."""
        return call("normalize_imported_asset", {"target_size": target_size, "selected_only": selected_only})

    @mcp.tool()
    def repair_materials() -> dict:
        """Assign missing materials and normalize material names/settings."""
        return call("repair_materials")

    @mcp.tool()
    def decimate_asset(ratio: float = 0.5, min_faces: int = 1000, apply: bool = False) -> dict:
        """Add or apply decimation to high-poly mesh objects."""
        return call("decimate_asset", {"ratio": ratio, "min_faces": min_faces, "apply": apply})

    @mcp.tool()
    def generate_lods(ratios: str = "0.6,0.3,0.12") -> dict:
        """Generate LOD mesh duplicates using comma-separated decimation ratios."""
        return call("generate_lods", {"ratios": ratios})

    @mcp.tool()
    def create_collision_proxies(mode: str = "box") -> dict:
        """Create simple collision proxy objects for game engines."""
        return call("create_collision_proxies", {"mode": mode})

    @mcp.tool()
    def check_engine_readiness(target: str = "unity", max_faces: int = 100000) -> dict:
        """Check whether the scene is ready for Unity/Unreal/Web export."""
        return call("check_engine_readiness", {"target": target, "max_faces": max_faces})

    @mcp.tool()
    def check_license_metadata() -> dict:
        """Check imported asset folders for attribution/license metadata."""
        return call("check_license_metadata")

    @mcp.tool()
    def apply_quad_remesh(voxel_size: float = 0.035, selected_only: bool = True) -> dict:
        """Run Blender's built-in Voxel Remesher on dense AI meshes to generate a clean quad layout."""
        return call("apply_quad_remesh", {"voxel_size": voxel_size, "selected_only": selected_only})

    @mcp.tool()
    def apply_voxel_blockout(depth: int = 6, selected_only: bool = True) -> dict:
        """Dynamically reconstruct selected models as highly stylized voxel blocks utilizing Remesh modifiers."""
        return call("apply_voxel_blockout", {"depth": depth, "selected_only": selected_only})
