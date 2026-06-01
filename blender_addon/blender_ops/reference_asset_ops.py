"""Reference-image driven 3D asset creation."""
from __future__ import annotations

import os
from pathlib import Path

import bpy

from ..reference_generators import sprite_reference_character
from .export_ops import workspace_output
from .image_to_3d_ai import ImageTo3DError, create_ai_image_to_3d, frame_imported_asset_camera


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


def _add_reference_image_plane(path: str, location=(-2.3, 0.65, 1.2), rotation=(1.5708, 0, 0), name="Reference_2D_View") -> str | None:
    image_path = Path(path).expanduser()
    if not image_path.exists():
        return None
    try:
        img = bpy.data.images.load(str(image_path), check_existing=True)
        mat = bpy.data.materials.new(f"M_2D_{name}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        tex = mat.node_tree.nodes.new(type="ShaderNodeTexImage")
        tex.image = img
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        mat.blend_method = "BLEND"
        bpy.ops.mesh.primitive_plane_add(location=location, rotation=rotation)
        plane = bpy.context.object
        plane.name = name
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
    glb_path = params.get("glb_path") or workspace_output("exports", f"{filename}.glb")
    preview_path = workspace_output("renders", f"{filename}_preview.png")

    sprite_reference_character.ensure_dirs()
    sprite_reference_character.clear()

    reference_plane = None
    extra_planes = []
    provider_result = params.get("provider_result")
    fallback_reason = params.get("fallback_reason")
    use_ai = bool(params.get("use_ai", True))
    extra_views = params.get("extra_views", [])

    # If the MCP server pre-generated the asset, we import it directly
    if use_ai and provider_result and os.path.exists(glb_path):
        try:
            from .image_to_3d_ai import _import_glb, _fit_imported_scene
            imported_names = _import_glb(glb_path)
            fit_info = _fit_imported_scene(params)

            # Setup scene lighting, camera, and turntable floor
            sprite_reference_character.setup_scene()

            # Place reference planes for all multi-view slices
            reference_plane = _add_reference_image_plane(reference_image, location=(-2.3, 0.65, 1.2), name="Ref_Front")

            # Place extra views (Side/Back) at offset columns
            for i, extra_path in enumerate(extra_views):
                view_name = "Ref_Side" if i == 0 else "Ref_Back"
                y_offset = 2.45 if i == 0 else -1.15
                plane_name = _add_reference_image_plane(extra_path, location=(-2.3, y_offset, 1.2), name=view_name)
                if plane_name:
                    extra_planes.append(plane_name)

            # Automatically rig and animate the imported AI mesh models!
            try:
                from .character_ops import _create_armature, op_bind_auto_weights, op_add_character_animation
                # Create the armature bone structure
                arm = _create_armature()

                # Make sure we select the imported meshes and the armature
                bpy.ops.object.mode_set(mode='OBJECT') if bpy.ops.object.mode_set.poll() else None
                bpy.ops.object.select_all(action='DESELECT')
                for name in imported_names:
                    obj = bpy.data.objects.get(name)
                    if obj and obj.type == 'MESH':
                        obj.select_set(True)

                # Bind with automatic bone weights
                bind_res = op_bind_auto_weights({})
                print("Auto-rigged AI meshes successfully:", bind_res)

                # Add default walking/waving idle motion
                anim_res = op_add_character_animation({"animation": "idle_wave", "frames": 120})
                print("Added animation successfully:", anim_res)
            except Exception as e:
                print("Could not auto-rig imported AI model meshes:", e)

            provider_result["camera_frame"] = frame_imported_asset_camera(preview_path)
            provider_result["imported_objects"] = imported_names
            provider_result["fit_info"] = fit_info
        except Exception as exc:
            fallback_reason = f"Import error: {exc}"
            provider_result = None
            sprite_reference_character.clear()

    # Blender-side generation if MCP side didn't pre-generate
    elif use_ai and reference_image and not provider_result:
        try:
            provider_result = create_ai_image_to_3d(reference_image, glb_path, params)
            reference_plane = _add_reference_image_plane(reference_image)
            sprite_reference_character.setup_scene()
            provider_result["camera_frame"] = frame_imported_asset_camera(preview_path)
        except ImageTo3DError as exc:
            fallback_reason = str(exc)
            sprite_reference_character.clear()

    if provider_result is None:
        log_msg = f"Falling back to high-quality procedural adventurer rig due to: {fallback_reason}"
        print(log_msg)
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
        "extra_planes": extra_planes,
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
