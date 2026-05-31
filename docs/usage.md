# Usage

## Quick start

1. `connect_blender`
2. `create_scene_from_prompt(prompt="Create a stylized mobile game campus … export Unity GLB", render_after=true)`
3. Inspect the structured response: created objects, scene summary, auto-fix report, render path, export path, suggested next commands.

## The prompt pipeline

`create_scene_from_prompt` runs end to end:

1. **Classify** the intent (game / architecture / interior / product / cinematic) via `blender_ops/prompt_router.py`.
2. **Build** geometry, materials, camera and lighting with the matching domain builder.
3. **Apply** a render preset.
4. **Auto-fix** issues (`auto_fix_scene`) when `auto_fix=true`.
5. **Render** a preview when `render_after=true`.
6. **Export** if the prompt mentions Unity/GLB/Unreal/FBX.

## Working step by step

You can also drive each stage manually:

```
clear_scene
create_living_room_scene(style="luxury_apartment", warm_lighting=true)
apply_interior_material_palette(palette="warm_modern")
setup_archviz_camera(focal_length=28)
setup_archviz_lighting(time_of_day="sunset", interior=true)
apply_render_preset(preset="archviz_render")
scene_quality_check
render_final(width=1920, height=1080, samples=128, filename="livingroom.png")
export_blend(filename="livingroom.blend")
```

## Game export

```
create_game_environment(style="mobile_stylized", theme="campus", isometric_camera=true)
optimize_for_game_engine(target_tris=50000)
prepare_for_unity_export()
export_glb(filename="campus.glb", target="unity")
```

## Outputs

Everything lands under `<workspace>/outputs/`:

- `blends/` — saved `.blend` files
- `exports/` — `.glb`, `.fbx`, `.obj`
- `renders/` — still images and turntable videos
- `thumbnails/` — reserved for preview thumbnails
