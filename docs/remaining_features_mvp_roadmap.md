# Remirdy — Remaining Features MVP Roadmap (2026)

This document tracks everything from the original "Çılgın Fikirler" list that has not yet reached professional MVP quality.

Goal: Bring the entire Remirdy project to a **coherent, demonstrable MVP** where many ambitious ideas are usable at production-adjacent quality, with clear extension points for the rest.

---

## Current Status Overview (as of this session)

**Strongly Implemented (MVP-ready or close):**
- Satellite → 3D Terrain (with real elevation + OSM potential)
- Multi-Agent Scene Orchestration (5 specialists + vision critique + auto-refinement)
- Real-time Weather Lighting
- Asset auto-import & placement pipeline

**Scaffold / Partial (needs professionalization):**
- Video Reference → 3D
- Physics from Prompt
- 3D Printing Preparation
- Auto Asset Workflows

**Not Yet Started or Very Early:**
- Multi-LLM Orchestration
- Figma → 3D
- Viewport Live Streaming
- NeRF / Gaussian Splatting Pipeline
- Brand Compliance Engine
- Procedural City Generator (large scale)
- Full Unity/Unreal Project Export (prefabs, materials, lights, scenes)
- Audio Generation after render
- Real-time Multi-user Editing

---

## Prioritization for MVP

### Tier A — Must Have for Credible MVP (Do These Next)

| Feature                        | Effort | Impact | Priority | Target Quality for MVP |
|--------------------------------|--------|--------|----------|------------------------|
| Video Reference → 3D (deep)    | Medium | Very High | 1 | Frame analysis + multi-agent reconstruction |
| Professional 3D Printing Pipeline | Medium | High | 2 | Reliable manifold + thickness + export |
| Improved Physics from Prompt   | Low-Medium | High | 3 | Usable cloth + basic fluid + rigid |
| Enhanced Unity/Unreal Export   | Medium | Very High | 4 | Real .unitypackage + material + light export |
| Procedural City Blockout       | Medium | High | 5 | 1-2km² believable city from prompt |

### Tier B — Strong MVP Stretch Goals

- Figma → 3D (if Figma MCP connection exists)
- Basic Audio Generation hook (ElevenLabs / Suno style)
- Viewport Live Streaming (simple WebSocket version)

### Tier C — Post-MVP / Research Heavy

- NeRF / Gaussian Splatting full pipeline
- Brand Compliance Engine (PDF parsing + enforcement)
- Real-time Multi-user Collaborative Editing
- Multi-LLM Orchestration (browser automation or API proxy)
- Full Procedural City at high fidelity

---

## Detailed Plans for Tier A Items

### 1. Video Reference → 3D (Deep)

Current state: Basic scaffold that creates reference planes.

MVP Target:
- Extract frames from video or folder
- Use existing vision tools (`analyze_scene_visuals` + screenshots) or external vision
- Feed into Multi-Agent system for intelligent reconstruction
- Generate camera animation from video motion (rough)
- Output: Blockout + materials + camera move that matches the reference

Integration points: `create_scene_from_video_reference` + `orchestrate_scene_with_agents`

### 2. Professional 3D Printing Pipeline

Current state: Basic scaffold.

MVP Target:
- Non-manifold detection + auto-repair attempts
- Minimum wall thickness analysis + auto Solidify
- Support structure hints (or simple generation)
- Watertight export (STL/3MF) with metadata
- Printability report (score + actionable issues)

Tool: `prepare_for_3d_printing` + dedicated Blender ops in `quality_ops.py`

### 3. Physics from Prompt (Reliable)

Current state: Basic trigger.

MVP Target:
- Better prompt classification (cloth vs fluid vs destruction)
- Automatic setup of cloth on selected mesh
- Basic fluid domain + effector creation
- Rigid body + fracture options
- Integration with weather (wind affecting cloth)

### 4. Enhanced Unity / Unreal Full Project Export

Current state: Basic GLB/FBX export exists.

MVP Target:
- Proper Unity package export (prefabs, materials as .mat, lights, cameras)
- Unreal .uproject structure with materials and actors
- LOD generation during export
- Metadata (collision, sockets, lightmaps)

### 5. Procedural City Blockout Generator

MVP Target:
- Prompt → "neo-Tokyo night, 1.5 km²"
- Grid-based + organic street layout
- Building height variation + simple modular kits
- Night lighting + emissive windows
- Integration with Multi-Agent for polishing

---

## Heavy Items — Professional Scaffolds (Tier C)

For these, we will create:
- Clear architectural design document
- Entry-point MCP tool (even if limited)
- Integration points with existing Multi-Agent and vision systems
- Honest "what would a full implementation require" section

Items in this category:
- NeRF / 3DGS Pipeline
- Brand Compliance Engine
- Real-time Multi-user Editing
- Multi-LLM Browser Orchestration

---

## Professionalization Requirements (Applies to Everything)

Before declaring MVP:
- Consistent error handling + helpful messages across all new tools
- Proper job system usage for long-running operations (terrain, video analysis, exports)
- Telemetry coverage
- Example prompts + expected outputs in `examples/`
- Updated `professional_mvp_plan.md`
- One "killer demo" workflow that combines 4+ ambitious features (e.g. real terrain + weather + multi-agent polish + 3D print export)

---

## Next Actions (Recommended Order)

1. Video Reference → 3D deep integration with Multi-Agent
2. Professional 3D Printing pipeline
3. Physics improvements
4. Unity/Unreal export enhancement
5. Procedural City Blockout
6. Heavy item architectural scaffolds
7. Full professionalization + docs pass
8. Comprehensive testing + demo workflows

---

**Status**: Living document. Will be updated as work progresses.

Last updated: During the "complete all remaining items + professionalize for MVP" phase.
