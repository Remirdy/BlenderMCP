"""Operation registry: maps structured op names to in-Blender handlers.

The bridge ONLY dispatches names found in this registry. There is no generic
"run arbitrary python" entry, which is the core safety guarantee.
"""
from __future__ import annotations

from . import (
    architecture_ops as A,
    asset_ops as AS,
    character_ops as C,
    export_ops as E,
    game_ops as G,
    import_ops as IM,
    interior_ops as I,
    material_ops as M,
    modular_ops as MK,
    packaging_ops as PK,
    product_ops as PR,
    quality_ops as Q,
    render_ops as R,
    reference_asset_ops as RA,
    layered_scene_ops as L,
    scene_ops as S,
    scoring_ops as SC,
    terrain_ops as T,
    understanding_ops as U,
)
from . import prompt_router


def op_create_scene_from_prompt(params):
    """Full pipeline: classify -> build -> auto-fix -> optionally render/export."""
    prompt = params.get("prompt", "")
    plan = prompt_router.classify(prompt)
    kind = plan["kind"]

    if kind == "interior_design":
        result = I.op_create_interior_design_scene(plan)
    elif kind == "architectural_exterior":
        result = A.op_create_architectural_exterior(plan)
    elif kind == "product_render":
        result = S.op_create_product_render_scene(plan)
    elif kind == "cinematic":
        result = S.op_create_cinematic_scene(plan)
    else:
        result = G.op_create_game_environment(plan)

    R.op_apply_render_preset({"preset": params.get("render_preset", "portfolio_render")})

    fix_report = None
    if params.get("auto_fix", True):
        fix_report = Q.op_auto_fix_scene({})

    render_path = None
    if params.get("render_after", False):
        render_path = R.op_render_preview({"filename": "prompt_preview.png"}).get("render_path")

    export_info = None
    if plan.get("export"):
        exp = plan["export"]
        if exp["format"] == "glb":
            export_info = E.op_export_glb({"filename": "scene.glb", "target": exp["target"]})
        else:
            export_info = E.op_export_fbx({"filename": "scene.fbx", "target": exp["target"]})

    summary = S.op_get_scene_summary({})
    return {
        "plan": plan,
        "created": result.get("created", []),
        "scene_summary": summary,
        "auto_fix": fix_report,
        "render_path": render_path,
        "export": export_info,
        "suggested_next": _suggest(kind),
    }


def _suggest(kind):
    base = ["scene_quality_check", "render_preview"]
    if kind == "game_environment":
        return base + ["optimize_for_game_engine", "prepare_for_unity_export", "export_glb"]
    if kind == "architectural_exterior":
        return base + ["setup_archviz_lighting", "render_final"]
    if kind == "interior_design":
        return base + ["apply_interior_material_palette", "render_final"]
    if kind == "product_render":
        return base + ["export_turntable_animation", "render_final"]
    return base + ["export_glb"]


REGISTRY = {
    # connection / status
    "ping": S.op_ping,
    "get_blender_status": S.op_get_blender_status,
    "get_scene_summary": S.op_get_scene_summary,
    "inspect_scene": S.op_inspect_scene,
    "clear_scene": S.op_clear_scene,
    "create_collection": S.op_create_collection,
    "capture_viewport_screenshot": U.op_capture_viewport_screenshot,
    "capture_scene_contact_sheet": U.op_capture_scene_contact_sheet,
    "analyze_scene_visuals": U.op_analyze_scene_visuals,
    "get_scene_graph": U.op_get_scene_graph,
    # scene creation
    "create_scene_from_prompt": op_create_scene_from_prompt,
    "create_game_environment": G.op_create_game_environment,
    "create_game_environment_from_reference_image": G.op_create_game_environment_from_reference_image,
    "create_architectural_exterior": A.op_create_architectural_exterior,
    "create_interior_design_scene": I.op_create_interior_design_scene,
    "create_product_render_scene": S.op_create_product_render_scene,
    "create_cinematic_scene": S.op_create_cinematic_scene,
    "create_scene_from_video_reference": S.op_create_scene_from_video_reference,
    # game tools
    "create_game_ready_prop": G.op_create_game_ready_prop,
    "create_game_environment_from_image": G.op_create_game_environment_from_reference_image,
    "create_modular_environment_piece": G.op_create_modular_environment_piece,
    "create_low_poly_environment": G.op_create_low_poly_environment,
    "create_stylized_building": G.op_create_stylized_building,
    "create_mobile_game_scene": G.op_create_mobile_game_scene,
    "optimize_for_game_engine": G.op_optimize_for_game_engine,
    "prepare_for_unity_export": G.op_prepare_for_unity_export,
    "prepare_for_unreal_export": G.op_prepare_for_unreal_export,
    "apply_biome_painter": G.op_apply_biome_painter,
    "create_bezier_path": G.op_create_bezier_path,
    "spawn_weather_particles": G.op_spawn_weather_particles,
    "create_building_facade": G.op_create_building_facade,
    "create_procedural_foliage": G.op_create_procedural_foliage,
    "create_istanbul_bosphorus": G.op_create_istanbul_bosphorus,
    "create_physics_from_prompt": G.op_create_physics_from_prompt,
    "create_procedural_city_blockout": G.op_create_procedural_city_blockout,
    # character tools
    "create_rigged_character": C.op_create_rigged_character,
    "add_character_animation": C.op_add_character_animation,
    "validate_character_rig": C.op_validate_character_rig,
    "export_character_glb": C.op_export_character_glb,
    "create_3d_asset_from_reference_image": RA.op_create_3d_asset_from_reference_image,
    "create_layered_depth_scene": L.op_create_layered_depth_scene,
    "bind_auto_weights": C.op_bind_auto_weights,
    # terrain (Satellite → 3D)
    "create_terrain_from_heightmap": T.op_create_terrain_from_heightmap,
    "add_text_motion_preset": C.op_add_text_motion_preset,
    "create_facial_blendshapes": C.op_create_facial_blendshapes,
    "fit_clothing_mesh": C.op_fit_clothing_mesh,
    "convert_hair_to_curves": C.op_convert_hair_to_curves,
    "reduce_armature_bones": C.op_reduce_armature_bones,
    "adapt_fbx_rig": C.op_adapt_fbx_rig,
    # architecture
    "create_floor_plan_blockout": A.op_create_floor_plan_blockout,
    "create_modern_house_exterior": A.op_create_modern_house_exterior,
    "add_architectural_details": A.op_add_architectural_details,
    "add_windows_doors_stairs": A.op_add_windows_doors_stairs,
    # interior
    "create_apartment_interior": I.op_create_apartment_interior,
    "create_living_room_scene": I.op_create_living_room_scene,
    "create_bedroom_scene": I.op_create_bedroom_scene,
    "create_kitchen_scene": I.op_create_kitchen_scene,
    "create_office_interior": I.op_create_office_interior,
    "add_furniture_set": I.op_add_furniture_set,
    "apply_interior_material_palette": I.op_apply_interior_material_palette,
    # render
    "setup_camera": R.op_setup_camera,
    "setup_isometric_camera": R.op_setup_isometric_camera,
    "setup_archviz_camera": R.op_setup_archviz_camera,
    "setup_product_camera": R.op_setup_product_camera,
    "setup_lighting": R.op_setup_lighting,
    "setup_three_point_lighting": R.op_setup_three_point_lighting,
    "setup_archviz_lighting": R.op_setup_archviz_lighting,
    "setup_cinematic_lighting": R.op_setup_cinematic_lighting,
    "apply_render_preset": R.op_apply_render_preset,
    "render_preview": R.op_render_preview,
    "render_final": R.op_render_final,
    # materials
    "create_material": M.op_create_material,
    "apply_material": M.op_apply_material,
    "apply_style_preset": M.op_apply_style_preset,
    "create_stylized_materials": M.op_create_stylized_materials,
    "create_archviz_materials": M.op_create_archviz_materials,
    "create_product_materials": M.op_create_product_materials,
    "create_emissive_materials": M.op_create_emissive_materials,
    "apply_color_palette_from_image": M.op_apply_color_palette_from_image,
    "apply_cel_shading_outline": M.op_apply_cel_shading_outline,
    "create_stylized_water": M.op_create_stylized_water,
    "apply_seamless_tiling": M.op_apply_seamless_tiling,
    "apply_neon_edge_tracer": M.op_apply_neon_edge_tracer,
    "compile_texture_atlas": M.op_compile_texture_atlas,
    "bake_pbr_textures": M.op_bake_pbr_textures,
    "generate_ai_textures": M.op_generate_ai_textures,
    # quality / organization
    "organize_scene": Q.op_organize_scene,
    "rename_objects_professionally": Q.op_rename_objects_professionally,
    "set_origins_and_pivots": Q.op_set_origins_and_pivots,
    "fix_transforms": Q.op_fix_transforms,
    "apply_scale_rotation": Q.op_apply_scale_rotation,
    "scene_quality_check": Q.op_scene_quality_check,
    "auto_fix_scene": Q.op_auto_fix_scene,
    "normalize_imported_asset": Q.op_normalize_imported_asset,
    "repair_materials": Q.op_repair_materials,
    "decimate_asset": Q.op_decimate_asset,
    "generate_lods": Q.op_generate_lods,
    "create_collision_proxies": Q.op_create_collision_proxies,
    "check_engine_readiness": Q.op_check_engine_readiness,
    "check_license_metadata": Q.op_check_license_metadata,
    "apply_quad_remesh": Q.op_apply_quad_remesh,
    "apply_voxel_blockout": Q.op_apply_voxel_blockout,
    "prepare_for_3d_printing": Q.op_prepare_for_3d_printing,
    "generate_lods_advanced": Q.op_generate_lods_advanced,
    "prepare_lightmap_uvs": Q.op_prepare_lightmap_uvs,
    # export
    "export_blend": E.op_export_blend,
    "export_glb": E.op_export_glb,
    "export_fbx": E.op_export_fbx,
    "export_obj": E.op_export_obj,
    "import_asset_file": IM.op_import_asset_file,
    "set_hdri_environment": IM.op_set_hdri_environment,
    "export_render_image": R.op_export_render_image,
    "export_turntable_animation": R.op_export_turntable_animation,
    "setup_camera_auto_focus": R.op_setup_camera_auto_focus,
    "generate_html_catalog": E.op_generate_html_catalog,
    "sync_engine_live_link": S.op_sync_engine_live_link,
    # weather
    "set_weather_environment": R.op_set_weather_environment,
    # ---- asset pack generator ----
    "create_asset_pack": AS.op_create_asset_pack,
    "create_game_prop_pack": AS.op_create_game_prop_pack,
    "create_stylized_prop_set": AS.op_create_stylized_prop_set,
    "create_low_poly_asset_pack": AS.op_create_low_poly_asset_pack,
    "create_mobile_game_asset_pack": AS.op_create_mobile_game_asset_pack,
    "generate_asset_variations": AS.op_generate_asset_variations,
    "create_asset_variation": AS.op_generate_asset_variations,
    "create_asset_pack_thumbnails": AS.op_create_asset_pack_thumbnails,
    "create_preview_grid": AS.op_create_preview_grid,
    "export_asset_pack_for_unity": AS.op_export_asset_pack_for_unity,
    "export_asset_pack_for_unreal": AS.op_export_asset_pack_for_unreal,
    "create_interior_asset_pack": AS.op_create_interior_asset_pack,
    # ---- modular kit builder ----
    "create_modular_kit": MK.op_create_modular_kit,
    "create_modular_wall_piece": MK.op_create_modular_wall_piece,
    "create_modular_floor_piece": MK.op_create_modular_floor_piece,
    "create_modular_corner_piece": MK.op_create_modular_corner_piece,
    "create_modular_door_piece": MK.op_create_modular_door_piece,
    "create_modular_window_piece": MK.op_create_modular_window_piece,
    "create_modular_roof_piece": MK.op_create_modular_roof_piece,
    "create_modular_stair_piece": MK.op_create_modular_stair_piece,
    "create_modular_prop_variants": MK.op_create_modular_prop_variants,
    "validate_modular_grid": MK.op_validate_modular_grid,
    "create_modular_test_layout": MK.op_create_test_layout,
    "export_modular_kit": MK.op_export_modular_kit,
    # ---- product render creator ----
    "create_product_asset": PR.op_create_product_asset,
    "create_product_variations": PR.op_create_product_variations,
    "create_packaging_mockup": PR.op_create_packaging_mockup,
    "setup_product_render_stage": PR.op_setup_product_render_stage,
    "render_product_thumbnail": PR.op_render_product_thumbnail,
    "render_product_turntable": PR.op_render_product_turntable,
    "export_product_model": PR.op_export_product_model,
    # ---- quality scoring ----
    "score_asset_quality": SC.op_score_asset_quality,
    "score_asset_pack_quality": SC.op_score_asset_pack_quality,
    "check_game_readiness": SC.op_check_game_readiness,
    "check_archviz_readiness": SC.op_check_archviz_readiness,
    "check_marketplace_readiness": SC.op_check_marketplace_readiness,
    "auto_fix_asset_pack": SC.op_auto_fix_asset_pack,
    # ---- marketplace packaging ----
    "package_asset_for_marketplace": PK.op_package_asset_for_marketplace,
    "generate_asset_pack_readme": PK.op_generate_pack_readme,
    "generate_pack_readme": PK.op_generate_pack_readme,
    "generate_asset_manifest": PK.op_generate_asset_manifest,
    "generate_usage_guide": PK.op_generate_usage_guide,
    "generate_license_template": PK.op_generate_license_template,
    "generate_preview_renders": PK.op_generate_preview_renders,
    "generate_thumbnail_sheet": PK.op_generate_thumbnail_sheet,
    "create_asset_catalog": PK.op_create_asset_catalog,
}


def dispatch(op: str, params: dict) -> dict:
    handler = REGISTRY.get(op)
    if handler is None:
        raise ValueError(f"Unknown operation '{op}'. Not in the Remirdy registry.")
    return handler(params or {})
