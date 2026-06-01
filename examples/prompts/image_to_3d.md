# Example Prompts — Image to 3D Model

These prompts work with the `generate_3d_from_image` and related tools.

---

## Provider overview

| Provider | Type | API Key env var | Speed | Quality |
|---|---|---|---|---|
| **Meshy** | Cloud | `MESHY_API_KEY` | ~60 s | ⭐⭐⭐⭐ |
| **Tripo** | Cloud | `TRIPO_API_KEY` | ~45 s | ⭐⭐⭐⭐⭐ |
| **Rodin** | Cloud | `RODIN_API_KEY` | ~90 s | ⭐⭐⭐⭐⭐ |
| **Hunyuan3D** | Cloud | `HUNYUAN3D_API_KEY` | ~120 s | ⭐⭐⭐⭐ |
| **Local (TripoSR)** | Local | `REMIRDY_LOCAL_IMAGE_TO_3D_COMMAND` | ~30–300 s | ⭐⭐⭐ |

---

## 1. Auto provider (try all configured, use first success)

```
Convert ~/Desktop/sneaker.png into a 3D model and import it into the current
Blender scene. Use the best available provider automatically.
```

---

## 2. Specific cloud provider — Meshy

```
Use Meshy to generate a 3D model from ~/Downloads/pottery_jug.jpg.
Enable PBR textures and target a quad topology at 80 000 polygons.
Import the result into Blender and apply a studio lighting setup.
```

---

## 3. Specific cloud provider — Tripo

```
Generate a 3D game asset from ~/Desktop/character_concept.png using Tripo.
Target low-poly (10 000 triangles) for a mobile game. Export as GLB.
```

---

## 4. Local generation (TripoSR / custom command)

> Requires `REMIRDY_LOCAL_IMAGE_TO_3D_COMMAND` set in `.env`.

```
Run a local image-to-3D conversion on ~/Desktop/product_photo.jpg using my
local TripoSR installation. Import the resulting GLB into Blender.
```

---

## 5. Parallel pipeline (cloud + local race)

```
Convert ~/Desktop/vehicle.png to 3D using the parallel pipeline — run cloud
and local models simultaneously and use whichever finishes first.
```

---

## 6. Batch conversion

```
Convert all PNG files in ~/Desktop/game_assets/ to 3D models using Meshy.
Place each imported model in a grid layout in Blender, 2 m apart.
Export the full scene as a GLB.
```

---

## 7. Full end-to-end: image → 3D → render

```
Take ~/Desktop/chair_concept.png, generate a 3D model with Tripo,
import it into Blender, apply a metallic_paint material in teal (#4A90A4),
set up a product_render lighting preset, and render a 1920×1080 PNG to
~/Desktop/chair_render.png.
```

---

## Tips

- Set your API keys in `.env` (see `.env.example`).
- `parallel` mode is great when latency matters and you have both a cloud key
  and a local model installed.
- For production assets, prefer `rodin` or `tripo` — they produce the cleanest
  topology and textures.
- Use `enable_pbr: true` (default) for physically-based materials that look
  correct under any lighting.
