# Example Prompts — PSD / Layered Image → 3D Scene

These prompts work with the `build_layered_scene_from_image` tool.

---

## 1. Basic PSD → 3D scene

```
Build a 3D scene from my concept art at ~/Desktop/my_scene.psd.
Export the result as a GLB file to ~/Desktop/scene_output/.
```

---

## 2. AI-enhanced scene (with Gemini Vision)

> Requires `GEMINI_API_KEY` set in your environment.

```
Analyse ~/Desktop/mediterranean_village.psd with AI vision and build a fully
positioned 3D scene in Blender. Use the Gemini-suggested object positions,
materials, and lighting to place each element accurately.
Export as GLB.
```

---

## 3. Flat image (PNG/JPEG) to 3D environment

```
Use ~/Downloads/concept_art.jpg as reference and create a Blender 3D environment
from it. Detect the sky, ground, water, and major scene elements automatically.
Set the render style to portfolio_render and export as GLB.
```

---

## 4. Custom prop placement overrides

```
Build a 3D scene from ~/Desktop/game_level.psd.
After generation, move the "castle_tower" prop to position (5.0, 2.0, 0.0)
and scale it to 2.5.
Export the final scene as FBX.
```

---

## 5. Multi-layer PSD with named layers

When your PSD uses semantic layer names, the system maps them automatically:

| Layer name contains | Mapped 3D role |
|---|---|
| `bg`, `back`, `sky`, `horizon` | background |
| `fg`, `fore`, `char`, `hero` | foreground |
| `prop`, `rock`, `tree`, `item` | prop |
| anything else | midground |

```
Open ~/Desktop/game_art.psd. It has layers named BG_Sky, Midground_Hills,
FG_Character, and Props_Rocks. Build the 3D scene respecting these roles
and add a golden-hour lighting preset.
```

---

## 6. PSB (large document) support

PSB files (Photoshop Big) are supported identically to PSD:

```
Build a 3D environment from my high-res concept art at ~/Documents/panorama.psb.
The file is 8K so use the fast_preview render preset while composing.
```

---

## Tips

- Place your API keys in `.env` (copy `.env.example` to `.env` and fill in the values).
- The AI vision analyser (`GEMINI_API_KEY`) dramatically improves accuracy on
  complex scenes with recognisable objects.
- For fastest iteration, start with `fast_preview` render preset, then switch to
  `portfolio_render` for the final export.
