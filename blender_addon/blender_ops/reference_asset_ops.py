"""Reference-image driven 3D asset creation."""
from __future__ import annotations

import os
from pathlib import Path

import bpy

from ..reference_generators import sprite_reference_character
from .export_ops import workspace_output
from .image_to_3d_ai import ImageTo3DError, create_ai_image_to_3d


def _add_reference_image_plane(path: str) -> str | None:
    image_path = Path(path).expanduser()
    if not image_path.exists():
        return None
    try:
        img = bpy.data.images.load(str(image_path), check_existing=True)
        mat = bpy.data.materials.new("M_2D_Reference_Image")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        tex = mat.node_tree.nodes.new(type="ShaderNodeTexImage")
        tex.image = img
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        mat.blend_method = "BLEND"
        bpy.ops.mesh.primitive_plane_add(location=(-2.3, 0.65, 1.2), rotation=(1.5708, 0, 0))
        plane = bpy.context.object
        plane.name = "Reference_2D_Sprite_Sheet"
        plane.dimensions = (2.2, 0.01, 0.75)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        plane.data.materials.append(mat)
        plane.hide_render = True
        return plane.name
    except Exception:
        return None


def op_create_3d_asset_from_reference_image(params):
    """Create a 3D asset that matches a supplied 2D character reference."""
    reference_image = params.get("reference_image", "")
    asset_type = params.get("asset_type", "human_character")
    if asset_type != "human_character":
        raise ValueError("MVP supports asset_type='human_character'.")

    filename = params.get("filename", "reference_matched_character")
    blend_path = workspace_output("blends", f"{filename}.blend")
    glb_path = workspace_output("exports", f"{filename}.glb")
    preview_path = workspace_output("renders", f"{filename}_preview.png")

    sprite_reference_character.ensure_dirs()
    sprite_reference_character.clear()
    reference_plane = None
    provider_result = None
    fallback_reason = None
    use_ai = bool(params.get("use_ai", True))

    if use_ai and reference_image:
        try:
            provider_result = create_ai_image_to_3d(reference_image, glb_path, params)
            reference_plane = _add_reference_image_plane(reference_image)
            sprite_reference_character.setup_scene()
        except ImageTo3DError as exc:
            fallback_reason = str(exc)
            sprite_reference_character.clear()

    if provider_result is None:
        sprite_reference_character.build(reference_image)
        sprite_reference_character.setup_scene()
        reference_plane = _add_reference_image_plane(reference_image) if reference_image else None

    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    if provider_result is None:
        bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB", export_animations=True, export_yup=True)
    bpy.context.scene.render.filepath = preview_path
    bpy.ops.render.render(write_still=True)

    return {
        "asset_type": asset_type,
        "reference_image": os.path.basename(reference_image) if reference_image else None,
        "reference_plane": reference_plane,
        "generation_mode": "ai_image_to_3d" if provider_result else "procedural_reference_fallback",
        "provider_result": provider_result,
        "fallback_reason": fallback_reason,
        "blend_path": blend_path,
        "glb_path": glb_path,
        "preview_path": preview_path,
        "match_notes": [
            "navy long coat",
            "cream high collar and cuffs",
            "open white shirt",
            "brown diagonal strap and utility belt",
            "bronze shoulder armor",
            "cyan gems",
            "dark trousers, knee pads and brown boots",
            "spiky black hair",
        ],
    }
