# Advanced Feature Roadmap

This note tracks larger ideas that are not part of the core install path yet.
The goal is to keep future work realistic: each item should have a clear user
workflow, a testable output, and a fallback when external services are not
configured.

## Principles

- Prefer local Blender operations where possible.
- Use the job system for long-running work.
- Report progress and failure reasons clearly.
- Keep licensing and attribution visible for imported assets.
- Support both high-level workflows and lower-level tool control.

## Candidate Features

### Video-to-3D Reconstruction

Input: a video clip or image sequence.

Expected output: a Blender scene with approximate camera placement, blockout
geometry, materials, lighting notes, and a reconstruction report.

This builds on `create_scene_from_video_reference`, visual analysis tools, and
the existing scene quality checks.

### Asset Curation and Placement

Input: a request such as "find rocks that match this terrain scene".

Expected output: imported assets with scale checks, attribution metadata,
reasonable placement, and a short import report.

### Scene Optimization and Delivery

Input: an existing Blender scene.

Expected output: engine-focused cleanup for Unity, Unreal, or web delivery:
material consolidation, collision proxies, export settings, and a readiness
report.

### Time, Weather, and Lighting Studies

Input: a scene and a time/weather brief.

Expected output: lighting variants or animation data that can be reviewed for
architectural visualization, previz, or environment design.

### Batch Project Mode

Input: a JSON/YAML project definition.

Expected output: queued renders/exports with a combined report, useful for
product variations, campaign renders, or repeated environment studies.

## Current Status

These are roadmap items. They should be implemented incrementally and kept out
of the default happy path until they have tests, examples, and clear failure
handling.
