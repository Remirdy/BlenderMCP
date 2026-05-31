# Game environment prompts

### Stylized mobile campus (flagship)
```
Create a stylized mobile game campus scene with a canteen, library, copy center,
trees, roads, students as simple characters, isometric camera, bright cartoon
materials, and export it as Unity-ready GLB.
```
Tools exercised: `create_scene_from_prompt` → game_environment / mobile_stylized →
auto-fix → `export_glb(target="unity")`.

### Sci-fi corridor level
```
Create a futuristic sci-fi game corridor with modular wall panels, emissive blue
lights, metallic floor, doors, vents, cinematic lighting, and export it as FBX.
```

### Low-poly prototype
```
Create a low-poly nature environment with scattered trees and rocks, isometric
camera and bright lighting for a quick prototype.
```

### Manual build
```
create_mobile_game_scene(theme="campus", isometric_camera=true)
optimize_for_game_engine(target_tris=50000)
prepare_for_unity_export()
export_glb(filename="campus.glb", target="unity")
```
