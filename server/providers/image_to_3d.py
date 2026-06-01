"""Concrete image-to-3D provider adapters.

Hosted: Meshy, Tripo, Hyper3D Rodin.
Local:  Hunyuan3D (self-hosted HTTP endpoint), TRELLIS / generic local command.

All adapters degrade honestly: if their key/endpoint is absent they report it
through ``missing_config`` and the registry skips them in an ``auto`` chain.
"""
from __future__ import annotations

import base64
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from ..utils.http_utils import download, request_json
from .base import (
    GenerationOptions,
    ImageTo3DProvider,
    ProviderError,
    ProviderNotConfigured,
    ProviderResult,
)


def _data_uri(image_path: str) -> str:
    path = Path(image_path).expanduser()
    if not path.exists():
        raise ProviderError(f"reference image does not exist: {path}")
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/webp" if suffix == ".webp" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _poll(fetch, *, is_done, is_failed, wait_seconds: int, poll_interval: int, label: str) -> dict[str, Any]:
    deadline = time.time() + wait_seconds
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = fetch()
        if is_done(last):
            return last
        if is_failed(last):
            raise ProviderError(f"{label} task failed: {last}")
        time.sleep(poll_interval)
    raise ProviderError(f"{label} timed out after {wait_seconds}s; last status: {last}")


# --------------------------------------------------------------------------- #
# Hosted providers
# --------------------------------------------------------------------------- #
class MeshyProvider(ImageTo3DProvider):
    name = "meshy"
    kind = "hosted"
    supports_multiview = True
    homepage = "https://www.meshy.ai"
    BASE = "https://api.meshy.ai/openapi/v1/image-to-3d"

    def _required_env(self) -> list[str]:
        return ["MESHY_API_KEY", "REMIRDY_MESHY_API_KEY"]

    def generate(self, image_path: str, glb_path: str, opts: GenerationOptions) -> ProviderResult:
        key = self._api_key()
        glb_path = self._ensure_parent(glb_path)
        headers = {"Authorization": f"Bearer {key}"}
        started = time.time()
        payload: dict[str, Any] = {
            "image_url": _data_uri(image_path),
            "ai_model": opts.extra.get("ai_model", os.environ.get("REMIRDY_MESHY_MODEL", "latest")),
            "enable_pbr": opts.enable_pbr,
            "should_texture": opts.should_texture,
            "should_remesh": True,
            "target_polycount": opts.target_polycount,
            "topology": opts.topology,
            "pose_mode": opts.pose_mode,
            "target_formats": ["glb"],
            "multi_view_thumbnails": True,
            "remove_lighting": True,
        }
        if opts.extra_views and self.supports_multiview:
            # Meshy multi-image conditioning (front + side/back).
            payload["multi_image_urls"] = [_data_uri(image_path)] + [
                _data_uri(v) for v in opts.extra_views
            ]
        created = request_json(self.BASE, "POST", headers, payload, timeout=90)
        task_id = created.get("result") if isinstance(created, dict) else None
        if not task_id:
            raise ProviderError(f"Meshy returned no task id: {created}")

        status = _poll(
            lambda: request_json(f"{self.BASE}/{task_id}", headers=headers, timeout=60),
            is_done=lambda s: s.get("status") == "SUCCEEDED",
            is_failed=lambda s: s.get("status") in {"FAILED", "CANCELED", "EXPIRED"},
            wait_seconds=opts.wait_seconds,
            poll_interval=opts.poll_interval,
            label="Meshy",
        )
        model_url = (status.get("model_urls") or {}).get("glb")
        if not model_url:
            raise ProviderError(f"Meshy succeeded without GLB url: {status}")
        download(model_url, glb_path, timeout=300)
        return ProviderResult(
            provider=self.name,
            glb_path=glb_path,
            task_id=task_id,
            thumbnail_url=status.get("thumbnail_url"),
            runtime_seconds=round(time.time() - started, 2),
            cost_note=str(status.get("consumed_credits")),
            meta={"progress": status.get("progress")},
        )


class TripoProvider(ImageTo3DProvider):
    name = "tripo"
    kind = "hosted"
    supports_multiview = True
    homepage = "https://www.tripo3d.ai"
    BASE = "https://api.tripo3d.ai/v2/openapi"

    def _required_env(self) -> list[str]:
        return ["TRIPO_API_KEY", "REMIRDY_TRIPO_API_KEY"]

    def _upload(self, key: str, image_path: str) -> str:
        # Tripo accepts an uploaded image token or an inline data URI; we use the
        # base64 inline form to avoid multipart handling in stdlib.
        return _data_uri(image_path)

    def generate(self, image_path: str, glb_path: str, opts: GenerationOptions) -> ProviderResult:
        key = self._api_key()
        glb_path = self._ensure_parent(glb_path)
        headers = {"Authorization": f"Bearer {key}"}
        started = time.time()
        payload: dict[str, Any] = {
            "type": "image_to_model",
            "file": {"type": "data_uri", "url": self._upload(key, image_path)},
            "model_version": opts.extra.get("model_version", "v2.5-20250123"),
            "texture": opts.should_texture,
            "pbr": opts.enable_pbr,
            "face_limit": opts.target_polycount,
            "quad": opts.topology == "quad",
        }
        if opts.seed is not None:
            payload["model_seed"] = opts.seed
        created = request_json(f"{self.BASE}/task", "POST", headers, payload, timeout=90)
        task_id = (created.get("data") or {}).get("task_id") if isinstance(created, dict) else None
        if not task_id:
            raise ProviderError(f"Tripo returned no task id: {created}")

        def fetch():
            r = request_json(f"{self.BASE}/task/{task_id}", headers=headers, timeout=60)
            return (r.get("data") or {}) if isinstance(r, dict) else {}

        status = _poll(
            fetch,
            is_done=lambda s: s.get("status") == "success",
            is_failed=lambda s: s.get("status") in {"failed", "cancelled", "expired", "banned"},
            wait_seconds=opts.wait_seconds,
            poll_interval=opts.poll_interval,
            label="Tripo",
        )
        output = status.get("output") or {}
        model_url = output.get("pbr_model") or output.get("model")
        if not model_url:
            raise ProviderError(f"Tripo succeeded without model url: {status}")
        download(model_url, glb_path, timeout=300)
        return ProviderResult(
            provider=self.name,
            glb_path=glb_path,
            task_id=task_id,
            thumbnail_url=output.get("rendered_image"),
            runtime_seconds=round(time.time() - started, 2),
            meta={"progress": status.get("progress")},
        )


class RodinProvider(ImageTo3DProvider):
    name = "rodin"
    kind = "hosted"
    supports_multiview = True
    homepage = "https://hyper3d.ai"
    BASE = "https://hyperhuman.deemos.com/api/v2"

    def _required_env(self) -> list[str]:
        return ["RODIN_API_KEY", "REMIRDY_RODIN_API_KEY"]

    def generate(self, image_path: str, glb_path: str, opts: GenerationOptions) -> ProviderResult:
        key = self._api_key()
        glb_path = self._ensure_parent(glb_path)
        headers = {"Authorization": f"Bearer {key}"}
        started = time.time()
        images = [_data_uri(image_path)] + [_data_uri(v) for v in opts.extra_views]
        payload: dict[str, Any] = {
            "images": images,
            "tier": opts.extra.get("tier", "Regular" if opts.quality in {"draft", "regular"} else "Detail"),
            "geometry_file_format": "glb",
            "material": "PBR" if opts.enable_pbr else "Shaded",
            "quality": "high" if opts.quality in {"high", "ultra"} else "medium",
            "use_hyper": True,
            "mesh_mode": "Quad" if opts.topology == "quad" else "Raw",
        }
        if opts.seed is not None:
            payload["seed"] = opts.seed
        created = request_json(f"{self.BASE}/rodin", "POST", headers, payload, timeout=90)
        task_uuid = created.get("uuid") if isinstance(created, dict) else None
        subscription = (created or {}).get("jobs", {}).get("subscription_key")
        if not task_uuid:
            raise ProviderError(f"Rodin returned no task uuid: {created}")

        def fetch():
            return request_json(
                f"{self.BASE}/status",
                "POST",
                headers,
                {"subscription_key": subscription} if subscription else {"task_uuid": task_uuid},
                timeout=60,
            )

        _poll(
            fetch,
            is_done=lambda s: (s.get("status") or "").lower() in {"done", "succeeded", "success"},
            is_failed=lambda s: (s.get("status") or "").lower() in {"failed", "error"},
            wait_seconds=opts.wait_seconds,
            poll_interval=opts.poll_interval,
            label="Rodin",
        )
        result = request_json(
            f"{self.BASE}/download", "POST", headers, {"task_uuid": task_uuid}, timeout=60
        )
        files = result.get("list") or result.get("files") or []
        glb_url = next((f.get("url") for f in files if str(f.get("name", "")).lower().endswith(".glb")), None)
        if not glb_url:
            raise ProviderError(f"Rodin produced no GLB: {result}")
        download(glb_url, glb_path, timeout=300)
        return ProviderResult(
            provider=self.name,
            glb_path=glb_path,
            task_id=task_uuid,
            runtime_seconds=round(time.time() - started, 2),
        )


# --------------------------------------------------------------------------- #
# Local / self-hosted providers
# --------------------------------------------------------------------------- #
class Hunyuan3DProvider(ImageTo3DProvider):
    """Self-hosted Hunyuan3D HTTP endpoint (e.g. the gradio/api server)."""

    name = "hunyuan3d"
    kind = "local"
    supports_multiview = False
    homepage = "https://github.com/Tencent/Hunyuan3D-2"

    def _required_env(self) -> list[str]:
        return ["HUNYUAN3D_ENDPOINT", "HUNYUAN3D_API_KEY"]

    def generate(self, image_path: str, glb_path: str, opts: GenerationOptions) -> ProviderResult:
        endpoint = os.environ.get("HUNYUAN3D_ENDPOINT")
        if not endpoint:
            raise ProviderNotConfigured("hunyuan3d: set HUNYUAN3D_ENDPOINT to your server URL")
        glb_path = self._ensure_parent(glb_path)
        headers = {}
        if os.environ.get("HUNYUAN3D_API_KEY"):
            headers["Authorization"] = f"Bearer {os.environ['HUNYUAN3D_API_KEY']}"
        started = time.time()
        payload = {
            "image": _data_uri(image_path),
            "texture": opts.should_texture,
            "face_count": opts.target_polycount,
            "seed": opts.seed if opts.seed is not None else 1234,
        }
        created = request_json(endpoint.rstrip("/") + "/generate", "POST", headers, payload, timeout=120)
        # Endpoint may return a GLB url or a job id depending on deployment.
        model_url = created.get("glb_url") or created.get("model_url") if isinstance(created, dict) else None
        if not model_url and isinstance(created, dict) and created.get("job_id"):
            job_id = created["job_id"]
            status = _poll(
                lambda: request_json(f"{endpoint.rstrip('/')}/status/{job_id}", headers=headers, timeout=60),
                is_done=lambda s: bool(s.get("glb_url") or s.get("model_url")),
                is_failed=lambda s: s.get("status") in {"failed", "error"},
                wait_seconds=opts.wait_seconds,
                poll_interval=opts.poll_interval,
                label="Hunyuan3D",
            )
            model_url = status.get("glb_url") or status.get("model_url")
        if not model_url:
            raise ProviderError(f"Hunyuan3D produced no model url: {created}")
        if model_url.startswith("http"):
            download(model_url, glb_path, headers=headers, timeout=600)
        else:
            # local filesystem path returned by a co-located server
            Path(glb_path).write_bytes(Path(model_url).read_bytes())
        return ProviderResult(
            provider=self.name,
            glb_path=glb_path,
            runtime_seconds=round(time.time() - started, 2),
            cost_note="self-hosted (no API cost)",
        )


class LocalCommandProvider(ImageTo3DProvider):
    """Run any on-machine model runner (TRELLIS, TripoSR, InstantMesh, ...).

    Configure REMIRDY_LOCAL_IMAGE_TO_3D_COMMAND with {image}/{output}/{workdir}
    placeholders. This is the escape hatch for models without a hosted API.
    """

    name = "local_command"
    kind = "local"
    supports_multiview = False
    homepage = ""

    def _required_env(self) -> list[str]:
        return ["REMIRDY_LOCAL_IMAGE_TO_3D_COMMAND", "REMIRDY_IMAGE_TO_3D_COMMAND"]

    def generate(self, image_path: str, glb_path: str, opts: GenerationOptions) -> ProviderResult:
        template = (
            opts.extra.get("local_command")
            or os.environ.get("REMIRDY_LOCAL_IMAGE_TO_3D_COMMAND")
            or os.environ.get("REMIRDY_IMAGE_TO_3D_COMMAND")
        )
        if not template:
            raise ProviderNotConfigured(
                "local_command: set REMIRDY_LOCAL_IMAGE_TO_3D_COMMAND to a runner "
                "that writes a GLB to {output}"
            )
        glb_path = self._ensure_parent(glb_path)
        image = str(Path(image_path).expanduser())
        workdir = str(Path(glb_path).parent / f"{Path(glb_path).stem}_work")
        Path(workdir).mkdir(parents=True, exist_ok=True)
        command = template.format(image=image, output=glb_path, workdir=workdir)
        started = time.time()
        proc = subprocess.run(
            command, shell=True, cwd=workdir, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=opts.wait_seconds, check=False,
        )
        if proc.returncode != 0 or not Path(glb_path).exists():
            raise ProviderError(
                f"local command failed (exit {proc.returncode}). "
                f"stderr: {proc.stderr[-1500:]}"
            )
        return ProviderResult(
            provider=self.name,
            glb_path=glb_path,
            runtime_seconds=round(time.time() - started, 2),
            cost_note="local compute (no API cost)",
            meta={"command": command, "stdout_tail": proc.stdout[-1000:]},
        )
