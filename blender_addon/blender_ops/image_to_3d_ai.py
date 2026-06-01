"""AI image-to-3D provider integrations for Blender-side generation."""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector


MESHY_CREATE_URL = "https://api.meshy.ai/openapi/v1/image-to-3d"


class ImageTo3DError(RuntimeError):
    """Raised when a configured image-to-3D provider cannot finish a task."""


def _json_request(url: str, method: str = "GET", headers: dict[str, str] | None = None, payload: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    data = None
    req_headers = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ImageTo3DError(f"{method} {url} failed with HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise ImageTo3DError(f"{method} {url} failed: {exc}") from exc


def _download(url: str, path: str | Path, timeout: int = 300) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Remirdy-Blender-Studio/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, path.open("wb") as out:
            shutil.copyfileobj(resp, out)
    except urllib.error.URLError as exc:
        raise ImageTo3DError(f"download failed: {exc}") from exc
    return str(path)


def _data_uri(image_path: str) -> str:
    path = Path(image_path).expanduser()
    if not path.exists():
        raise ImageTo3DError(f"reference image does not exist: {path}")
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _import_glb(glb_path: str) -> list[str]:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=glb_path)
    imported = [obj for obj in bpy.data.objects if obj not in before]
    for obj in imported:
        obj.name = f"AI_Reconstructed_{obj.name}"
    return [obj.name for obj in imported]


def _imported_scene_objects() -> list[bpy.types.Object]:
    imported = [obj for obj in bpy.context.scene.objects if obj.name.startswith("AI_Reconstructed_")]
    return imported


def _root_imported_objects(imported: list[bpy.types.Object]) -> list[bpy.types.Object]:
    imported_set = set(imported)
    roots = [obj for obj in imported if obj.parent not in imported_set]
    return roots or imported


def _bounds(imported: list[bpy.types.Object]) -> tuple[Vector, Vector] | None:
    min_v = None
    max_v = None
    for obj in imported:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            min_v = world.copy() if min_v is None else Vector((min(min_v.x, world.x), min(min_v.y, world.y), min(min_v.z, world.z)))
            max_v = world.copy() if max_v is None else Vector((max(max_v.x, world.x), max(max_v.y, world.y), max(max_v.z, world.z)))
    if min_v is None or max_v is None:
        return None
    return min_v, max_v


def _apply_root_rotation(imported: list[bpy.types.Object], rotation: tuple[float, float, float]) -> None:
    for obj in _root_imported_objects(imported):
        obj.rotation_mode = 'XYZ'
        obj.rotation_euler.rotate_axis("X", rotation[0])
        obj.rotation_euler.rotate_axis("Y", rotation[1])
        obj.rotation_euler.rotate_axis("Z", rotation[2])
    bpy.context.view_layer.update()


def _auto_upright(imported: list[bpy.types.Object]) -> dict[str, Any]:
    b = _bounds(imported)
    if b is None:
        return {"rotated": False, "reason": "no bounds"}
    min_v, max_v = b
    dims = max_v - min_v
    axis_lengths = {"x": dims.x, "y": dims.y, "z": dims.z}
    longest = max(axis_lengths, key=axis_lengths.get)
    if longest == "z" and dims.z >= max(dims.x, dims.y) * 0.75:
        return {"rotated": False, "axis": "z", "dimensions_before": [dims.x, dims.y, dims.z]}
    if longest == "x":
        _apply_root_rotation(imported, (0.0, -1.57079632679, 0.0))
    elif longest == "y":
        _apply_root_rotation(imported, (1.57079632679, 0.0, 0.0))
    b2 = _bounds(imported)
    after = (b2[1] - b2[0]) if b2 else Vector((0, 0, 0))
    return {
        "rotated": longest in {"x", "y"},
        "axis": longest,
        "dimensions_before": [round(dims.x, 4), round(dims.y, 4), round(dims.z, 4)],
        "dimensions_after": [round(after.x, 4), round(after.y, 4), round(after.z, 4)],
    }


def _fit_imported_scene(imported_names: list[str] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = dict(params or {})
    if imported_names is not None:
        imported = [bpy.data.objects.get(name) for name in imported_names if bpy.data.objects.get(name)]
    else:
        imported = _imported_scene_objects()
    if not imported:
        return {"object_count": 0, "fit": False}
    bpy.ops.object.select_all(action="DESELECT")
    for obj in imported:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = imported[0]
    try:
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    except Exception:
        pass

    upright = {"rotated": False}
    if params.get("auto_upright", True):
        upright = _auto_upright(imported)

    b = _bounds(imported)
    if b is None:
        return {"object_count": len(imported), "fit": False, "upright": upright}
    min_v, max_v = b
    height = max(max_v.z - min_v.z, 0.001)
    target_height = float(params.get("target_height") or os.environ.get("REMIRDY_IMPORTED_TARGET_HEIGHT", "2.7"))
    scale = target_height / height
    center_x = (min_v.x + max_v.x) * 0.5
    center_y = (min_v.y + max_v.y) * 0.5
    for obj in _root_imported_objects(imported):
        obj.scale *= scale
        obj.location.x -= center_x * scale
        obj.location.y -= center_y * scale
        obj.location.z -= min_v.z * scale
    bpy.context.view_layer.update()
    b2 = _bounds(imported)
    dims = (b2[1] - b2[0]) if b2 else Vector((0, 0, 0))
    return {
        "object_count": len(imported),
        "fit": True,
        "upright": upright,
        "target_height": target_height,
        "dimensions": [round(dims.x, 4), round(dims.y, 4), round(dims.z, 4)],
    }


def frame_imported_asset_camera(filename: str | None = None) -> dict[str, Any]:
    imported = _imported_scene_objects()
    b = _bounds(imported)
    if b is None:
        return {"framed": False, "reason": "no imported bounds"}
    min_v, max_v = b
    center = (min_v + max_v) * 0.5
    dims = max_v - min_v
    size = max(dims.x, dims.y, dims.z, 0.1)
    for obj in list(bpy.context.scene.objects):
        if obj.type == "CAMERA" and obj.name.startswith(("Camera_", "ImportedAsset_")):
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.object.camera_add(location=(center.x, center.y - size * 2.45, center.z + size * 0.35))
    cam = bpy.context.object
    cam.name = "ImportedAsset_Camera"
    cam.data.lens = 55
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    bpy.context.scene.render.resolution_x = 1200
    bpy.context.scene.render.resolution_y = 1600
    if filename:
        bpy.context.scene.render.filepath = filename
    return {
        "framed": True,
        "camera": cam.name,
        "center": [round(center.x, 4), round(center.y, 4), round(center.z, 4)],
        "dimensions": [round(dims.x, 4), round(dims.y, 4), round(dims.z, 4)],
    }


def create_with_meshy(reference_image: str, glb_path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Generate a textured GLB from one image through Meshy Image-to-3D."""
    api_key = os.environ.get("MESHY_API_KEY") or os.environ.get("REMIRDY_MESHY_API_KEY")
    if not api_key:
        raise ImageTo3DError("MESHY_API_KEY or REMIRDY_MESHY_API_KEY is not set")
    params = dict(params or {})
    wait_seconds = int(params.get("wait_seconds") or os.environ.get("REMIRDY_IMAGE_TO_3D_WAIT_SECONDS", "900"))
    poll_interval = max(5, int(params.get("poll_interval") or 8))
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "image_url": _data_uri(reference_image),
        "ai_model": params.get("ai_model", os.environ.get("REMIRDY_MESHY_MODEL", "latest")),
        "enable_pbr": True,
        "should_texture": True,
        "should_remesh": True,
        "target_polycount": int(params.get("target_polycount") or os.environ.get("REMIRDY_TARGET_POLYCOUNT", "100000")),
        "topology": params.get("topology", "quad"),
        "pose_mode": params.get("pose_mode", "a-pose"),
        "target_formats": ["glb"],
        "multi_view_thumbnails": True,
        "remove_lighting": True,
    }

    created = _json_request(MESHY_CREATE_URL, method="POST", headers=headers, payload=payload, timeout=90)
    task_id = created.get("result")
    if not task_id:
        raise ImageTo3DError(f"Meshy did not return a task id: {created}")

    deadline = time.time() + wait_seconds
    last_status: dict[str, Any] = {}
    while time.time() < deadline:
        status = _json_request(f"{MESHY_CREATE_URL}/{task_id}", headers=headers, timeout=60)
        last_status = status
        state = status.get("status")
        if state == "SUCCEEDED":
            model_url = (status.get("model_urls") or {}).get("glb")
            if not model_url:
                raise ImageTo3DError(f"Meshy task succeeded without a GLB URL: {status}")
            _download(model_url, glb_path)
            imported_names = _import_glb(glb_path)
            fit_info = _fit_imported_scene(imported_names, params)
            return {
                "provider": "meshy",
                "task_id": task_id,
                "imported_objects": imported_names,
                "fit_info": fit_info,
                "model_url": model_url,
                "thumbnail_url": status.get("thumbnail_url"),
                "progress": status.get("progress"),
                "consumed_credits": status.get("consumed_credits"),
            }
        if state in {"FAILED", "CANCELED", "EXPIRED"}:
            raise ImageTo3DError(f"Meshy task ended with {state}: {status.get('task_error')}")
        time.sleep(poll_interval)
    raise ImageTo3DError(f"Meshy task timed out after {wait_seconds}s; last status: {last_status}")


def create_with_local_command(reference_image: str, glb_path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run an on-machine image-to-3D model command and import its GLB.

    Configure with REMIRDY_LOCAL_IMAGE_TO_3D_COMMAND, for example:
      python /models/TripoSR/run.py --image "{image}" --output "{output}"

    Available placeholders:
      {image}  absolute reference image path
      {output} target GLB path expected by Blender
      {workdir} directory beside the target GLB for intermediate files
    """
    params = dict(params or {})
    command_template = (
        params.get("local_command")
        or os.environ.get("REMIRDY_LOCAL_IMAGE_TO_3D_COMMAND")
        or os.environ.get("REMIRDY_IMAGE_TO_3D_COMMAND")
    )
    if not command_template:
        raise ImageTo3DError(
            "local image-to-3d command is not configured. Set "
            "REMIRDY_LOCAL_IMAGE_TO_3D_COMMAND to a model runner that writes a GLB."
        )
    image = str(Path(reference_image).expanduser())
    output = str(Path(glb_path).expanduser())
    workdir = str(Path(output).parent / f"{Path(output).stem}_local_ai_work")
    Path(workdir).mkdir(parents=True, exist_ok=True)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    command = command_template.format(image=image, output=output, workdir=workdir)
    timeout = int(params.get("wait_seconds") or os.environ.get("REMIRDY_IMAGE_TO_3D_WAIT_SECONDS", "3600"))

    started = time.time()
    proc = subprocess.run(
        command,
        shell=True,
        cwd=workdir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise ImageTo3DError(
            "local image-to-3d command failed "
            f"(exit {proc.returncode}). stdout: {proc.stdout[-2000:]} stderr: {proc.stderr[-2000:]}"
        )
    if not Path(output).exists():
        raise ImageTo3DError(
            "local image-to-3d command finished but did not create the expected GLB: "
            f"{output}. stdout: {proc.stdout[-2000:]} stderr: {proc.stderr[-2000:]}"
        )
    imported_names = _import_glb(output)
    fit_info = _fit_imported_scene(imported_names, params)
    return {
        "provider": "local_command",
        "command": command,
        "runtime_seconds": round(time.time() - started, 2),
        "imported_objects": imported_names,
        "fit_info": fit_info,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def create_ai_image_to_3d(reference_image: str, glb_path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    provider = (params or {}).get("provider") or os.environ.get("REMIRDY_IMAGE_TO_3D_PROVIDER", "local")
    provider = provider.lower().strip()
    if provider in {"local", "local_command", "mcp"}:
        return create_with_local_command(reference_image, glb_path, params)
    if provider == "meshy":
        return create_with_meshy(reference_image, glb_path, params)
    if provider in {"auto", "parallel"}:
        errors = []
        for candidate in ("local", "meshy"):
            try:
                return create_ai_image_to_3d(reference_image, glb_path, {**(params or {}), "provider": candidate})
            except ImageTo3DError as exc:
                errors.append(f"{candidate}: {exc}")
        raise ImageTo3DError("; ".join(errors))
    raise ImageTo3DError(f"unsupported image-to-3d provider: {provider}")
