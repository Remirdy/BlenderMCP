# Feature Backlog

This backlog collects future ideas and organizes them by practical value and
implementation risk. It is not a promise that every feature exists today.

## Near-Term

### Shot Planning

Create a small set of cameras for an existing scene, render previews, and return
a contact sheet. This is useful for reviewing composition without manually
placing every camera.

### Scene Variants

Generate controlled variations of an existing scene, such as time of day,
weather, material palette, or level-of-detail changes.

### Narrative Scene Details

Add small environmental storytelling elements from a scene brief: props, signs,
lighting cues, object placement, and camera notes.

### Optimization Report

Inspect a scene for export readiness: polygon counts, material count, naming,
missing cameras, missing lights, and likely engine issues.

## Mid-Term

### Time-of-Day and Season Matrix

Render a scene across a small matrix of lighting and environment states.

### Screenshot-to-Level Blockout

Use a reference image to create a layered scene blockout with colliders and
engine export notes.

### Behavior Tree Drafts

Turn a plain-language NPC behavior description into a simple state machine or
behavior tree draft for a target engine.

### Character Turnaround

Create a camera rig and render set for reviewing a character from multiple
angles.

## Long-Term

- Crowd simulation helpers
- Shader node to engine shader export
- Continuity checks across shots
- Browser-assisted asset/reference collection
- Storyboard-to-3D animatic workflows

## Notes

Each backlog item should include:

- A minimal user workflow
- Input and output formats
- Dependencies
- Tests or smoke checks
- Clear behavior when optional providers are missing
