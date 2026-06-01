# Tool reference

Every tool returns a uniform envelope: `{ "ok": bool, "op": str, ... }`. On
failure: `{ "ok": false, "error": str, "hint": str }`.

## Connection & status
- **connect_blender(host="127.0.0.1", port=8765)** — establish the bridge connection.
- **connect_remote_blender(host, port, token)** — connect to a token-protected remote Blender bridge.
- **get_blender_status()** — Blender version, render engine, object count, bridge health.
- **get_scene_summary()** — object/mesh/poly counts, collections, camera, lights, materials.
- **inspect_scene()** — per-object transform, polycount, materials, collections.
- **clear_scene(keep_camera=false, keep_lights=false)** — wipe the scene.

## Scene understanding
- **capture_viewport_screenshot(view, width, height, filename)** — capture camera/front/side/top/perspective screenshots under `outputs/screenshots`.
- **capture_scene_contact_sheet(width, height)** — capture camera, front, side and top review images.
- **analyze_scene_visuals(view)** — capture a screenshot and return high-level scene facts.
- **get_scene_graph()** — return collections, objects, transforms, bounds, materials and armature bones.

## Scene creation
- **create_scene_from_prompt(prompt, render_preset="portfolio_render", auto_fix=true, render_after=false)** — full pipeline.
- **create_game_environment(style, theme, size, isometric_camera)**.
- **create_game_environment_from_reference_image(reference_image, style, theme, size, isometric_camera, add_reference_billboard, seed)** — samples a reference image, infers a broad game-environment theme and builds a procedural playable blockout with lighting and camera.
- **create_architectural_exterior(preset, floors, landscaping)**.
- **create_interior_design_scene(room, style, warm_lighting)**.
- **create_product_render_scene(product, background)**.
- **create_cinematic_scene(subject, mood)**.

## Game assets
- **create_game_ready_prop(name, kind, detail)** — kind: crate|barrel|rock|lamp|bench|fence|sign.
- **create_modular_environment_piece(piece, grid)** — piece: wall_panel|floor_tile|corner|doorway|pillar.
- **create_low_poly_environment(theme, extent)**.
- **create_stylized_building(stories, footprint, roof)**.
- **create_mobile_game_scene(theme, isometric_camera)**.
- **optimize_for_game_engine(target_tris, merge_materials)**.
- **prepare_for_unity_export(apply_transforms)** / **prepare_for_unreal_export(apply_transforms)**.

## Characters
- **create_rigged_character(name, style, animation, clear_scene)** — creates a stylized humanoid with separated mesh parts, a humanoid armature and starter animation. Styles: stylized_hero|cyber_adventurer|fantasy_knight|sci_fi_scout.
- **add_character_animation(animation, frames)** — adds idle, wave, walk_preview or idle_wave keyframes to the active Remirdy character rig.
- **validate_character_rig()** — checks expected humanoid bones, parented mesh parts and animation data.
- **export_character_glb(filename, target)** — exports the rigged character with armature and animation as GLB.

## Architecture
- **create_floor_plan_blockout(width, depth, rooms)**.
- **create_modern_house_exterior(floors, pool, garden)**.
- **add_architectural_details(level)** — low|medium|high.
- **add_windows_doors_stairs(windows, doors, stairs)**.

## Interior
- **create_apartment_interior(rooms, style)**.
- **create_living_room_scene(style, warm_lighting)**.
- **create_bedroom_scene(style)**.
- **create_kitchen_scene(style, island)**.
- **create_office_interior(desks, glass_partitions)**.
- **add_furniture_set(set_name)** — living_room|bedroom|kitchen|office.
- **apply_interior_material_palette(palette)** — warm_modern|minimalist_neutral|luxury_dark.

## Render
- **setup_camera / setup_isometric_camera / setup_archviz_camera / setup_product_camera**.
- **setup_lighting / setup_three_point_lighting / setup_archviz_lighting / setup_cinematic_lighting**.
- **apply_render_preset(preset)** — fast_preview|portfolio_render|archviz_render|product_render|cinematic_render.
- **render_preview(width, height, filename)** / **render_final(width, height, samples, filename)**.

## Materials
- **create_material(name, base_color, metallic, roughness, emission_strength)**.
- **apply_material(object_name, material_name)**.
- **apply_style_preset(preset)**.
- **create_stylized_materials / create_archviz_materials / create_product_materials**.
- **create_emissive_materials(color, strength)** — blue|cyan|magenta|orange.

## Organization & quality
- **create_collection(name)**.
- **organize_scene()** — sort into Architecture/Furniture/Props/Environment/Lighting/Cameras.
- **rename_objects_professionally(prefix)**.
- **set_origins_and_pivots(mode)** — bottom_center|geometry.
- **fix_transforms()** / **apply_scale_rotation()**.
- **scene_quality_check()** — returns issues with severities + quality_score (0–100).
- **auto_fix_scene(aggressive)** — fixes common issues, returns before/after score.
- **normalize_imported_asset(target_size, selected_only)** — scale and ground imported assets to a predictable max dimension.
- **repair_materials()** — assign missing materials and normalize material naming.
- **decimate_asset(ratio, min_faces, apply)** — reduce high-poly meshes with decimate modifiers.
- **generate_lods(ratios)** — duplicate LOD0/LOD1/LOD2-style meshes with decimation ratios.
- **create_collision_proxies(mode)** — create non-rendering box collision proxies.
- **check_engine_readiness(target, max_faces)** — score Unity/Unreal/Web export readiness.
- **check_license_metadata()** — check imported asset folders for attribution/license metadata.

## Export
- **export_blend(filename)**.
- **export_glb(filename, target, selected_only)** — target: generic|unity|unreal.
- **export_fbx(filename, target, selected_only)**.
- **export_obj(filename)**.
- **import_asset_file(path, collection)** — import GLB/glTF/FBX/OBJ/Blend files from inside the Remirdy workspace.
- **set_hdri_environment(path, strength)** — set a downloaded `.hdr`/`.exr` workspace file as world lighting.
- **export_render_image(filename, width, height)**.
- **export_turntable_animation(filename, frames)**.

## External assets and model generation
- **search_polyhaven_assets(query, type, max_results)** — search Poly Haven HDRIs, textures and models.
- **download_polyhaven_asset(asset_id, resolution, format)** — download Poly Haven metadata and a matching asset file.
- **search_sketchfab_models(query, downloadable, licenses, max_results)** — search Sketchfab models; authenticated requests use `SKETCHFAB_API_TOKEN`.
- **download_sketchfab_model(uid, format)** — download via the official Sketchfab Download API; requires `SKETCHFAB_API_TOKEN`.
- **generate_model(prompt, provider, quality, seed)** — create a Rodin/Hunyuan3D generation job scaffold; requires `RODIN_API_KEY`, `HUNYUAN3D_API_KEY` or `HUNYUAN3D_ENDPOINT`.
- **generate_3d_model_from_image(image_path, provider, prompt, quality, seed)** — create a Rodin/Hunyuan3D image-to-3D job scaffold from a reference image.
- **download_generated_model(job_id, model_url, filename)** — download a provider result URL into the workspace until provider-specific polling is fully wired.
- **poll_generation_job(job_id)** / **list_generation_jobs()**.

## Reference image to 3D
- **create_3d_asset_from_reference_image(reference_image, asset_type, filename)** — create a reference-matched stylized 3D human character with Blend, GLB and preview output.

## Real-world terrain (Satellite → 3D) — Phase A
- **geocode_location_tool(query)** — turn "Kapadokya", "Bosphorus", "Pamukkale" etc. into lat/lon + bbox.
- **fetch_elevation_heightmap(lat, lon, radius_km, zoom)** — download real AWS Terrarium elevation tiles and return a decoded heightmap PNG + elevation stats.
- **create_real_world_terrain_scene(location, radius_km, resolution, exaggeration, style)** — the magic button: geocode → fetch real elevation data → create displaced mesh in Blender with sun + camera.

## Multi-Agent Scene Orchestration (New)
- **orchestrate_scene_with_agents(prompt, focus_areas, max_iterations, use_vision_critique)** — the main "AI director". Runs specialist agents (lighting, critique via vision, geometry...) in iterative loops with self-reflection.
- **run_lighting_specialist_pass(mood, time_of_day)** — direct access to the lighting agent.
- **run_critique_pass()** — run only the powerful vision + quality critique agent (excellent for diagnostics or after terrain creation).

## Real-time Weather Lighting
- **set_real_time_weather(location, time_of_day, intensity)** — OpenWeatherMap'ten gerçek hava durumu çeker ve Blender'ın güneş pozisyonu + world aydınlatmasını otomatik ayarlar. Terrain sahneleriyle özellikle güçlüdür.

## Other Çılgın Özellik Scaffold'ları (Kısmi Implementasyon)
- **create_scene_from_video_reference** — Video/frame → 3D reconstruction scaffold
- **create_physics_from_prompt** — "kumaş dalgalanıyor", "su dökülüyor" gibi prompt'lardan basit fizik
- **prepare_for_3d_printing** — 3D baskı için manifold + thickness hazırlığı
- **auto_import_polyhaven_asset** / **search_and_place_asset** — Otomatik asset pipeline

## Telemetry
- **get_telemetry_status()** — show telemetry mode and privacy guarantees.
- **set_telemetry_mode(mode)** — `off|local|anonymous`; default is off.
- **export_local_telemetry_report(limit)** — read local scrubbed JSONL events.
