# Satellite → 3D + Multi-Agent Scene Orchestration — Implementation Plan

**Goal**: define two higher-level workflows that build on the existing
architecture without changing the bridge safety model.

- **Satellite → 3D Terrain**: Turn any real-world location ("Kapadokya", "Bosphorus Strait", "Tokyo Shibuya crossing") into a production-ready Blender terrain with optional OSM buildings, roads, and water.
- **Multi-Agent Scene Production**: A built-in specialist agent coordinator (inspired by the existing `providers/registry.py` parallel orchestration) that runs Geometry → Materials → Lighting → Composition → Critique (vision) loops.

Both features leverage the current strengths:
- Strict registry dispatch (no arbitrary Python)
- Existing vision tools (`analyze_scene_visuals`, screenshots)
- Provider-style orchestration patterns
- `asset_source_tools.py` HTTP + download patterns (Pillow already available)
- Procedural terrain precedents (Istanbul Bosphorus displaced grid, reference-image rolling hills)

---

## 1. Satellite → 3D Terrain Pipeline

### 1.1 Product Vision
User says:
> "Kapadokya'nın 2 km²'lik alanını gerçek topoğrafyayla, fairy chimney'ler ve birkaç cave hotel ile yap"

Remirdy:
1. Geocodes the name (Nominatim)
2. Computes a sensible bounding box
3. Fetches elevation tiles (AWS Terrarium by default — zero config)
4. (Optional) Fetches OpenStreetMap buildings, roads, waterways via Overpass
5. Creates a real displaced mesh terrain in Blender
6. Extrudes simple building volumes + road curves where data exists
7. Applies plausible biome materials + an HDRI or sky that matches latitude/time
8. Sets up a hero camera (dramatic or isometric)

Result: A geolocated, measurable, production-usable terrain blockout in < 60 seconds.

### 1.2 Data Sources

| Source              | Purpose                  | Key / Cost     | Priority | Notes |
|---------------------|--------------------------|----------------|----------|-------|
| Nominatim           | Geocoding "Kapadokya" → lat/lon + bbox | Free (polite) | High     | https://nominatim.openstreetmap.org |
| AWS Terrain Tiles   | Elevation (Terrarium PNG) | None           | High     | `s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png` |
| OpenTopography      | Higher-quality Copernicus GLO-30 | Free API key   | Medium   | Best global 30 m DEM |
| Overpass API        | Buildings, roads, water, landuse | None         | High     | `overpass-api.de` |
| Mapbox (optional)   | Fallback / higher zoom tiles | Token        | Low      | Only if user supplies key |

**Primary MVP path**: Nominatim + AWS Terrarium + Overpass (100% free, no secrets).

### 1.3 New MCP Tools (server/tools/asset_source_tools.py)

- `geocode_location(query: str) → {lat, lon, bbox, display_name, confidence}`
- `fetch_elevation_for_bbox(bbox, zoom=12, source="aws_terrarium"|"opentopo") → {heightmap_path, metadata, stats}`
- `fetch_osm_features(bbox, categories=["buildings","roads","water","landuse"]) → {geojson-like, counts}`
- `create_real_world_terrain_scene(location: str, radius_km: float = 2.0, resolution: int = 256, exaggeration: float = 1.5, include_buildings: bool = True, include_roads: bool = True, style: str = "realistic|stylized") → full pipeline result`

High-level tool calls the sequence + finally invokes Blender ops.

### 1.4 New / Extended Blender Ops

**New file recommended**: `blender_addon/blender_ops/terrain_ops.py`

Core operations:
- `op_create_terrain_from_heightmap(params)` — grid or plane + displace modifier from image or raw array. Supports vertical exaggeration, origin centering, UVs for satellite texturing.
- `op_extrude_osm_buildings(params)` — takes simplified building footprints (polygons + height tags), extrudes boxes or simple LODs.
- `op_create_osm_road_network(params)` — curve or thin extruded road meshes from OSM ways.
- `op_apply_biome_from_osm_landuse(params)` — assigns materials based on landuse/natural tags (forest → foliage, residential → urban concrete mix, etc.).
- `op_georeference_terrain(params)` — stores real lat/lon/bbox + scale metadata on the terrain object (useful for later export or compositing).

Extend `game_ops.py` temporarily if preferred, but separate file is cleaner long-term.

### 1.5 Implementation Phases

**Phase A (Core, 3-4 days)**
- Geocode + AWS Terrarium tile fetcher + stitcher + height decoder (pure Pillow + math)
- `create_real_world_terrain_scene` tool + basic displaced mesh in Blender
- Simple flat material + sun light matching rough latitude

**Phase B (Data Rich, 4-5 days)**
- Overpass integration (buildings + roads)
- Building extrusion + road curves
- Basic landuse material routing
- Camera + simple HDRI setup

**Phase C (Polish)**
- OpenTopography fallback (higher quality)
- LOD generation for large terrains
- Export-ready (Unity terrain? GLB with real-world scale metadata)
- Caching of downloaded tiles under `outputs/imports/terrain/`

### 1.6 Success Criteria
- User can say "Kapadokya peri bacaları" and get a recognizable 3D terrain within one minute.
- Terrain has real vertical scale (user can measure heights).
- Optional OSM overlays do not explode polycount (smart simplification).
- Works offline after first download (cache friendly).

---

## 2. Multi-Agent Scene Orchestration

### 2.1 Inspiration & Fit
The existing `server/providers/registry.py` already does sophisticated parallel + fallback + winner-takes-all for image-to-3D. We copy that exact mindset for **scene construction specialists**.

Current single-shot flow:
`create_scene_from_prompt` → `prompt_router.classify` → one big `op_*` → optional quality pass.

New world:
A coordinator that can invoke **specialist passes** in sequence or parallel, with optional **vision critique loops**.

### 2.2 Agent Roles (Specialists)

| Agent            | Responsibility                              | Existing Tools It Leverages                  | Output Artifacts |
|------------------|---------------------------------------------|----------------------------------------------|------------------|
| **Geometry**     | Major forms, blockout, terrain, modular kit | `create_*_environment`, modular ops, terrain ops | Collections, major meshes, proxies |
| **Materials**    | PBR assignment, procedural textures, palette| material_tools, `apply_style_preset`, AI texture | Material slots filled, baked maps |
| **Lighting**     | HDRI, 3-point, cinematic, time-of-day, volumetrics | render_ops lighting functions, `set_hdri_environment` | World + light data |
| **Composition**  | Camera, focal length, framing, DOF          | camera setup ops                             | Camera object + animation |
| **Critique**     | Vision-based quality analysis               | `analyze_scene_visuals`, `capture_*`, `scene_quality_check` | Structured issues + score + suggestions |

### 2.3 Coordinator Architecture (server/agents/scene_coordinator.py)

Pattern copy from providers:

```python
class SceneCoordinator:
    def orchestrate(self, prompt, focus_areas, max_iterations=3, use_vision=True):
        # 1. Initial plan (enhanced prompt_router or lightweight LLM call if available)
        # 2. For each iteration:
        #    - Run Geometry pass (if in focus)
        #    - Run Materials pass
        #    - Run Lighting pass
        #    - Run Composition pass
        #    - if use_vision: capture + CritiqueAgent.analyze() → structured feedback
        #    - if feedback has high-severity issues and iterations remain → refine specific agents
        # 3. Return rich report: plan, passes, vision_critiques, final score
```

Expose both:
- **High-level tool**: `orchestrate_scene_with_agents(...)`
- **Granular tools** so the calling LLM (or human) can run custom workflows:
  - `run_geometry_specialist_pass(plan)`
  - `run_lighting_specialist_pass(mood, time_of_day)`
  - `run_vision_critique(return_suggestions=True)`
  - `apply_critique_suggestions(suggestions)`

### 2.4 Vision-in-the-Loop

This is what makes it truly multi-agent and not just sequential scripts:

1. After Lighting pass → `capture_viewport_screenshot` + `analyze_scene_visuals`
2. Critique agent returns JSON like:
   ```json
   {"issues": [{"severity":"high","area":"lighting","msg":"Key light too frontal, flat shading on hero rock"}], "score": 68, "next_actions":["run_lighting_specialist_pass", "increase_contrast"]}
   ```
3. Coordinator can auto-apply or surface to the user/LLM.

This closes the loop using tools that **already exist** (`understanding_tools`).

### 2.5 Implementation Phases

**Phase 1 (Foundation, 2-3 days)**
- New `server/agents/` package + base coordinator skeleton
- `SceneAgent` abstract base + simple pass registry
- One high-level `orchestrate_scene_with_agents` tool that runs 2-3 fixed passes + optional critique
- Wire it into `create_scene_from_prompt` as an opt-in mode (`orchestration_mode="multi_agent"`)

**Phase 2 (Specialists, 4-5 days)**
- Implement GeometryAgent, LightingAgent, MaterialAgent as real classes that call existing ops intelligently
- CritiqueAgent that consumes vision output + quality score
- Iteration loop with early exit on high score

**Phase 3 (Power User + Polish)**
- Granular specialist tools exposed (DONE)
- Smart auto-execution of critique suggestions inside the coordinator (DONE)
- Full 5-agent system (geometry, materials, lighting, composition, critique)
- Combined `create_and_polish_real_world_terrain` super-tool (Terrain + Multi-Agent in one call)
- Terrain-aware intelligence in CritiqueAgent

### 2.6 Success Criteria
- `orchestrate_scene_with_agents(prompt="neo-Tokyo night alley, cyberpunk", focus_areas=["lighting","materials"], max_iterations=3)` produces visibly better results than single-shot on the same prompt.
- Vision critique actually catches real problems (flat lighting, bad scale, material clashes) and the next iteration measurably improves the quality_score.
- Power users can bypass the coordinator and drive individual agents for surgical control.

---

## 3. Combined Delivery Roadmap (Recommended Order)

Because the two features are synergistic:

1. **Week 1-1.5**: Satellite Terrain Phase A + B (the data fetching + basic mesh is pure server + one new Blender op file).
2. **Week 1.5-2.5**: Multi-Agent Foundation + Geometry + Lighting specialists + first vision loop. The terrain work gives us a perfect test case ("make the real Kapadokya terrain, then run multi-agent polish on it").
3. **Week 3**: Cross-polish — make the multi-agent coordinator aware of terrain scenes, add terrain-specific agents or passes if needed. Add caching, error handling, nice progress reporting via jobs.
4. **Polish & Docs**: Real-world examples (Kapadokya, Galata + Bosphorus extension, Pamukkale, Tokyo crossing, Grand Canyon).

**Why this order?**
- Satellite terrain has clearer external dependencies and a very visible output (you can literally see "this is real geography").
- Multi-agent benefits enormously from having a rich, complex scene type (real terrain + OSM buildings) as its primary demonstration target.
- Both reuse the same patterns (asset_source + orchestration).

---

## 4. File Change Summary

**Server (Python)**
- `server/tools/asset_source_tools.py` — heavy additions (geo tools)
- `server/agents/__init__.py`, `scene_coordinator.py`, `base_agent.py`
- `server/agents/geometry_agent.py`, `lighting_agent.py`, etc. (or keep in coordinator first)
- `server/tools/scene_tools.py` — new high-level `orchestrate...` tool
- Possibly small extension to `jobs.py` for long-running terrain downloads

**Blender Addon**
- `blender_addon/blender_ops/terrain_ops.py` (new)
- `blender_addon/blender_ops/registry.py` — register new ops
- Minor extensions to `game_ops.py` / `material_ops.py` for biome application

**Docs & Examples**
- Update `tool_reference.md`
- New examples under `examples/prompts/real_world_terrain.md` and `multi_agent_workflows.md`
- Add to `professional_mvp_plan.md` or create a "2026 Roadmap" note

**Dependencies**
- No hard new runtime deps for MVP (requests + Pillow already transitive).
- Recommend in README: `pip install numpy` (optional, big perf win for large heightmaps).

---

## 5. Risks & Mitigations

| Risk                        | Likelihood | Mitigation |
|----------------------------|------------|------------|
| Overpass rate limits on popular locations | Medium | Polite headers, client-side caching (already pattern in Poly Haven), smaller queries + simplification |
| Bad elevation data in some regions (AWS tiles) | Medium | Offer OpenTopography as one-click upgrade, expose quality metadata |
| Multi-agent loops taking too long / token cost | High (for LLM clients) | Hard iteration cap, early exit on score, expose "lite" mode (no vision), detailed timing in results |
| Complex geometry from real terrain killing viewport | Medium | Auto-decimate on import, offer "blockout" vs "detailed" resolution switch |
| Maintaining two big new surfaces | Medium | Strict adherence to existing patterns; both features should feel "native" |

---

## 6. Example User Experiences (After Delivery)

**Satellite**
```
> "Gerçek Kapadokya'da bir drone shot sahnesi yap, 1.5 km², stylized ama topoğrafya gerçek olsun"
→ geocode → fetch terrain (AWS) → fetch some fairy chimney hints via OSM landform → create displaced mesh + warm sunrise lighting + hero camera
```

**Multi-Agent**
```
> "Aynı sahneyi multi-agent ile 3 iterasyon polish'le, özellikle lighting ve materials'a odaklan"
→ Coordinator runs Geometry (skip) → Materials specialist → Lighting specialist → Critique (vision sees "too flat on rock faces") → Lighting refines rim + bounce → final score 87 (was 71)
```

---

## 7. Next Concrete Steps (If Approved)

1. Create the plan review branch or just start coding the terrain data layer (lowest risk, highest demo value).
2. Implement `geocode_location` + `fetch_elevation_for_bbox` first — can be tested completely outside Blender.
3. Once basic terrain lands in Blender, immediately wire the first two multi-agent specialists against it.

Together, these features would make real-world terrain workflows and iterative
scene-polish workflows easier to demonstrate and test.

Ready to start with whichever half should be de-risked first.

---

**Status**: Draft for review. Open to re-scoping, splitting, or changing priority between the two features.
