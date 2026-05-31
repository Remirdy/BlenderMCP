"""Preset metadata and shared schema constants.

These describe the high-level presets the system exposes. The actual geometry
is generated inside Blender by the bridge, but keeping the catalog here lets the
MCP layer validate input and surface choices to the AI client.
"""
from __future__ import annotations

GAME_PRESETS = {
    "mobile_stylized": "Low/mid poly, bright colors, simple readable shapes, optimized materials.",
    "pc_game_environment": "Detailed modular geometry, richer lighting, export-ready.",
    "low_poly": "Clean geometric style, minimal materials, fast generation.",
    "stylized_cartoon": "Rounded shapes, saturated colors, soft lighting.",
    "sci_fi_game_level": "Modular panels, emissive lights, corridors, doors, props.",
}

ARCH_PRESETS = {
    "modern_villa": "Large windows, concrete/wood/glass, landscaping, realistic proportions.",
    "luxury_apartment": "Modern living room, furniture layout, warm lighting.",
    "minimalist_interior": "Clean forms, neutral materials, soft natural light.",
    "office_interior": "Desks, chairs, meeting area, lighting panels, glass partitions.",
    "retail_store": "Product shelves, display counters, commercial lighting.",
}

RENDER_PRESETS = {
    "fast_preview": "Eevee/Workbench, low samples, quick checks.",
    "portfolio_render": "Eevee Next/Cycles, AO, contact shadows, filmic, 1080p+.",
    "archviz_render": "Cycles, higher samples, natural light, realistic focal length.",
    "product_render": "Studio lighting, clean background, optional DoF, centered.",
    "cinematic_render": "Dramatic lighting, optional volumetrics, filmic color.",
}

SCENE_KINDS = (
    "game_environment",
    "architectural_exterior",
    "interior_design",
    "product_render",
    "cinematic",
)

EXPORT_TARGETS = ("generic", "unity", "unreal")
