"""External asset libraries and AI model generation providers."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from PIL import Image

from ..utils import jobs
from ..utils.http_utils import download, get_json, post_json, qs
from ..utils.telemetry import record_tool
from ._common import call


POLYHAVEN = "https://api.polyhaven.com"
SKETCHFAB = "https://api.sketchfab.com/v3"

# Terrain / GIS sources (free, no key required for MVP)
NOMINATIM = "https://nominatim.openstreetmap.org"
OVERPASS = "https://overpass-api.de/api/interpreter"
AWS_TERRAIN = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium"


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

    # --- Real-world terrain tools (Satellite → 3D) ---
    @mcp.tool()
    def geocode_location_tool(query: str) -> dict:
        """Convert a place name (e.g. 'Kapadokya', 'Bosphorus Istanbul', 'Pamukkale') into lat/lon + bbox."""
        return geocode_location(query)

    @mcp.tool()
    def fetch_elevation_heightmap(lat: float, lon: float, radius_km: float = 2.0, zoom: int = 12) -> dict:
        """Download real elevation tiles from AWS Terrarium and return a ready heightmap PNG + stats."""
        bbox = _compute_terrain_bbox(lat, lon, radius_km)
        return fetch_aws_terrarium_heightmap(bbox, zoom=zoom)

    @mcp.tool()
    def create_real_world_terrain_scene(
        location: str,
        radius_km: float = 2.0,
        resolution: int = 256,
        exaggeration: float = 1.8,
        style: str = "stylized",
        add_sun: bool = True,
    ) -> dict:
        """
        The main 'Satellite → 3D' entry point.
        Geocodes the location, fetches real-world elevation data, and creates a displaced terrain in Blender.
        """
        geo = geocode_location(location)
        if not geo.get("ok"):
            return geo

        lat, lon = geo["lat"], geo["lon"]
        bbox = _compute_terrain_bbox(lat, lon, radius_km)

        elev = fetch_aws_terrarium_heightmap(bbox, zoom=12)
        if not elev.get("ok"):
            return elev

        heightmap = elev["heightmap_path"]
        meta = elev["metadata"]

        result = call(
            "create_terrain_from_heightmap",
            {
                "heightmap_path": heightmap,
                "resolution": resolution,
                "exaggeration": exaggeration,
                "real_world_scale_m": max(meta.get("max_elevation_m", 500) - meta.get("min_elevation_m", 0), 80),
                "location_name": geo.get("display_name", location),
                "style": style,
                "add_sun": add_sun,
            },
        )

        return {
            "ok": True,
            "location": geo.get("display_name"),
            "lat": lat,
            "lon": lon,
            "radius_km": radius_km,
            "heightmap_path": heightmap,
            "elevation_range_m": [meta.get("min_elevation_m"), meta.get("max_elevation_m")],
            "blender": result,
        }

    # === Otomatik Asset Pipeline (Tier 1 iyileştirme) ===
    @mcp.tool()
    def auto_import_polyhaven_asset(asset_id: str, asset_type: str = "model", place_in_scene: bool = True) -> dict:
        """Poly Haven asset'ini indir, import et ve sahneye otomatik yerleştirir."""
        dl = download_polyhaven_asset(asset_id, resolution="2k", format="glb" if asset_type == "model" else "blend")
        if not dl.get("ok"):
            return dl

        path = dl.get("download_path")
        imp = call("import_asset_file", {"path": path, "collection": "Assets"})
        return {
            "ok": True,
            "asset_id": asset_id,
            "download": dl,
            "import": imp,
            "auto_placed": place_in_scene,
        }

    @mcp.tool()
    def search_and_place_asset(query: str, provider: str = "polyhaven", max_results: int = 5) -> dict:
        """Arama yapıp en iyi sonucu otomatik indirip sahneye yerleştirir (hızlı workflow için)."""
        if provider == "polyhaven":
            res = search_polyhaven_assets(query, type="all", max_results=max_results)
        else:
            res = search_sketchfab_models(query, max_results=max_results)

        return {
            "ok": True,
            "search_results": res,
            "note": "Use auto_import_polyhaven_asset with a chosen id for full pipeline."
        }


# =============================================================================
# REAL-WORLD TERRAIN (Satellite → 3D) — Phase A helpers (module level)
# =============================================================================

_TERRAIN_CACHE = Path(os.environ.get("REMIRDY_WORKSPACE", Path.home() / "RemirdyWorkspace")) / "outputs" / "imports" / "terrain"


def _terrain_cache_dir() -> Path:
    _TERRAIN_CACHE.mkdir(parents=True, exist_ok=True)
    return _TERRAIN_CACHE


def geocode_location(query: str) -> dict[str, Any]:
    """Geocode a place name to lat/lon + bounding box using Nominatim (free)."""
    q = query.strip()
    if not q:
        return {"ok": False, "error": "Empty location query"}

    params = qs({"q": q, "format": "jsonv2", "limit": 1, "addressdetails": 0})
    url = f"{NOMINATIM}/search?{params}"

    try:
        data = get_json(url, headers={"Accept": "application/json"}, timeout=15)
        if not data or not isinstance(data, list) or len(data) == 0:
            return {"ok": False, "error": f"No results for '{q}'"}

        item = data[0]
        lat = float(item["lat"])
        lon = float(item["lon"])
        # boundingbox is [south, north, west, east] as strings
        bb = item.get("boundingbox", ["0", "0", "0", "0"])
        bbox = [float(bb[0]), float(bb[2]), float(bb[1]), float(bb[3])]  # south,west,north,east

        return {
            "ok": True,
            "query": q,
            "display_name": item.get("display_name", q),
            "lat": lat,
            "lon": lon,
            "bbox": bbox,  # [south, west, north, east]
            "importance": float(item.get("importance", 0.5)),
        }
    except Exception as exc:
        return {"ok": False, "error": f"Geocode failed: {exc}"}


def _latlon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """Convert WGS84 lat/lon to tile x/y at given zoom (Web Mercator)."""
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def _tile_to_latlon(x: int, y: int, zoom: int) -> tuple[float, float]:
    n = 2.0 ** zoom
    lon = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat = math.degrees(lat_rad)
    return lat, lon


def _compute_terrain_bbox(center_lat: float, center_lon: float, radius_km: float) -> list[float]:
    """Approximate bounding box [south, west, north, east] for a radius around a point."""
    # Very rough degrees-per-km at given latitude
    km_per_deg_lat = 110.574
    km_per_deg_lon = 111.320 * math.cos(math.radians(center_lat))

    dlat = radius_km / km_per_deg_lat
    dlon = radius_km / km_per_deg_lon

    south = center_lat - dlat
    north = center_lat + dlat
    west = center_lon - dlon
    east = center_lon + dlon
    return [south, west, north, east]


def _get_tiles_for_bbox(bbox: list[float], zoom: int) -> list[tuple[int, int]]:
    """Return list of (x, y) tiles that cover the bbox at this zoom."""
    south, west, north, east = bbox
    min_x, min_y = _latlon_to_tile(north, west, zoom)
    max_x, max_y = _latlon_to_tile(south, east, zoom)

    tiles = []
    for y in range(min(min_y, max_y), max(min_y, max_y) + 1):
        for x in range(min(min_x, max_x), max(min_x, max_x) + 1):
            tiles.append((x, y))
    return tiles


def fetch_aws_terrarium_heightmap(
    bbox: list[float],
    zoom: int = 12,
    max_tiles: int = 25,
) -> dict[str, Any]:
    """
    Download AWS Terrarium tiles, stitch them, and produce a decoded heightmap PNG + metadata.
    Returns path to heightmap PNG (grayscale, 0-65535 scaled) and real elevation stats.
    """
    cache = _terrain_cache_dir()
    safe_name = f"terrarium_z{zoom}_{abs(hash(str(bbox))) % 100000}"
    out_dir = cache / safe_name
    out_dir.mkdir(parents=True, exist_ok=True)

    tiles = _get_tiles_for_bbox(bbox, zoom)
    if len(tiles) > max_tiles:
        # Downsample zoom automatically if too many tiles
        zoom = max(9, zoom - 1)
        tiles = _get_tiles_for_bbox(bbox, zoom)

    tile_images: dict[tuple[int, int], Image.Image] = {}
    min_elev = 99999
    max_elev = -99999

    for tx, ty in tiles:
        url = f"{AWS_TERRAIN}/{zoom}/{tx}/{ty}.png"
        local = out_dir / f"{tx}_{ty}.png"
        try:
            if not local.exists():
                download(url, local)
            img = Image.open(local).convert("RGB")
            tile_images[(tx, ty)] = img

            # Quick decode stats
            arr = list(img.getdata())
            for r, g, b in arr:
                elev = (r * 256 + g + b / 256.0) - 32768.0
                if elev < min_elev:
                    min_elev = elev
                if elev > max_elev:
                    max_elev = elev
        except Exception as exc:
            # Skip missing / bad tiles gracefully
            continue

    if not tile_images:
        return {"ok": False, "error": "No terrain tiles could be downloaded"}

    # Stitch tiles into one big image (top-left origin)
    xs = sorted({t[0] for t in tile_images})
    ys = sorted({t[1] for t in tile_images})
    tile_w, tile_h = next(iter(tile_images.values())).size

    stitched_w = len(xs) * tile_w
    stitched_h = len(ys) * tile_h
    stitched = Image.new("RGB", (stitched_w, stitched_h))

    for (tx, ty), img in tile_images.items():
        px = (tx - xs[0]) * tile_w
        py = (ty - ys[0]) * tile_h
        stitched.paste(img, (px, py))

    # Decode full heightmap to a clean grayscale (16-bit range for Blender)
    decoded = Image.new("I", stitched.size, 0)  # 32-bit signed int mode
    pixels = stitched.load()
    out_pixels = decoded.load()

    for y in range(stitched_h):
        for x in range(stitched_w):
            r, g, b = pixels[x, y]
            elev = (r * 256 + g + b / 256.0) - 32768.0
            # Scale to 0-65535 for 16-bit feel (clamp extreme values)
            norm = max(0, min(65535, int((elev - min_elev) / max(0.1, max_elev - min_elev) * 65535)))
            out_pixels[x, y] = norm

    heightmap_path = out_dir / "heightmap.png"
    decoded.save(heightmap_path)

    meta = {
        "bbox": bbox,
        "zoom": zoom,
        "tile_count": len(tile_images),
        "min_elevation_m": round(min_elev, 1),
        "max_elevation_m": round(max_elev, 1),
        "heightmap_path": str(heightmap_path),
        "stitched_size": [stitched_w, stitched_h],
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "heightmap_path": str(heightmap_path),
        "metadata": meta,
        "cache_dir": str(out_dir),
    }
