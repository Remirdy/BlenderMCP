# Remirdy Blender Studio MCP - Professional MVP Plan

This plan turns Remirdy from a local procedural Blender helper into a production-grade
3D creation MCP: model generation, asset search/import, viewport understanding,
remote Blender execution, character rigging, validation, export and anonymous tool
telemetry.

## Product Goal

Remirdy should let an AI client reliably do this end to end:

1. Understand the current Blender scene visually and structurally.
2. Generate or import high-quality assets from multiple providers.
3. Create characters, rigs, starter animations and game-ready exports.
4. Validate quality, licensing, scale, topology and engine readiness.
5. Run locally or against a remote Blender host.
6. Log anonymous tool execution telemetry for product improvement, without scene
   content, prompts, file paths or personal data.

## MVP Pillars

### 1. Scene Understanding

New tools:

- `capture_viewport_screenshot(view="camera|front|side|top|perspective", width=1280, height=720)`
- `capture_scene_contact_sheet()`
- `analyze_scene_visuals()`
- `get_scene_graph()`
- `compare_scene_before_after(before_id, after_id)`

Implementation:

- Use Blender viewport/render APIs to save screenshots under
  `outputs/screenshots/`.
- Return screenshot paths and scene graph metadata.
- Keep image capture local to the configured workspace.

MVP acceptance:

- Can capture camera and orthographic screenshots.
- Can return a concise object tree with collections, object types, material names,
  triangle counts and bounding boxes.

### 2. Character/Rig Pipeline

Current MVP already added:

- `create_rigged_character`
- `add_character_animation`
- `validate_character_rig`
- `export_character_glb`

Next MVP upgrades:

- `create_humanoid_metarig()`
- `skin_character_to_rig(mode="rigid|automatic_weights")`
- `add_ik_controls()`
- `retarget_animation(source="mixamo|bvh|glb")`
- `export_unity_humanoid_package()`

MVP acceptance:

- Creates a named humanoid rig with expected bones.
- Exports GLB with animation.
- Validates required bones and animation action.

### 3. AI 3D Model Generation Providers

Provider abstraction:

- `server/providers/model_generation/base.py`
- `server/providers/model_generation/hunyuan3d.py`
- `server/providers/model_generation/rodin.py`

New tools:

- `generate_model(prompt, provider="hunyuan3d|rodin", style, quality, seed)`
- `poll_generation_job(job_id)`
- `download_generated_model(job_id, format="glb")`
- `import_generated_model(job_id)`

Environment variables:

- `HUNYUAN3D_API_KEY`
- `RODIN_API_KEY`

MVP acceptance:

- Providers are optional. If an API key is missing, the tool returns a clear setup
  error instead of failing silently.
- Generated assets are downloaded only into `outputs/imports/`.
- Imports are scale-normalized and placed into a named collection.

### 4. Asset Search And Download

#### Sketchfab

New tools:

- `search_sketchfab_models(query, downloadable=true, licenses, max_results)`
- `download_sketchfab_model(uid, format="glb")`
- `import_sketchfab_model(uid)`

Environment:

- `SKETCHFAB_API_TOKEN`

Policy:

- Only import downloadable models.
- Preserve author, license, source URL and model UID in custom properties.
- Write attribution metadata to `outputs/imports/<asset>/attribution.json`.

#### Poly Haven

New tools:

- `search_polyhaven_assets(query, type="hdris|textures|models|all")`
- `download_polyhaven_asset(asset_id, resolution, format)`
- `import_polyhaven_model(asset_id)`
- `apply_polyhaven_texture(asset_id, object_name)`
- `set_polyhaven_hdri(asset_id)`

Policy:

- Store downloaded files under `outputs/imports/polyhaven/`.
- Cache asset metadata and avoid duplicate downloads.

MVP acceptance:

- Search returns clean metadata.
- Download stores files in workspace.
- Import creates objects/materials and metadata tags.

### 5. Remote Blender Host

Goal:

Run MCP server on one machine and Blender bridge on another machine.

New config:

- `REMIRDY_BRIDGE_HOST`
- `REMIRDY_BRIDGE_PORT`
- `REMIRDY_BRIDGE_TOKEN`
- `REMIRDY_REMOTE_TLS=true|false`

New tools:

- `connect_remote_blender(host, port, token)`
- `get_remote_host_status()`
- `sync_workspace_manifest()`

Security:

- Require token auth for non-localhost connections.
- Optional TLS/reverse proxy support.
- Never expose arbitrary Python execution.
- Keep operation registry allowlisted.

MVP acceptance:

- Localhost remains zero-config.
- Remote bridge rejects missing/invalid token.
- All remote ops use the same structured registry.

### 6. Anonymous Telemetry

Goal:

Understand tool reliability and latency without collecting user content.

What is allowed:

- Tool name.
- Duration.
- Success/failure.
- Error class, not full traceback by default.
- Blender version.
- Remirdy version.
- Anonymous install ID generated locally.

What is forbidden:

- Prompts.
- File paths.
- Screenshots.
- Scene/object names.
- Usernames.
- API keys.
- Download URLs containing tokens.

New config:

- `REMIRDY_TELEMETRY=off|local|anonymous`
- default: `off`

New tools:

- `get_telemetry_status()`
- `set_telemetry_mode(mode)`
- `export_local_telemetry_report()`

MVP acceptance:

- Telemetry is opt-in.
- Local telemetry works without network.
- Anonymous mode strips all user content before sending.

### 7. Import, Cleanup And Quality Gates

New tools:

- `normalize_imported_asset(scale_mode="unit|human|meter")`
- `repair_materials()`
- `generate_lods(levels=3)`
- `decimate_asset(target_tris)`
- `check_license_metadata()`
- `check_engine_readiness(target="unity|unreal|web")`
- `create_collision_proxies(mode="box|convex|mesh")`

MVP acceptance:

- Imported/generated assets can be cleaned, renamed, origin-fixed and exported.
- Quality report includes actionable issues and a score.

### 8. Job System

Long-running generation/download/render tasks need job IDs.

New internal modules:

- `server/jobs.py`
- `server/cache.py`

New tools:

- `list_jobs()`
- `get_job(job_id)`
- `cancel_job(job_id)`

MVP acceptance:

- Model generation and downloads return job IDs.
- Polling returns progress/state/result paths.

## Suggested Tool Surface For MVP v1

Connection:

- `connect_blender`
- `connect_remote_blender`
- `get_blender_status`

Scene understanding:

- `capture_viewport_screenshot`
- `get_scene_graph`
- `inspect_scene`

Characters:

- `create_rigged_character`
- `add_character_animation`
- `validate_character_rig`
- `export_character_glb`

Generation:

- `generate_model`
- `poll_generation_job`
- `import_generated_model`

Asset libraries:

- `search_sketchfab_models`
- `download_sketchfab_model`
- `import_sketchfab_model`
- `search_polyhaven_assets`
- `download_polyhaven_asset`
- `import_polyhaven_model`
- `set_polyhaven_hdri`

Quality/export:

- `scene_quality_check`
- `auto_fix_scene`
- `check_engine_readiness`
- `export_glb`
- `export_fbx`
- `export_blend`

Telemetry:

- `get_telemetry_status`
- `set_telemetry_mode`
- `export_local_telemetry_report`

## Implementation Phases

### Phase 1 - Core Professionalization

- Add viewport screenshots.
- Add scene graph tool.
- Finish character MVP docs and examples.
- Add provider/job/cache skeletons.
- Add opt-in local telemetry.

### Phase 2 - Asset Sources

- Poly Haven search/download/import.
- Sketchfab search/download/import with attribution metadata.
- Asset cache and license metadata validation.

### Phase 3 - AI Model Generation

- Hyper3D Rodin provider.
- Hunyuan3D provider.
- Async job polling.
- Import generated GLB/OBJ.

### Phase 4 - Remote Host

- Token-protected remote bridge.
- Remote host status.
- Workspace sync manifest.

### Phase 5 - Production Character Pipeline

- IK controls.
- Automatic weights or rigid-part binding modes.
- Retarget/import animation.
- Unity humanoid export profile.

## Non-Goals For MVP

- Arbitrary Python execution from MCP.
- Scraping paid marketplaces.
- Importing non-downloadable Sketchfab models.
- Collecting prompts or screenshots in telemetry.
- Full DCC-grade auto-retopology. MVP can decimate and validate; advanced retopo is later.

## Example MVP Workflows

### Character

1. `create_rigged_character(name="Cyber Scout", style="sci_fi_scout")`
2. `validate_character_rig()`
3. `capture_viewport_screenshot(view="camera")`
4. `export_character_glb(filename="cyber_scout.glb", target="unity")`

### Poly Haven HDRI

1. `search_polyhaven_assets(query="studio", type="hdris")`
2. `download_polyhaven_asset(asset_id="...", resolution="2k")`
3. `set_polyhaven_hdri(asset_id="...")`
4. `render_preview()`

### Rodin/Hunyuan3D

1. `generate_model(prompt="stylized sci-fi drone", provider="rodin")`
2. `poll_generation_job(job_id="...")`
3. `import_generated_model(job_id="...")`
4. `check_engine_readiness(target="unity")`
5. `export_glb(filename="drone.glb", target="unity")`

## Quality Bar

The MVP is ready when a user can:

- Open Blender.
- Start the bridge.
- Ask Codex to search/generate/import a 3D model.
- See a viewport screenshot.
- Clean and validate the asset.
- Export a game-ready GLB.
- Do the same for a basic rigged character.

