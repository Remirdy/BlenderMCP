# Remirdy couture runway

The README showcase is rendered from [`create_couture_showcase.py`](../scripts/create_couture_showcase.py). It is a local Blender scene build, with no cloud generation service or API key required.

The 20-second film presents six looks: an emerald gown with sculpted shoulders, a champagne petal dress, an asymmetric garnet dress, a midnight trouser suit, a sapphire dress with a simulated cape, and an ivory mini dress with sculptural sleeves. Sixteen seated guests wear fitted business outfits.

Each look retains its full ten-second source choreography, played at 3× speed in the final film, with tracking, portrait, and turn views. The characters walk, transfer their weight, bring a hand to the waist, pose their head and shoulders, and perform a pivot turn. The final film contains 480 rendered frames at 24 fps. Every source segment is retained; the renderer samples across each complete choreography, including its first and last frame. The inline GIF is a short six-look trailer.

The walking controls start from MPFB's bundled experimental female cycle, resampled to every output frame with continuous root motion. Bodices and upper accessories receive skin weights from the character rig. Separate skirts and the sapphire cape use Blender Cloth with pinned seams, body collision, and self collision. The solver output is baked into shape keys, and waist seams are fitted to the skinned bodice. The saved scene plays the simulated fabric without external point-cache files. Structured shoulders retain their sculpted form; decorative layers also use art-directed motion. Review new poses before reusing the garments in another choreography.

## Requirements

- Blender 5.1 with MPFB 2.0.15 (the tested extension version) installed from Blender's extension repository.
- The CC0 [MakeHuman system assets pack](https://static.makehumancommunity.org/assets/assetpacks/makehuman_system_assets.html).
- Python with Pillow for the inline GIF. Video encoding uses Blender's bundled H.264 encoder.

The human meshes, skin, eyes, hair, and audience outfit sources come from MakeHuman's CC0 system assets. The scene builder creates the runway garments, accessories, stage, cameras, lighting, and animation setup. Source assets and generated `.blend` files stay in the ignored `outputs/` directory.

## Prepare the source assets

Download `makehuman_system_assets_cc0.zip` from the MakeHuman page, then extract the subset used by the scene:

```bash
python scripts/prepare_couture_assets.py /path/to/makehuman_system_assets_cc0.zip
```

This creates `outputs/couture/source_assets/`. To use another directory, pass `--output` to the preparation script and `--assets` to the scene builder.

## Build and render

Use your Blender executable in place of `blender`:

```bash
blender --background --threads 2 --python scripts/create_couture_showcase.py -- --mode build
```

The self-contained scene is saved to `outputs/couture/remirdy_couture.blend`, with packed image textures, baked cloth motion, and a 24 fps timeline. The cloth solve runs before the scene is saved. The builder starts with a new scene; run it in a separate Blender process to preserve any open project.

Render a Cycles still:

```bash
blender --background --threads 2 --python scripts/create_couture_showcase.py -- --mode still --shot gallery --width 1440 --samples 64
```

Render every frame of the runway sequence:

```bash
blender --background --threads 2 --python scripts/create_couture_showcase.py -- --mode animation --shot gallery --engine BLENDER_EEVEE --width 1280 --samples 64 --start 1 --end 144
```

Use `--shot detail` for the moving textile camera. Output folders are separate for the two shots. `--output` changes the generated scene and render location. The base scene builder uses two CPU threads; render time depends on the engine, resolution, sample count, and hardware. On an Apple Silicon Mac, `--device METAL` enables Cycles GPU rendering for that process. It does not save global Blender preferences.

## Prepare the six-look film

After building the base scene, add the three additional looks, the runway poses, the pivot turns, and the extended cloth simulation:

```bash
blender --background --threads 2 --python scripts/create_couture_film.py
```

The result is `outputs/couture_film/remirdy_couture_film.blend`. Its six numbered collections contain the individual looks. The original three are visible when the file opens; the other collections can be enabled individually. The source choreography spans frames 25–264 for each look.

## Render the 20-second film

```bash
blender --background outputs/couture_film/remirdy_couture_film.blend --threads 4 --python scripts/render_couture_film.py -- --width 1280 --samples 16 --duration 20 --resume
```

The renderer creates `film_frames_20s/frame_000001.png` through `frame_000480.png`, with 80 frames per look and camera cuts between the tracking, portrait, and turn views. `--start` and `--end` select an output range. `--resume` preserves existing complete PNG or lossless WebP frames of the requested resolution. Use `--duration 60 --output outputs/couture_film/film_frames_60s` to render the original-speed version instead. Keep separate output folders for different durations so resume cannot mix them. The film renderer uses four CPU threads; the base scene builder uses two. Use `--engine CYCLES --device METAL` for the Cycles path on a compatible Apple Silicon Mac.

## Encode the media

```bash
blender --background --threads 2 --python scripts/encode_couture_video.py -- outputs/couture_film/film_frames_20s docs/assets/remirdy_couture_runway.mp4 --width 1280 --height 800
python scripts/encode_couture_gif.py outputs/couture_film/film_frames_20s docs/assets/remirdy_couture_runway.gif --width 720 --film-teaser
```

The encoders accept PNG and WebP frames and reject sequences with missing frames. The MP4 retains all 480 output frames at 24 fps, giving exactly 20 seconds. The GIF selects six continuous one-second excerpts and uses a shared palette to reduce flicker. GIF delays alternate between 40 and 50 ms because that format stores time in hundredths of a second.

## Using the scene with the bridge

Open the generated `.blend` file in Blender, start the Remirdy bridge, and call `connect_blender` followed by `get_scene_summary`. The showcase script runs locally through Blender's command line. It does not add an arbitrary-Python execution tool to the MCP bridge.
