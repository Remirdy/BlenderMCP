"""MCP tools — NeRF / Gaussian Splatting → Blender pipeline."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from ..utils.logging_utils import get_logger
from ..utils import jobs as job_tracker

log = get_logger("remirdy.nerf_tools")


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def check_nerf_backends() -> dict:
        """
        Check which NeRF/3DGS backends are installed and available.
        Returns status for COLMAP, Nerfstudio, and Gaussian Splatting.

        Install guides:
          Nerfstudio : pip install nerfstudio && ns-install-cli
          COLMAP     : brew install colmap  (macOS) / apt install colmap (Ubuntu)
          3DGS       : git clone gaussian-splatting + pip install requirements
        """
        from ..providers.nerf_gs import status
        return status()

    @mcp.tool()
    def reconstruct_scene_from_photos(
        images_path: str,
        project_name: str = "my_scan",
        method: str = "auto",
        quality: str = "medium",
    ) -> dict:
        """
        Turn a folder of photographs into a 3D scene in Blender.

        Zero cost, runs entirely locally. Point your phone camera at an object
        or location from multiple angles (20–200 photos), then run this tool.

        Pipeline:
          1. COLMAP  — camera calibration + sparse point cloud
          2. NeRF/3DGS training — dense 3D reconstruction
          3. PLY export → imported into Blender
          4. Multi-agent material + lighting polish

        Args:
            images_path  : Folder of JPG/PNG photos OR path to a video file.
                           For best results: 30–100 overlapping photos, no motion blur.
            project_name : Name for this scan project (used for output folder).
            method       : "auto" | "nerfstudio" | "3dgs" | "colmap_only"
                           "auto" picks the best available backend.
            quality      : "low" (fast, ~5 min) | "medium" (~30 min) | "high" (~2h)

        Returns: ply_path, workspace, backend used, Blender import command.
        Tracked as a background job — use get_job_status(job_id) to follow progress.
        """
        from ..providers.nerf_gs import reconstruct_from_images
        from ..tools._common import call

        j = job_tracker.create_job("nerf", "reconstruct", {
            "images_path": images_path,
            "method": method,
            "quality": quality,
        })
        job_tracker.update_job(j["job_id"], state="running",
                               status_message="Starting reconstruction pipeline...")

        try:
            result = reconstruct_from_images(
                images_path=images_path,
                name=project_name,
                method=method,
                quality=quality,
                job_id=j["job_id"],
            )
            job_tracker.finish_job(j["job_id"], result=result)
            result["job_id"] = j["job_id"]

            # Auto-import into Blender if we have a PLY/mesh
            if result.get("ok") and result.get("ply_path"):
                import_result = call("import_glb", {"path": result["ply_path"]})
                result["blender_import"] = import_result

            return result
        except Exception as exc:
            job_tracker.finish_job(j["job_id"], error=str(exc))
            return {"ok": False, "error": str(exc), "job_id": j["job_id"]}

    @mcp.tool()
    def reconstruct_from_video(
        video_path: str,
        project_name: str = "video_scan",
        frames_per_second: float = 2.0,
        method: str = "auto",
        quality: str = "medium",
    ) -> dict:
        """
        Extract frames from a video and reconstruct a 3D scene from them.
        Walk around an object or location with your phone, import the result into Blender.

        Args:
            video_path         : Path to MP4/MOV/AVI video file.
            project_name       : Output folder name.
            frames_per_second  : Frame extraction rate (2 fps = good, 5 fps = more detail).
            method             : "auto" | "nerfstudio" | "3dgs" | "colmap_only"
            quality            : "low" | "medium" | "high"
        """
        from ..providers.nerf_gs import reconstruct_from_images
        from ..tools._common import call

        j = job_tracker.create_job("nerf", "video_reconstruct", {"video": video_path})
        job_tracker.update_job(j["job_id"], state="running", status_message="Extracting frames...")

        try:
            result = reconstruct_from_images(
                images_path=video_path,
                name=project_name,
                method=method,
                quality=quality,
                video_fps=frames_per_second,
                job_id=j["job_id"],
            )
            job_tracker.finish_job(j["job_id"], result=result)
            result["job_id"] = j["job_id"]

            if result.get("ok") and result.get("ply_path"):
                import_result = call("import_glb", {"path": result["ply_path"]})
                result["blender_import"] = import_result

            return result
        except Exception as exc:
            job_tracker.finish_job(j["job_id"], error=str(exc))
            return {"ok": False, "error": str(exc), "job_id": j["job_id"]}
