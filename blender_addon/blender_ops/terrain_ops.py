"""Real-world terrain generation from elevation heightmaps (Satellite → 3D)."""
from __future__ import annotations

import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

from . import helpers as H


def op_create_terrain_from_heightmap(params: dict) -> dict:
    """
    Create a real displaced terrain mesh from a heightmap PNG (grayscale).
    Expects the heightmap to be produced by the server-side AWS Terrarium pipeline.
    """
    heightmap_path = params.get("heightmap_path")
    if not heightmap_path or not Path(heightmap_path).exists():
        raise ValueError(f"Valid heightmap_path is required. Got: {heightmap_path}")

    resolution = int(params.get("resolution", 256))
    exaggeration = float(params.get("exaggeration", 1.6))
    real_world_scale_m = float(params.get("real_world_scale_m", 300))
    location_name = params.get("location_name", "Real Terrain")
    style = params.get("style", "stylized")
    add_sun = params.get("add_sun", True)

    # Load heightmap
    img = bpy.data.images.load(str(Path(heightmap_path).expanduser()), check_existing=True)
    img_width, img_height = img.size
    if img_width < 8 or img_height < 8:
        raise ValueError("Heightmap image is too small")

    # Sample pixels into a 2D height array (normalized 0-1)
    pixels = img.pixels[:]
    height_data = []
    for y in range(img_height):
        row = []
        for x in range(img_width):
            idx = (y * img_width + x) * 4
            # Use average of RGB as height (our pipeline already made it grayscale-ish)
            h = (pixels[idx] + pixels[idx + 1] + pixels[idx + 2]) / 3.0
            row.append(h)
        height_data.append(row)

    # Create dense grid
    env = H.get_or_create_collection("Environment")
    terrain_coll = H.get_or_create_collection("Terrain", parent=env)

    size = real_world_scale_m
    # Resolution here is vertex count per side
    verts_x = max(32, min(resolution, 512))
    verts_y = max(32, min(resolution, 512))

    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=verts_x - 1,
        y_subdivisions=verts_y - 1,
        size=size,
        location=(0, 0, 0),
    )
    grid = bpy.context.object
    grid.name = f"Terrain_{location_name.split(',')[0][:24].replace(' ', '_')}"
    H.link_to_collection(grid, terrain_coll)

    # Apply displacement from height_data
    bm = bmesh.new()
    bm.from_mesh(grid.data)

    # Build lookup: height_data is img_height rows, img_width cols
    def sample_height(u: float, v: float) -> float:
        """u,v in 0..1 → sampled height 0..1"""
        ix = min(int(u * (img_width - 1)), img_width - 1)
        iy = min(int((1.0 - v) * (img_height - 1)), img_height - 1)  # flip Y
        return height_data[iy][ix]

    for vert in bm.verts:
        # Grid verts are -size/2 .. +size/2
        u = (vert.co.x + size / 2.0) / size
        v = (vert.co.y + size / 2.0) / size
        h_norm = sample_height(u, v)
        vert.co.z = (h_norm - 0.5) * real_world_scale_m * exaggeration * 0.01

    bm.to_mesh(grid.data)
    bm.free()
    grid.data.update()

    # Shade smooth + optional subsurf for nicer look
    bpy.ops.object.shade_smooth()
    if resolution >= 128:
        subs = grid.modifiers.new("TerrainSubsurf", "SUBSURF")
        subs.levels = 1
        subs.render_levels = 2

    # Basic material
    if style == "realistic":
        mat = H.make_material(
            f"Terrain_Real_{grid.name[-12:]}",
            color=(0.40, 0.36, 0.30, 1.0),
            roughness=0.85,
        )
    else:
        mat = H.make_material(
            f"Terrain_Stylized_{grid.name[-12:]}",
            color=(0.55, 0.48, 0.38, 1.0),
            roughness=0.75,
        )
    if grid.data.materials:
        grid.data.materials[0] = mat
    else:
        grid.data.materials.append(mat)

    created = [grid.name]

    # Simple directional sun (optional)
    if add_sun:
        sun = bpy.data.objects.new("Terrain_Sun", bpy.data.lights.new("Terrain_Sun", "SUN"))
        sun.location = (size * 0.6, size * 0.4, size * 0.9)
        sun.rotation_euler = (math.radians(55), math.radians(25), math.radians(140))
        sun.data.energy = 4.0
        sun.data.angle = math.radians(8)
        H.link_to_collection(sun, terrain_coll)
        created.append(sun.name)

    # Nice top-down / angled camera suggestion
    cam = bpy.data.objects.new("Terrain_Camera", bpy.data.cameras.new("Terrain_Camera"))
    cam.location = (size * 0.35, -size * 0.85, size * 0.55)
    cam.rotation_euler = (math.radians(62), 0, math.radians(22))
    cam.data.lens = 35
    H.link_to_collection(cam, H.get_or_create_collection("Cameras"))
    created.append(cam.name)

    return {
        "created": created,
        "terrain": grid.name,
        "location": location_name,
        "real_world_scale_m": real_world_scale_m,
        "exaggeration": exaggeration,
        "vertex_count": len(grid.data.vertices),
        "heightmap_used": str(heightmap_path),
    }
