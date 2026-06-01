# Heavy Features — Professional Architecture & Scaffolds

This document defines the architectural approach for the most ambitious remaining items from the original list. These are intentionally scoped as **MVP scaffolds with clear production paths**.

---

## 1. NeRF / Gaussian Splatting Pipeline

**Goal**: Turn a folder of photos or a short video into a 3D asset that can be imported and edited in Blender.

**MVP Scope (Scaffold)**:
- Accept a folder of images or video path
- Job-based long-running task
- Call external tools (if configured): `ns-process-data`, `instant-ngp`, `3DGS` training, or TripoSR-style local models
- Export as `.ply` + `.splat` or baked mesh + textures
- Import into Blender with basic material

**Production Path**:
- Dedicated provider in `server/providers/nerf_gs/`
- Progress polling + preview generation
- Automatic cleanup + LOD creation
- Integration with Multi-Agent for material/lighting cleanup after import

**Entry Point Tool** (to be implemented):
`generate_nerf_from_images(folder_path, method="3dgs|nerf", quality="medium")`

---

## 2. Brand Compliance Engine

**Goal**: User uploads brand guidelines (PDF / images / colors) → AI respects them during scene generation.

**MVP Scope**:
- Accept brand PDF or color palette + logo references
- Extract dominant colors + logo placement rules (simple parsing)
- Before final render / export, run a "compliance check" pass
- Flag or auto-fix violations (wrong red, bad logo placement, etc.)

**Production Path**:
- Use vision models to deeply parse brand guidelines
- Store brand profile in workspace
- Multi-Agent "Brand Agent" that runs as a mandatory pass
- Export compliance report

**Entry Point**:
`load_brand_guidelines(path)` + `run_brand_compliance_check()`

---

## 3. Real-time Multi-user Collaborative Editing

**Goal**: Multiple AI agents (or humans + AI) editing the same Blender scene live.

**MVP Scope (Very Limited)**:
- Basic WebSocket bridge that can broadcast scene changes
- Simple conflict resolution (last writer wins for transforms)
- One "host" Blender + multiple thin clients (or other MCP instances)

**Production Path**:
- Proper CRDT or operational transform system for 3D data
- Scene delta compression
- Permission / locking model
- Integration with the existing bridge

**Current Status**: Not started. Extremely high complexity.

---

## 4. Multi-LLM Orchestration (Browser Automation Style)

**Goal**: Use ChatGPT, Gemini, Grok, Claude in parallel via browser automation or API, then pick the best output for scene planning.

**MVP Scope**:
- Simple round-robin or parallel call to configured LLM providers (via existing `google-genai` or future adapters)
- "Best of N" scene plan selection using the CritiqueAgent as judge
- Fallback when one provider fails

**Production Path**:
- Browser automation (Playwright / Selenium) for models without good APIs
- Structured output parsing + voting
- Cost / latency tracking

**Entry Point**:
`orchestrate_with_multiple_llms(prompt, models=["claude", "gpt4", "grok"], judge_with_critique=True)`

---

## Implementation Principles for All Heavy Features

1. Never block the main bridge.
2. Always go through the job system.
3. Every heavy feature must have a "lite" fallback that still produces useful output.
4. All features must integrate with the existing Multi-Agent + Vision system.
5. Clear separation between "data fetching / heavy compute" (server) and "scene manipulation" (Blender ops).

---

**Status**: Architectural foundation. Actual deep implementation will happen after the current MVP professionalization pass.
