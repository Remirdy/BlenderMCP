"""
NeRF / Gaussian Splatting Provider.

Turns a folder of photographs (or a video) into a 3D scene importable in Blender.

Supported backends (auto-detected by which tools are installed):
  3dgs        — Gaussian Splatting (gaussian-splatting repo / gsplat)
  nerfstudio  — Nerfstudio (ns-process-data + ns-train)
  instant_ngp — Instant-NGP (ngp_pl or official repo)
  colmap_only — COLMAP camera calibration only → sparse point cloud PLY

Typical install
---------------
    # Nerfstudio (recommended, easiest)
    pip install nerfstudio
    ns-install-cli

    # COLMAP
    brew install colmap  # macOS
    sudo apt install colmap  # Ubuntu

    # 3DGS
    git clone https://github.com/graphdeco-inria/gaussian-splatting
    pip install -r requirements.txt

Environment variables
---------------------
NERF_BACKEND        : "3dgs" | "nerfstudio" | "instant_ngp" | "colmap_only" | "auto"
NERF_COLMAP_PATH    : Path to colmap binary (default "colmap")
NERF_NS_TRAIN_PATH  : Path to ns-train binary (default "ns-train")
NERF_3DGS_PATH      : Path to 3DGS train.py
NERF_OUTPUT_DIR     : Output directory override
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from ..utils.logging_utils import get_logger
from ..utils import jobs as job_tracker

log = get_logger("remirdy.providers.nerf")

# ── config ────────────────────────────────────────────────────────────────────

NERF_BACKEND    = os.environ.get("NERF_BACKEND", "auto")
COLMAP_BIN      = os.environ.get("NERF_COLMAP_PATH", "colmap")
NS_TRAIN_BIN    = os.environ.get("NERF_NS_TRAIN_PATH", "ns-train")
GS_TRAIN_SCRIPT = os.environ.get("NERF_3DGS_PATH", "")


# ── availability checks ───────────────────────────────────────────────────────

def _bin_available(name: str) -> bool:
    return shutil.which(name) is not None


def colmap_available() -> bool:
    return _bin_available(COLMAP_BIN)


def nerfstudio_available() -> bool:
    return _bin_available(NS_TRAIN_BIN) or _bin_available("ns-process-data")


def gs_available() -> bool:
    if GS_TRAIN_SCRIPT and Path(GS_TRAIN_SCRIPT).exists():
        return True
    return _bin_available("gaussian_splatting") or _bin_available("train")


def detect_backend() -> str | None:
    b = NERF_BACKEND.lower()
    if b == "nerfstudio": return "nerfstudio" if nerfstudio_available() else None
    if b == "3dgs":        return "3dgs"        if gs_available()         else None
    if b == "colmap_only": return "colmap_only" if colmap_available()     else None
    # auto
    if nerfstudio_available(): return "nerfstudio"
    if gs_available():          return "3dgs"
    if colmap_available():      return "colmap_only"
    return None


def is_available() -> bool:
    return detect_backend() is not None


def status() -> dict[str, Any]:
    backend = detect_backend()
    return {
        "configured": backend is not None,
        "backend": backend,
        "colmap_available": colmap_available(),
        "nerfstudio_available": nerfstudio_available(),
        "3dgs_available": gs_available(),
    }


# ── workspace ─────────────────────────────────────────────────────────────────

def _workspace(name: str) -> Path:
    root = Path(
        os.environ.get("NERF_OUTPUT_DIR")
        or os.environ.get("REMIRDY_WORKSPACE", str(Path.home() / "RemirdyWorkspace"))
    ) / "outputs" / "nerf" / name
    root.mkdir(parents=True, exist_ok=True)
    return root


# ── image extraction from video ───────────────────────────────────────────────

def extract_frames(video_path: str, out_dir: str, fps: float = 2.0) -> list[str]:
    """Extract frames from a video at given FPS using FFmpeg."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [ffmpeg, "-i", video_path, "-vf", f"fps={fps}", str(out / "frame_%04d.png")]
    result = subprocess.run(cmd, capture_output=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"Frame extraction failed: {result.stderr.decode()[:300]}")
    return sorted(str(p) for p in out.glob("*.png"))


# ── COLMAP pipeline ───────────────────────────────────────────────────────────

def run_colmap(images_dir: str, workspace: Path, quality: str = "medium") -> dict[str, Any]:
    """Run COLMAP feature extraction + matching + reconstruction."""
    db_path = workspace / "colmap.db"
    sparse_dir = workspace / "sparse"
    sparse_dir.mkdir(exist_ok=True)

    quality_map = {"low": "low", "medium": "medium", "high": "high", "ultra": "extreme"}
    q = quality_map.get(quality, "medium")

    cmds = [
        [COLMAP_BIN, "feature_extractor",
         "--database_path", str(db_path),
         "--image_path", images_dir,
         "--ImageReader.single_camera", "1"],
        [COLMAP_BIN, "exhaustive_matcher",
         "--database_path", str(db_path)],
        [COLMAP_BIN, "mapper",
         "--database_path", str(db_path),
         "--image_path", images_dir,
         "--output_path", str(sparse_dir)],
    ]

    for cmd in cmds:
        log.info("[COLMAP] Running: %s", " ".join(cmd[:3]))
        result = subprocess.run(cmd, capture_output=True, timeout=600)
        if result.returncode != 0:
            return {"ok": False, "error": f"COLMAP step failed: {result.stderr.decode()[:300]}"}

    # Find output model
    model_dirs = list(sparse_dir.iterdir())
    if not model_dirs:
        return {"ok": False, "error": "COLMAP produced no model"}

    return {"ok": True, "sparse_model": str(model_dirs[0]), "database": str(db_path)}


# ── Nerfstudio pipeline ───────────────────────────────────────────────────────

def run_nerfstudio(
    images_dir: str,
    workspace: Path,
    method: str = "nerfacto",
    max_num_iterations: int = 30000,
) -> dict[str, Any]:
    """Run Nerfstudio training pipeline."""
    data_dir = workspace / "ns_data"
    output_dir = workspace / "ns_output"
    data_dir.mkdir(exist_ok=True)

    # Step 1: ns-process-data
    proc_cmd = [
        "ns-process-data", "images",
        "--data", images_dir,
        "--output-dir", str(data_dir),
    ]
    log.info("[Nerfstudio] Processing data...")
    result = subprocess.run(proc_cmd, capture_output=True, timeout=300)
    if result.returncode != 0:
        log.warning("[Nerfstudio] process-data warning: %s", result.stderr.decode()[:200])

    # Step 2: ns-train
    train_cmd = [
        NS_TRAIN_BIN, method,
        "--data", str(data_dir),
        "--output-dir", str(output_dir),
        "--max-num-iterations", str(max_num_iterations),
        "--pipeline.model.predict-normals", "True",
    ]
    log.info("[Nerfstudio] Training %s...", method)
    result = subprocess.run(train_cmd, capture_output=True, timeout=7200)
    if result.returncode != 0:
        return {"ok": False, "error": f"ns-train failed: {result.stderr.decode()[:300]}"}

    # Step 3: Export mesh
    export_dir = output_dir / "exports"
    export_dir.mkdir(exist_ok=True)
    ply_path = export_dir / "mesh.ply"

    # Find latest checkpoint
    checkpoints = list(output_dir.rglob("*.ckpt"))
    if checkpoints:
        latest = str(sorted(checkpoints)[-1])
        export_cmd = [
            "ns-export", "poisson",
            "--load-config", str(list(output_dir.rglob("config.yml"))[0]),
            "--output-dir", str(export_dir),
        ]
        subprocess.run(export_cmd, capture_output=True, timeout=300)

    return {
        "ok": True,
        "output_dir": str(output_dir),
        "ply_path": str(ply_path) if ply_path.exists() else None,
    }


# ── 3D Gaussian Splatting pipeline ───────────────────────────────────────────

def run_3dgs(
    images_dir: str,
    workspace: Path,
    iterations: int = 30000,
) -> dict[str, Any]:
    """Run Gaussian Splatting training after COLMAP calibration."""
    colmap_result = run_colmap(images_dir, workspace)
    if not colmap_result.get("ok"):
        return colmap_result

    output_dir = workspace / "3dgs_output"
    output_dir.mkdir(exist_ok=True)

    train_script = GS_TRAIN_SCRIPT or shutil.which("train.py") or "train.py"
    cmd = [
        "python", train_script,
        "-s", images_dir,
        "-m", str(output_dir),
        "--iterations", str(iterations),
    ]
    log.info("[3DGS] Training Gaussian Splatting...")
    result = subprocess.run(cmd, capture_output=True, timeout=7200)

    ply_path = output_dir / "point_cloud" / f"iteration_{iterations}" / "point_cloud.ply"
    return {
        "ok": result.returncode == 0,
        "output_dir": str(output_dir),
        "ply_path": str(ply_path) if ply_path.exists() else None,
        "error": result.stderr.decode()[:300] if result.returncode != 0 else None,
    }


# ── Unified entry point ───────────────────────────────────────────────────────

def reconstruct_from_images(
    images_path: str,
    name: str = "scene",
    method: str = "auto",
    quality: str = "medium",
    video_fps: float = 2.0,
    job_id: str | None = None,
) -> dict[str, Any]:
    """
    Full pipeline: images/video folder → 3D reconstruction → PLY file.

    Parameters
    ----------
    images_path : Folder of images OR path to a video file.
    name        : Project name (used for workspace folder).
    method      : "auto" | "nerfstudio" | "3dgs" | "colmap_only"
    quality     : "low" | "medium" | "high"
    video_fps   : FPS for video frame extraction (default 2).
    job_id      : Optional job ID for progress tracking.
    """
    def _progress(pct: float, msg: str):
        if job_id:
            job_tracker.set_job_progress(job_id, pct, msg)
        log.info("[NeRF] %.0f%% — %s", pct, msg)

    workspace = _workspace(name)
    images_path_obj = Path(images_path)

    # Handle video input
    images_dir = images_path
    if images_path_obj.is_file() and images_path_obj.suffix.lower() in (".mp4", ".mov", ".avi", ".mkv"):
        _progress(5, "Extracting frames from video...")
        frames_dir = str(workspace / "frames")
        try:
            frames = extract_frames(images_path, frames_dir, fps=video_fps)
            images_dir = frames_dir
            _progress(15, f"Extracted {len(frames)} frames")
        except Exception as exc:
            return {"ok": False, "error": f"Frame extraction failed: {exc}"}
    elif not images_path_obj.is_dir():
        return {"ok": False, "error": f"images_path must be a folder or video file: {images_path}"}

    backend = method if method != "auto" else (detect_backend() or "colmap_only")
    _progress(18, f"Using backend: {backend}")

    result: dict[str, Any] = {}
    try:
        if backend == "nerfstudio":
            _progress(20, "Running Nerfstudio pipeline...")
            result = run_nerfstudio(images_dir, workspace, max_num_iterations=15000 if quality == "low" else 30000)
        elif backend == "3dgs":
            _progress(20, "Running Gaussian Splatting pipeline...")
            result = run_3dgs(images_dir, workspace, iterations=10000 if quality == "low" else 30000)
        else:  # colmap_only
            _progress(20, "Running COLMAP reconstruction...")
            result = run_colmap(images_dir, workspace, quality=quality)

        if not result.get("ok"):
            return result

        _progress(90, "Reconstruction complete")

        # Return PLY path for Blender import
        ply = result.get("ply_path") or result.get("sparse_model")
        _progress(100, f"Done — output: {ply}")

        return {
            "ok": True,
            "backend": backend,
            "images_dir": images_dir,
            "workspace": str(workspace),
            "ply_path": ply,
            "import_command": f"import_glb(path='{ply}')" if ply and ply.endswith(".ply") else None,
            **result,
        }
    except Exception as exc:
        log.exception("[NeRF] Reconstruction failed")
        return {"ok": False, "error": str(exc)}
