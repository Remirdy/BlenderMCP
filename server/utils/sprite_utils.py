"""Sprite sheet slicing and segmentation utilities for 3D multi-view pipelines.

This module automates the extraction of individual pose views (e.g. Front, Side,
Back) from a character sprite sheet or multi-pose concept card. Slicing these
views allows multi-view image-to-3D pipelines to generate superior 3D models.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("remirdy.utils.sprites")


def slice_sprite_sheet(
    image_path: str, output_dir: str, num_slices: int = 3
) -> tuple[str, list[str]]:
    """Slice a horizontally-oriented sprite sheet into separate pose files.

    Returns:
        tuple[str, list[str]]: (primary_front_view_path, [extra_view_paths...])
    """
    image_path_obj = Path(image_path).expanduser().resolve()
    if not image_path_obj.exists():
        log.warning("Sprite sheet image not found: %s", image_path)
        return image_path, []

    # Ensure output directory exists
    out_dir_path = Path(output_dir).expanduser().resolve()
    out_dir_path.mkdir(parents=True, exist_ok=True)

    try:
        from PIL import Image
    except ImportError:
        log.warning(
            "PIL (Pillow) is not installed in the server environment. "
            "Sprite sheet auto-slicing falls back to returning the original image. "
            "To enable 10/10 multi-view generation, please install Pillow."
        )
        return str(image_path_obj), []

    try:
        img = Image.open(image_path_obj)
        width, height = img.size

        # Simple verification: if image is taller than it is wide, it's probably not a horizontal sheet
        if height >= width:
            log.info("Image is vertical or square (%dx%d); skipping slicing.", width, height)
            return str(image_path_obj), []

        # Find transparent/white bounding margins to crop empty edges
        # We sample a subset of pixels to find non-empty bounds
        rgba_img = img.convert("RGBA")
        pixels = rgba_img.load()

        min_x, max_x = width, 0
        min_y, max_y = height, 0

        # Sample pixel alpha to find bounding box of character content
        # Step value for faster analysis of large images
        step = max(1, min(width, height) // 100)
        for y in range(0, height, step):
            for x in range(0, width, step):
                r, g, b, a = pixels[x, y]
                # Consider non-empty if alpha > 15 and not pure white (if white background)
                is_bg = a < 15 or (r > 240 and g > 240 and b > 240)
                if not is_bg:
                    min_x = min(min_x, x)
                    max_x = max(max_x, x)
                    min_y = min(min_y, y)
                    max_y = max(max_y, y)

        # Apply margin padding around detected content bounds
        padding = 10
        if max_x > min_x and max_y > min_y:
            min_x = max(0, min_x - padding)
            max_x = min(width, max_x + padding)
            min_y = max(0, min_y - padding)
            max_y = min(height, max_y + padding)
        else:
            # Fall back to full size if no content detected
            min_x, max_x = 0, width
            min_y, max_y = 0, height

        cropped_w = max_x - min_x
        slice_w = cropped_w // num_slices

        log.info(
            "Slicing sprite sheet (detected content bounds: X [%d-%d], Y [%d-%d]) into %d views",
            min_x,
            max_x,
            min_y,
            max_y,
            num_slices,
        )

        slice_paths = []
        stem = image_path_obj.stem

        for i in range(num_slices):
            slice_min_x = min_x + i * slice_w
            # Make sure the last slice covers all the way to the boundary
            slice_max_x = (min_x + (i + 1) * slice_w) if i < num_slices - 1 else max_x

            # Crop slice
            box = (slice_min_x, min_y, slice_max_x, max_y)
            slice_img = rgba_img.crop(box)

            # Save slice
            slice_filename = f"{stem}_slice_{i}.png"
            slice_path = out_dir_path / slice_filename
            slice_img.save(slice_path, "PNG")
            slice_paths.append(str(slice_path))

        log.info("Successfully extracted %d slices: %s", len(slice_paths), slice_paths)

        # Front is typically the first slice (slice 0), and others are extra views (e.g. Side, Back)
        primary = slice_paths[0]
        extras = slice_paths[1:]
        return primary, extras

    except Exception as exc:
        log.error("Failed to slice sprite sheet: %s", exc)
        return str(image_path_obj), []
