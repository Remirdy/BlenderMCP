"""Install-free, API-free image -> 3D inside Blender.

True photogrammetric reconstruction needs an external neural model (TripoSR,
Meshy, etc.). When the user explicitly does NOT want any API or local install,
we still produce a *real, colored, volumetric mesh* — not a flat plane — using
only Blender's bundled numpy + bmesh:

  1. Read the image pixels into numpy.
  2. Build a foreground MASK (alpha channel, or background-colour rejection)
     and cut the silhouette so the model has the subject's actual outline.
  3. Displace the front surface by per-pixel luminance -> bas-relief detail
     (folds, features, depth cues read from shading).
  4. Solidify -> real thickness, then bevel + subdivision -> rounded,
     professional edges instead of a paper-thin cutout.
  5. Project the original image as the colour texture so the result is
     textured, not grey.

The output is a single clean mesh, centered and uprighted, ready to export.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import bpy
import bmesh
import numpy as np
from mathutils import Vector

from . import helpers as H


def _load_pixels(image_path: str):
    """Return (rgba float32 HxWx4, width, height) with row 0 = TOP."""
    path = str(Path(image_path).expanduser())
    if not os.path.exists(path):
        raise FileNotFoundError(f"reference image does not exist: {path}")
    img = bpy.data.images.load(path, check_existing=True)
    w, h = img.size
    if w == 0 or h == 0:
        raise ValueError(f"image has zero size: {path}")
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    arr = buf.reshape(h, w, 4)
    # Blender stores bottom-to-top; flip so row 0 is the top of the picture.
    arr = arr[::-1, :, :]
    return arr, w, h, img


def _luminance(rgba):
    return (0.2126 * rgba[..., 0] + 0.7152 * rgba[..., 1] + 0.0722 * rgba[..., 2])


def _foreground_mask(rgba, threshold=0.12):
    """Boolean HxW mask of the subject vs background.

    Prefers a real alpha channel; otherwise rejects the dominant border colour.
    """
    h, w, _ = rgba.shape
    alpha = rgba[..., 3]
    if float(alpha.min()) < 0.95 and float(alpha.std()) > 0.05:
        return alpha > 0.5
    # No usable alpha: estimate background from the 4 corners / border ring.
    border = np.concatenate([
        rgba[0, :, :3].reshape(-1, 3),
        rgba[-1, :, :3].reshape(-1, 3),
        rgba[:, 0, :3].reshape(-1, 3),
        rgba[:, -1, :3].reshape(-1, 3),
    ], axis=0)
    bg = np.median(border, axis=0)
    dist = np.sqrt(((rgba[..., :3] - bg) ** 2).sum(axis=-1))
    mask = dist > threshold
    # If background rejection found almost nothing (busy photo), fall back to
    # "use the whole frame" so we still produce a relief.
    if mask.mean() < 0.02:
        mask = np.ones((h, w), dtype=bool)
    return mask


def _downsample_index(n_src, n_dst):
    return np.linspace(0, n_src - 1, n_dst).astype(int)


def build_image_model(
    image_path: str,
    name: str = "AI_ImageModel",
    mode: str = "model",          # 'model' (silhouette volume) | 'relief'
    max_res: int = 220,
    relief_depth: float = 0.18,
    thickness: float = 0.12,
    target_height: float = 2.4,
    smooth: bool = True,
) -> dict[str, Any]:
    rgba, w, h, img = _load_pixels(image_path)
    lum = _luminance(rgba)
    mask = _foreground_mask(rgba) if mode == "model" else np.ones((h, w), dtype=bool)

    # Resolution of the vertex grid (cap for performance, keep aspect).
    if w >= h:
        nx = min(max_res, w)
        ny = max(2, int(nx * h / w))
    else:
        ny = min(max_res, h)
        nx = max(2, int(ny * w / h))
    xi = _downsample_index(w, nx)
    yi = _downsample_index(h, ny)

    lum_s = lum[np.ix_(yi, xi)]
    mask_s = mask[np.ix_(yi, xi)]

    # World size: largest dimension -> target_height, preserve aspect.
    aspect = w / h
    if aspect >= 1.0:
        world_w = target_height
        world_h = target_height / aspect
    else:
        world_h = target_height
        world_w = target_height * aspect

    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    vgrid: dict[tuple, Any] = {}
    vert_uv: dict[Any, tuple] = {}

    for j in range(ny):
        for i in range(nx):
            if not mask_s[j, i]:
                continue
            u = i / (nx - 1)
            v = 1.0 - j / (ny - 1)
            x = (u - 0.5) * world_w
            z = (v - 0.5) * world_h
            # front surface pushed out by luminance -> bas-relief
            y = -lum_s[j, i] * relief_depth
            vert = bm.verts.new((x, y, z))
            vgrid[(i, j)] = vert
            vert_uv[vert] = (u, v)

    bm.verts.ensure_lookup_table()
    faces = 0
    for j in range(ny - 1):
        for i in range(nx - 1):
            corners = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            if all(c in vgrid for c in corners):
                try:
                    f = bm.faces.new([vgrid[c] for c in corners])
                except ValueError:
                    continue
                for loop in f.loops:
                    loop[uv_layer].uv = vert_uv[loop.vert]
                faces += 1

    if faces == 0:
        bm.free()
        raise ValueError("no foreground faces produced; try mode='relief'")

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    coll = H.get_or_create_collection("Props")
    bpy.context.scene.collection.objects.link(obj)
    H.link_to_collection(obj, coll)
    bpy.context.view_layer.objects.active = obj

    # --- give it real volume + clean edges ---
    sol = obj.modifiers.new("solidify", "SOLIDIFY")
    sol.thickness = thickness
    sol.offset = 0.0
    try:
        sol.use_even_offset = True
    except Exception:
        pass
    bev = obj.modifiers.new("bevel", "BEVEL")
    bev.width = min(thickness * 0.4, 0.03)
    bev.segments = 2
    if smooth:
        sub = obj.modifiers.new("smooth_subsurf", "SUBSURF")
        sub.levels = 1
        sub.render_levels = 2
        try:
            bpy.ops.object.shade_smooth()
        except Exception:
            pass
    obj.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")

    # --- textured material from the source image ---
    mat = bpy.data.materials.new(f"{name}_Mat")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF") or next(
        (n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.location = (-400, 200)
    if bsdf:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = 0.6
    obj.data.materials.append(mat)

    # center & upright
    try:
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    except Exception:
        pass
    obj.location = (0.0, 0.0, world_h * 0.5)

    return {
        "object": obj.name,
        "mode": mode,
        "grid": [nx, ny],
        "faces": faces,
        "world_size": [round(world_w, 3), round(world_h, 3)],
        "textured": True,
    }


def create_local_image_to_3d(reference_image: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Entry point used by the image-to-3D dispatcher (no API, no install)."""
    params = dict(params or {})
    name = params.get("name", "AI_Reconstructed_ImageModel")
    info = build_image_model(
        reference_image,
        name=name,
        mode=params.get("mode", "model"),
        max_res=int(params.get("max_res", 220)),
        relief_depth=float(params.get("relief_depth", 0.18)),
        thickness=float(params.get("thickness", 0.12)),
        target_height=float(params.get("target_height", 2.4)),
        smooth=bool(params.get("smooth", True)),
    )
    info["provider"] = "local_procedural"
    info["note"] = ("Generated with Blender's built-in numpy/bmesh — no API or "
                    "external model. Silhouette + luminance relief volume.")
    return info


# Registry-facing ops -------------------------------------------------------- #
def op_create_model_from_image(params):
    img = params.get("reference_image") or params.get("image")
    if not img:
        return {"ok": False, "error": "reference_image is required"}
    return create_local_image_to_3d(img, params)


def op_create_relief_from_image(params):
    img = params.get("reference_image") or params.get("image")
    if not img:
        return {"ok": False, "error": "reference_image is required"}
    p = dict(params)
    p["mode"] = "relief"
    return create_local_image_to_3d(img, p)
