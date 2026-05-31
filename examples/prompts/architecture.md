# Architecture prompts

### Modern villa exterior
```
Create a modern villa exterior with two floors, large glass facade, concrete and
wood materials, pool, garden, pathway, trees, realistic lighting, and a portfolio
render setup.
```

### Floor-plan blockout
```
create_floor_plan_blockout(width=12, depth=9, rooms=4)
add_windows_doors_stairs(windows=6, doors=2, stairs=true)
add_architectural_details(level="medium")
```

### Scene repair
```
Inspect the current scene, fix missing materials, rename objects professionally,
set correct origins, add lighting if missing, and render a preview.
```
Tools: `inspect_scene` → `auto_fix_scene` → `render_preview`.
