"""
ComfyUI / Stable Diffusion Local Provider.

Supports two local backends (auto-detected):
  • ComfyUI  — REST API on http://localhost:8188  (recommended)
  • Automatic1111 (A1111) — REST API on http://localhost:7860

Use cases
---------
  txt2img       : Generate a texture / concept art from a prompt
  img2img       : Re-style an existing render/image (style transfer)
  texture_synth : Generate a seamless PBR texture from a description
  depth2img     : Depth-guided generation (uses Blender depth pass)
  inpaint       : Fill a masked region (e.g. replace a texture patch)

Environment variables
---------------------
COMFYUI_URL   : ComfyUI base URL   (default http://localhost:8188)
A1111_URL     : A1111 base URL     (default http://localhost:7860)
SD_BACKEND    : "comfyui" | "a1111" | "auto" (default "auto")
SD_MODEL      : Model checkpoint name override
"""
from __future__ import annotations

import base64
import io
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

from ..utils.logging_utils import get_logger

log = get_logger("remirdy.providers.sd")

# ── defaults ─────────────────────────────────────────────────────────────────

COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://localhost:8188")
A1111_URL   = os.environ.get("A1111_URL",   "http://localhost:7860")
SD_BACKEND  = os.environ.get("SD_BACKEND",  "auto")


# ── health checks ─────────────────────────────────────────────────────────────

def _ping(url: str, path: str = "/", timeout: int = 3) -> bool:
    try:
        urllib.request.urlopen(f"{url}{path}", timeout=timeout)
        return True
    except Exception:
        return False


def comfyui_available() -> bool:
    return _ping(COMFYUI_URL, "/system_stats")


def a1111_available() -> bool:
    return _ping(A1111_URL, "/sdapi/v1/sd-models")


def detect_backend() -> str | None:
    backend = SD_BACKEND.lower()
    if backend == "comfyui":
        return "comfyui" if comfyui_available() else None
    if backend == "a1111":
        return "a1111" if a1111_available() else None
    # auto
    if comfyui_available():
        return "comfyui"
    if a1111_available():
        return "a1111"
    return None


def is_available() -> bool:
    return detect_backend() is not None


def status() -> dict[str, Any]:
    backend = detect_backend()
    return {
        "name": "local_sd",
        "configured": backend is not None,
        "backend": backend,
        "comfyui_url": COMFYUI_URL,
        "a1111_url": A1111_URL,
        "comfyui_online": comfyui_available(),
        "a1111_online": a1111_available(),
    }


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _img_to_b64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("utf-8")


def _b64_to_file(b64: str, out_path: str) -> str:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(base64.b64decode(b64))
    return out_path


# ═════════════════════════════════════════════════════════════════════════════
# Automatic1111 backend
# ═════════════════════════════════════════════════════════════════════════════

def _a1111_txt2img(
    prompt: str,
    negative_prompt: str = "ugly, blurry, bad anatomy, watermark",
    width: int = 512,
    height: int = 512,
    steps: int = 25,
    cfg_scale: float = 7.5,
    sampler: str = "DPM++ 2M Karras",
    seed: int = -1,
    model: str | None = None,
) -> list[str]:
    """Returns list of base64-encoded PNG images."""
    payload: dict[str, Any] = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "sampler_name": sampler,
        "seed": seed,
        "batch_size": 1,
    }
    if model:
        payload["override_settings"] = {"sd_model_checkpoint": model}

    resp = _post(f"{A1111_URL}/sdapi/v1/txt2img", payload)
    return resp.get("images", [])


def _a1111_img2img(
    init_image_path: str,
    prompt: str,
    negative_prompt: str = "ugly, blurry",
    denoising_strength: float = 0.65,
    width: int = 512,
    height: int = 512,
    steps: int = 25,
    cfg_scale: float = 7.5,
) -> list[str]:
    b64 = _img_to_b64(init_image_path)
    payload = {
        "init_images": [b64],
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "denoising_strength": denoising_strength,
        "width": width,
        "height": height,
        "steps": steps,
        "cfg_scale": cfg_scale,
    }
    resp = _post(f"{A1111_URL}/sdapi/v1/img2img", payload)
    return resp.get("images", [])


def _a1111_inpaint(
    init_image_path: str,
    mask_image_path: str,
    prompt: str,
    denoising_strength: float = 0.85,
) -> list[str]:
    b64_img  = _img_to_b64(init_image_path)
    b64_mask = _img_to_b64(mask_image_path)
    payload = {
        "init_images": [b64_img],
        "mask": b64_mask,
        "prompt": prompt,
        "denoising_strength": denoising_strength,
        "inpainting_fill": 1,
        "inpaint_full_res": True,
    }
    resp = _post(f"{A1111_URL}/sdapi/v1/img2img", payload)
    return resp.get("images", [])


# ═════════════════════════════════════════════════════════════════════════════
# ComfyUI backend — workflow-based
# ═════════════════════════════════════════════════════════════════════════════

def _comfyui_queue_prompt(workflow: dict) -> str:
    """Queue a workflow and return prompt_id."""
    resp = _post(f"{COMFYUI_URL}/prompt", {"prompt": workflow})
    return resp["prompt_id"]


def _comfyui_wait_for_output(prompt_id: str, timeout: int = 300) -> list[str]:
    """Poll until the prompt is complete, return list of output image filenames."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        hist = _get(f"{COMFYUI_URL}/history/{prompt_id}")
        if prompt_id in hist:
            outputs = hist[prompt_id].get("outputs", {})
            images = []
            for node_id, node_out in outputs.items():
                for img in node_out.get("images", []):
                    images.append(img["filename"])
            return images
        time.sleep(2)
    raise TimeoutError(f"ComfyUI prompt {prompt_id} timed out after {timeout}s")


def _comfyui_download_image(filename: str, out_path: str) -> str:
    url = f"{COMFYUI_URL}/view?filename={filename}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(resp.read())
    return out_path


def _comfyui_txt2img_workflow(
    prompt: str,
    negative_prompt: str = "ugly, blurry",
    width: int = 512,
    height: int = 512,
    steps: int = 25,
    cfg: float = 7.5,
    seed: int = -1,
    model: str = "v1-5-pruned-emaonly.ckpt",
) -> dict:
    """Minimal ComfyUI workflow for txt2img."""
    if seed == -1:
        import random
        seed = random.randint(0, 2**32 - 1)
    return {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": model}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["4", 1]}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0],
                "latent_image": ["5", 0], "seed": seed, "steps": steps,
                "cfg": cfg, "sampler_name": "dpm_2_ancestral", "scheduler": "karras",
                "denoise": 1.0,
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "remirdy_"}},
    }


# ═════════════════════════════════════════════════════════════════════════════
# Unified public API
# ═════════════════════════════════════════════════════════════════════════════

def _workspace_sd(*parts: str) -> str:
    root = os.environ.get("REMIRDY_WORKSPACE", str(Path.home() / "RemirdyWorkspace"))
    out = Path(root) / "outputs" / "stable_diffusion"
    out.mkdir(parents=True, exist_ok=True)
    return str(out.joinpath(*parts))


def txt2img(
    prompt: str,
    output_path: str | None = None,
    negative_prompt: str = "ugly, blurry, bad anatomy, watermark, low quality",
    width: int = 512,
    height: int = 512,
    steps: int = 25,
    cfg_scale: float = 7.5,
    seed: int = -1,
    model: str | None = None,
) -> dict[str, Any]:
    """Generate an image from a text prompt using the local SD backend."""
    backend = detect_backend()
    if not backend:
        return {"ok": False, "error": "No local SD backend found. Start ComfyUI or A1111."}

    safe = "".join(c if c.isalnum() else "_" for c in prompt[:30])
    out = output_path or _workspace_sd(f"txt2img_{safe}.png")

    try:
        if backend == "a1111":
            images = _a1111_txt2img(
                prompt, negative_prompt, width, height, steps, cfg_scale, seed=seed,
                model=model or os.environ.get("SD_MODEL"),
            )
            if not images:
                return {"ok": False, "error": "A1111 returned no images"}
            _b64_to_file(images[0], out)
        else:  # comfyui
            wf = _comfyui_txt2img_workflow(
                prompt, negative_prompt, width, height, steps, cfg_scale, seed,
                model=model or os.environ.get("SD_MODEL", "v1-5-pruned-emaonly.ckpt"),
            )
            pid = _comfyui_queue_prompt(wf)
            filenames = _comfyui_wait_for_output(pid)
            if not filenames:
                return {"ok": False, "error": "ComfyUI returned no output images"}
            _comfyui_download_image(filenames[0], out)

        return {"ok": True, "backend": backend, "image_path": out, "prompt": prompt}
    except Exception as exc:
        log.exception("[SD] txt2img failed")
        return {"ok": False, "error": str(exc)}


def img2img(
    init_image_path: str,
    prompt: str,
    output_path: str | None = None,
    negative_prompt: str = "ugly, blurry, low quality",
    denoising_strength: float = 0.65,
    width: int = 512,
    height: int = 512,
    steps: int = 25,
) -> dict[str, Any]:
    """Re-style an existing image (render, concept art) using SD img2img."""
    backend = detect_backend()
    if not backend:
        return {"ok": False, "error": "No local SD backend available."}

    safe = "".join(c if c.isalnum() else "_" for c in prompt[:30])
    out = output_path or _workspace_sd(f"img2img_{safe}.png")

    try:
        if backend == "a1111":
            images = _a1111_img2img(
                init_image_path, prompt, negative_prompt,
                denoising_strength, width, height, steps,
            )
            if not images:
                return {"ok": False, "error": "A1111 img2img returned no images"}
            _b64_to_file(images[0], out)
        else:
            # ComfyUI img2img workflow
            b64 = _img_to_b64(init_image_path)
            import random
            wf = {
                "1":  {"class_type": "LoadImageBase64", "inputs": {"image": b64}},
                "4":  {"class_type": "CheckpointLoaderSimple",
                       "inputs": {"ckpt_name": os.environ.get("SD_MODEL", "v1-5-pruned-emaonly.ckpt")}},
                "6":  {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
                "7":  {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["4", 1]}},
                "10": {"class_type": "VAEEncode", "inputs": {"pixels": ["1", 0], "vae": ["4", 2]}},
                "3":  {
                    "class_type": "KSampler",
                    "inputs": {
                        "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0],
                        "latent_image": ["10", 0], "seed": random.randint(0, 2**32 - 1),
                        "steps": steps, "cfg": 7.5, "sampler_name": "euler_a",
                        "scheduler": "karras", "denoise": denoising_strength,
                    },
                },
                "8":  {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
                "9":  {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "remirdy_i2i_"}},
            }
            pid = _comfyui_queue_prompt(wf)
            filenames = _comfyui_wait_for_output(pid)
            if not filenames:
                return {"ok": False, "error": "ComfyUI img2img returned no output"}
            _comfyui_download_image(filenames[0], out)

        return {"ok": True, "backend": backend, "image_path": out, "source": init_image_path}
    except Exception as exc:
        log.exception("[SD] img2img failed")
        return {"ok": False, "error": str(exc)}


def texture_synthesis(
    description: str,
    output_path: str | None = None,
    resolution: int = 512,
    seamless: bool = True,
) -> dict[str, Any]:
    """Generate a seamless PBR-ready texture from a description."""
    seamless_suffix = ", seamless texture, tileable, no borders" if seamless else ""
    full_prompt = (
        f"{description}, PBR texture, albedo map, high detail, "
        f"game-ready material{seamless_suffix}"
    )
    negative = "watermark, text, logo, seams, visible borders, gradient"
    safe = "".join(c if c.isalnum() else "_" for c in description[:30])
    out = output_path or _workspace_sd(f"texture_{safe}.png")
    return txt2img(
        full_prompt, out,
        negative_prompt=negative,
        width=resolution, height=resolution,
        steps=30, cfg_scale=8.0,
    )


def style_transfer_render(
    render_path: str,
    style_prompt: str,
    output_path: str | None = None,
    strength: float = 0.55,
) -> dict[str, Any]:
    """Apply an artistic style to a Blender render via img2img."""
    safe = "".join(c if c.isalnum() else "_" for c in style_prompt[:30])
    out = output_path or _workspace_sd(f"styled_{safe}.png")
    return img2img(
        init_image_path=render_path,
        prompt=style_prompt,
        output_path=out,
        denoising_strength=strength,
    )
