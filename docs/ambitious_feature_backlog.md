# Remirdy Ambitious Feature Backlog

This document organizes the "çılgın" feature ideas into a realistic, prioritized execution plan.

## Guiding Philosophy
- Build on existing strengths (Multi-Agent system, OptimizationAgent, Terrain, Video reference, Jobs, Vision tools).
- Every feature should feel magical but be production-usable.
- Prioritize features that create strong "wow" moments with relatively contained scope.

---

## Tier S — Super High Impact / Feels Like Magic (Start Here)

### 1. AI Director Mode (Automatic Shot Planning + Video Storyboard)
**Description**: One scene → AI Director plans 5 shots (establishing, medium, close-up, dramatic angle, top-down), renders them, stitches with FFmpeg + transitions → ready video storyboard.

**Why it fits**: Leverages CritiqueAgent + Multi-Agent + render pipeline heavily. Very visual and impressive.

**Dependencies**: Multi-Agent, render tools, FFmpeg wrapper (new but small).

**Priority**: ★★★★★

---

### 2. "What If" Engine
**Description**: Take any scene → generate 5 dramatic variants ("what if it was on fire?", "50 years abandoned?", "cyberpunk version?", etc.) using Multi-Agent + OptimizationAgent. Each runs as a job.

**Why it fits**: Almost direct extension of current OptimizationAgent + Multi-Agent. Extremely powerful creative tool.

**Priority**: ★★★★★

---

### 3. Agent Self-Improvement Loop
**Description**: CritiqueAgent learns from high-scoring scenes and automatically refines its own prompts/weights over time.

**Why it fits**: Meta layer on top of existing CritiqueAgent. Makes the whole system feel alive.

**Priority**: ★★★★

---

## Tier A — High Value for Specific Users

### 4. Narrative Scene Engine
Add story/lore layer on top of environments (blood trails, mourning NPCs, closed shops, etc. based on text description).

### 5. Time-of-Day × Season Matrix
One command → render 4 times of day × 4 seasons = 16 variants as a sprite sheet or grid.

---

## New Ideas from Latest User List (High Priority)

### AI Director Mode (Enhanced)
- Full automatic shot planning (5 specific angles)
- Camera + lighting setup per shot
- Render + FFmpeg video + transitions
- Narrative Scene Engine integration

### Narrative Scene Engine
- Text description of story events → automatic environmental storytelling (blood, closed shops, emotional poses, evidence markers, etc.)

### Time-of-Day × Season Matrix
- 4x4 matrix rendering with proper HDRI + sun positioning + seasonal changes

### Game Jam Machine
- Theme in → complete playable Godot/Unity scene + scripts + UI + packaging + itch.io draft

### Davranış Ağacı Üretici (Behavior Tree Generator)
- Natural language NPC description → working state machine code + placed character with colliders

### Screenshot → Playable Level
- Image → full layered 3D reconstruction + colliders + export

### AI Oyun Testçisi
- Automated playability analysis from the player's perspective

### Sonsuz Yeniden Üretilebilir Dünyalar
- Seed-based deterministic world generation

### Shader → GLSL/HLSL Export
- Blender shader nodes → real engine shader code

### Storyboard → 3D Animatik
- Hand-drawn panels → 3D reconstructed animatic with cameras and timing

### Karakter Turnaround Otomatik Üretici
- Front concept → full 360 turnaround render + model

### Tek Tuşla Çizgi Film Shader'ı
- Multiple professional toon styles (Ghibli, Spider-Verse, etc.)

### Senaryo → Animasyonlu Sahne
- Dialogue + characters → blocked scene with facial animation and camera cuts

### İfade Tablosu Otomatik Renderer
- Character → full facial expression reference sheet

### Devamlılık Denetleyicisi (Continuity Checker)
- Compare two shots/scenes for continuity errors using vision

### Renk Scripti Üretici
- Scene description → emotional color/lighting script + direct application

### Browser Automation Layer (Foundation)
- Midjourney → Blender
- ArtStation style reference scraping + application
- itch.io auto-publishing
- Google Street View → 3D scene

---

## Execution Phases (Realistic)

**Phase 1 (Current - High Momentum)**
- AI Director Mode (full implementation)
- "What If" Engine
- Optimization & Delivery Agent (already strong)
- Core professionalization (jobs, error handling)

**Phase 2**
- Narrative Scene Engine
- Time-of-Day × Season Matrix
- Agent Self-Improvement Loop

**Phase 3**
- Game Jam Machine
- Behavior Tree Generator
- Screenshot → Playable Level

**Phase 4**
- Browser Automation foundation
- Advanced creative tools (Scene DNA, Physics Oracle, Continuity Checker, etc.)

### 6. Game Jam Machine
Theme in → full playable Godot/Unity scene + scripts + package + itch.io draft out.

### 7. Behavior Tree Generator (for NPCs)
Natural language description → working state machine code + placed character with colliders.

### 8. Screenshot → Playable Level
Game screenshot or concept art → layered 3D reconstruction + colliders + Godot/Unity export.

---

## Tier B — Very Ambitious (Longer Term)

- Crowd Simulation via Geometry Nodes (500+ unique NPCs)
- Scene DNA Cloner (extract style fingerprint from image/render and apply to another scene)
- Blender as Physics Oracle (ask engineering questions, get simulation-backed answers)
- Devamlılık Denetleyicisi (continuity checker between shots)
- Browser Automation Layer (Midjourney → Blender, ArtStation style transfer, itch.io auto-publish, Street View → Scene, etc.)

---

## Recommended Execution Order (Next 4-6 Weeks)

1. **AI Director Mode** (highest magic/value ratio)
2. **"What If" Engine** (builds directly on current agents)
3. **Agent Self-Improvement Loop** (makes the system feel intelligent)
4. **Narrative Scene Engine** or **Time-of-Day × Season Matrix**
5. Start **Browser Automation Layer** foundation (Playwright or similar) — this unlocks many "no API key" dreams.

---

**Status**: Living document. Will be updated as features are implemented.
