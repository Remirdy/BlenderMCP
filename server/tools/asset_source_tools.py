"""External asset libraries and AI model generation providers."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..utils import jobs
from ..utils.http_utils import download, get_json, qs
from ..utils.telemetry import record_tool


POLYHAVEN = "https://api.polyhaven.com"
SKETCHFAB = "https://api.sketchfab.com/v3"


def _workspace() -> Path:
    root = os.environ.get("REMIRDY_WORKSPACE", os.path.join(Path.home(), "RemirdyWorkspace"))
    path = Path(root) / "outputs" / "imports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_asset_dir(provider: str, asset_id: str) -> Path:
    safe = "".join(ch for ch in asset_id if ch.isalnum() or ch in ("-", "_"))[:96]
    path = _workspace() / provider / safe
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_attribution(out_dir: Path, provider: str, asset_id: str, meta: dict[str, Any]) -> str:
    payload = {
        "provider": provider,
        "asset_id": asset_id,
        "name": meta.get("name") or asset_id,
        "license": meta.get("license") or meta.get("license_url") or "unknown",
        "authors": meta.get("authors") or meta.get("user") or [],
        "source_url": meta.get("source_url") or meta.get("url"),
    }
    path = out_dir / "attribution.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)


def _auth_header(env_name: str) -> dict[str, str] | None:
    token = os.environ.get(env_name)
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


def _timed(name: str, fn):
    import time

    started = time.perf_counter()
    try:
        result = fn()
        record_tool(name, (time.perf_counter() - started) * 1000, True)
        return result
    except Exception as exc:
        record_tool(name, (time.perf_counter() - started) * 1000, False, type(exc).__name__)
        raise


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def search_polyhaven_assets(query: str = "", type: str = "all", max_results: int = 20) -> dict:
        """Search Poly Haven public assets. type: hdris | textures | models | all."""
        def work():
            asset_type = None if type == "all" else type
            data = get_json(f"{POLYHAVEN}/assets?{qs({'type': asset_type})}")
            items = []
            q = query.lower().strip()
            for asset_id, meta in data.items():
                haystack = " ".join([
                    asset_id,
                    str(meta.get("name", "")),
                    " ".join(meta.get("categories", []) or []),
                    " ".join(meta.get("tags", []) or []),
                ]).lower()
                if q and q not in haystack:
                    continue
                items.append({
                    "id": asset_id,
                    "name": meta.get("name", asset_id),
                    "type": meta.get("type"),
                    "categories": meta.get("categories", []),
                    "tags": meta.get("tags", [])[:12],
                })
                if len(items) >= max_results:
                    break
            return {"ok": True, "provider": "polyhaven", "results": items, "count": len(items)}

        return _timed("search_polyhaven_assets", work)

    @mcp.tool()
    def download_polyhaven_asset(asset_id: str, resolution: str = "1k", format: str = "blend") -> dict:
        """Download Poly Haven metadata and the first matching file URL when available."""
        def work():
            files = get_json(f"{POLYHAVEN}/files/{asset_id}")
            meta_all = get_json(f"{POLYHAVEN}/info/{asset_id}")
            out_dir = _safe_asset_dir("polyhaven", asset_id)
            (out_dir / "metadata.json").write_text(json.dumps(files, indent=2), encoding="utf-8")
            attribution = _write_attribution(out_dir, "polyhaven", asset_id, {
                **(meta_all if isinstance(meta_all, dict) else {}),
                "license": "CC0",
                "source_url": f"https://polyhaven.com/a/{asset_id}",
            })

            candidates: list[tuple[str, str]] = []
            def walk(node: Any, label: str = ""):
                if isinstance(node, dict):
                    if "url" in node and isinstance(node["url"], str):
                        candidates.append((label, node["url"]))
                    for key, value in node.items():
                        walk(value, f"{label}/{key}" if label else key)
                elif isinstance(node, list):
                    for idx, value in enumerate(node):
                        walk(value, f"{label}/{idx}")

            walk(files)
            preferred = [c for c in candidates if resolution in c[0].lower() and format.lower() in c[0].lower()]
            label, url = (preferred or candidates)[0]
            filename = url.split("?")[0].rstrip("/").split("/")[-1] or f"{asset_id}.{format}"
            path = download(url, out_dir / filename)
            return {
                "ok": True,
                "provider": "polyhaven",
                "asset_id": asset_id,
                "download_path": path,
                "metadata_path": str(out_dir / "metadata.json"),
                "attribution_path": attribution,
                "matched_file": label,
            }

        return _timed("download_polyhaven_asset", work)

    @mcp.tool()
    def search_sketchfab_models(
        query: str,
        downloadable: bool = True,
        licenses: str = "by,by-sa,cc0",
        max_results: int = 20,
    ) -> dict:
        """Search Sketchfab models. Downloading requires SKETCHFAB_API_TOKEN."""
        def work():
            params = qs({
                "q": query,
                "downloadable": "true" if downloadable else None,
                "licenses": licenses,
                "count": min(max_results, 24),
            })
            headers = _auth_header("SKETCHFAB_API_TOKEN") or {}
            data = get_json(f"{SKETCHFAB}/search?type=models&{params}", headers=headers)
            results = []
            for item in data.get("results", []):
                results.append({
                    "uid": item.get("uid"),
                    "name": item.get("name"),
                    "url": item.get("viewerUrl") or item.get("uri"),
                    "license": (item.get("license") or {}).get("label"),
                    "user": (item.get("user") or {}).get("displayName"),
                    "downloadable": item.get("isDownloadable"),
                })
            return {"ok": True, "provider": "sketchfab", "results": results, "count": len(results)}

        return _timed("search_sketchfab_models", work)

    @mcp.tool()
    def download_sketchfab_model(uid: str, format: str = "gltf") -> dict:
        """Download a Sketchfab model through the official Download API."""
        def work():
            headers = _auth_header("SKETCHFAB_API_TOKEN")
            if not headers:
                return {"ok": False, "error": "Set SKETCHFAB_API_TOKEN to download Sketchfab models."}
            data = get_json(f"{SKETCHFAB}/models/{uid}/download", headers=headers)
            entry = data.get(format) or data.get("gltf") or data.get("glb") or data.get("usdz")
            if not entry or not entry.get("url"):
                return {"ok": False, "error": f"No downloadable {format} URL returned for {uid}."}
            out_dir = _safe_asset_dir("sketchfab", uid)
            (out_dir / "download.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
            attribution = _write_attribution(out_dir, "sketchfab", uid, {
                "source_url": f"https://sketchfab.com/3d-models/{uid}",
                "license": "see Sketchfab model license",
            })
            archive = download(entry["url"], out_dir / f"{uid}_{format}.zip", headers=headers)
            return {"ok": True, "provider": "sketchfab", "uid": uid, "download_path": archive, "attribution_path": attribution}

        return _timed("download_sketchfab_model", work)

    @mcp.tool()
    def generate_model(prompt: str, provider: str = "rodin", quality: str = "regular", seed: int | None = None) -> dict:
        """Submit an AI 3D generation job. Providers: rodin | hunyuan3d."""
        def work():
            provider_name = provider.lower()
            if provider_name == "rodin" and not os.environ.get("RODIN_API_KEY"):
                return {"ok": False, "error": "Set RODIN_API_KEY to use Hyper3D Rodin generation."}
            if provider_name == "hunyuan3d" and not (os.environ.get("HUNYUAN3D_API_KEY") or os.environ.get("HUNYUAN3D_ENDPOINT")):
                return {"ok": False, "error": "Set HUNYUAN3D_API_KEY or HUNYUAN3D_ENDPOINT to use Hunyuan3D."}
            job = jobs.create_job(provider_name, "model_generation", {
                "prompt_length": len(prompt),
                "quality": quality,
                "seed": seed,
            })
            jobs.update_job(job["job_id"], state="queued")
            return {
                "ok": True,
                "job_id": job["job_id"],
                "provider": provider_name,
                "state": "queued",
                "note": "Provider adapter scaffold is ready; wire account-specific endpoint details before production submission.",
            }

        return _timed("generate_model", work)

    @mcp.tool()
    def generate_3d_model_from_image(
        image_path: str,
        provider: str = "rodin",
        prompt: str = "",
        quality: str = "regular",
        seed: int | None = None,
    ) -> dict:
        """Submit an image-to-3D generation job. Providers: rodin | hunyuan3d."""
        def work():
            image = Path(image_path).expanduser()
            if not image.exists():
                return {"ok": False, "error": f"Image path does not exist: {image_path}"}
            if image.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                return {"ok": False, "error": "image_path must be .png, .jpg, .jpeg or .webp"}

            provider_name = provider.lower()
            if provider_name == "rodin" and not os.environ.get("RODIN_API_KEY"):
                return {"ok": False, "error": "Set RODIN_API_KEY to use Rodin image-to-3D generation."}
            if provider_name == "hunyuan3d" and not (os.environ.get("HUNYUAN3D_API_KEY") or os.environ.get("HUNYUAN3D_ENDPOINT")):
                return {"ok": False, "error": "Set HUNYUAN3D_API_KEY or HUNYUAN3D_ENDPOINT to use Hunyuan3D image-to-3D."}

            job = jobs.create_job(provider_name, "image_to_3d", {
                "image_name": image.name,
                "prompt_length": len(prompt),
                "quality": quality,
                "seed": seed,
            })
            jobs.update_job(job["job_id"], state="queued")
            return {
                "ok": True,
                "job_id": job["job_id"],
                "provider": provider_name,
                "state": "queued",
                "source_image": image.name,
                "note": "Image-to-3D provider scaffold is ready; wire account-specific submit/poll/download endpoint details for production.",
            }

        return _timed("generate_3d_model_from_image", work)

    @mcp.tool()
    def download_generated_model(job_id: str, model_url: str = "", filename: str = "generated_model.glb") -> dict:
        """Download a generated model result URL into the Remirdy workspace."""
        def work():
            job = jobs.get_job(job_id)
            if not job:
                return {"ok": False, "error": "Unknown job_id"}
            if not model_url:
                return {"ok": False, "error": "model_url is required until provider polling is fully wired."}
            out_dir = _safe_asset_dir("generated", job_id)
            path = download(model_url, out_dir / os.path.basename(filename))
            jobs.update_job(job_id, state="downloaded", result={"model_path": path})
            return {"ok": True, "job_id": job_id, "model_path": path}

        return _timed("download_generated_model", work)

    @mcp.tool()
    def poll_generation_job(job_id: str) -> dict:
        """Return generation job state."""
        job = jobs.get_job(job_id)
        if not job:
            return {"ok": False, "error": "Unknown job_id"}
        return {"ok": True, "job": job}

    @mcp.tool()
    def list_generation_jobs() -> dict:
        """List in-process generation jobs."""
        return {"ok": True, "jobs": jobs.list_jobs()}
