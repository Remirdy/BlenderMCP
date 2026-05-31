"""Material libraries and material operations."""
from __future__ import annotations

import bpy

from . import helpers as H

# Curated procedural palettes. Each entry: name -> (rgb, metallic, roughness, emission)
STYLIZED_LIB = {
    "Stylized_Grass": ((0.30, 0.62, 0.24), 0.0, 0.85, 0.0),
    "Stylized_Road": ((0.22, 0.22, 0.25), 0.0, 0.8, 0.0),
    "Cartoon_Concrete": ((0.74, 0.72, 0.68), 0.0, 0.7, 0.0),
    "Cartoon_Wood": ((0.55, 0.35, 0.18), 0.0, 0.6, 0.0),
    "Cartoon_Glass": ((0.55, 0.75, 0.85), 0.0, 0.15, 0.0),
    "Stylized_Metal": ((0.6, 0.62, 0.66), 0.9, 0.35, 0.0),
    "Stylized_Roof": ((0.7, 0.28, 0.22), 0.0, 0.6, 0.0),
    "Stylized_Foliage": ((0.20, 0.50, 0.22), 0.0, 0.8, 0.0),
    "Stylized_Trunk": ((0.36, 0.24, 0.14), 0.0, 0.7, 0.0),
}

ARCHVIZ_LIB = {
    "Warm_Wood": ((0.45, 0.28, 0.15), 0.0, 0.45, 0.0),
    "Polished_Concrete": ((0.62, 0.62, 0.6), 0.0, 0.35, 0.0),
    "White_Plaster": ((0.92, 0.91, 0.88), 0.0, 0.7, 0.0),
    "Dark_Metal": ((0.08, 0.08, 0.09), 0.85, 0.35, 0.0),
    "Clear_Glass": ((0.7, 0.8, 0.85), 0.0, 0.05, 0.0),
    "Frosted_Glass": ((0.8, 0.85, 0.88), 0.0, 0.4, 0.0),
    "Marble": ((0.9, 0.89, 0.86), 0.0, 0.2, 0.0),
    "Fabric": ((0.5, 0.45, 0.4), 0.0, 0.9, 0.0),
    "Leather": ((0.25, 0.15, 0.1), 0.0, 0.5, 0.0),
    "Ceramic_Tile": ((0.85, 0.85, 0.83), 0.0, 0.25, 0.0),
}

PRODUCT_LIB = {
    "Studio_White": ((0.95, 0.95, 0.95), 0.0, 0.6, 0.0),
    "Matte_Black": ((0.03, 0.03, 0.03), 0.0, 0.7, 0.0),
    "Brushed_Metal": ((0.7, 0.71, 0.73), 0.9, 0.3, 0.0),
    "Soft_Plastic": ((0.2, 0.4, 0.8), 0.0, 0.4, 0.0),
    "Premium_Glass": ((0.8, 0.85, 0.9), 0.0, 0.03, 0.0),
    "Warm_Emissive": ((1.0, 0.7, 0.3), 0.0, 0.5, 3.0),
}

EMISSIVE_COLORS = {
    "blue": (0.1, 0.4, 1.0),
    "cyan": (0.1, 0.9, 1.0),
    "magenta": (1.0, 0.1, 0.7),
    "orange": (1.0, 0.5, 0.1),
}


def _build_lib(lib: dict) -> list[str]:
    created = []
    for name, (rgb, metallic, rough, emit) in lib.items():
        H.make_material(name, color=rgb, metallic=metallic, roughness=rough, emission_strength=emit)
        created.append(name)
    return created


def op_create_stylized_materials(params):
    return {"created_materials": _build_lib(STYLIZED_LIB)}


def op_create_archviz_materials(params):
    return {"created_materials": _build_lib(ARCHVIZ_LIB)}


def op_create_product_materials(params):
    return {"created_materials": _build_lib(PRODUCT_LIB)}


def op_create_emissive_materials(params):
    color = params.get("color", "blue")
    strength = float(params.get("strength", 5.0))
    rgb = EMISSIVE_COLORS.get(color, EMISSIVE_COLORS["blue"])
    name = f"Emissive_{color.title()}"
    H.make_material(name, color=rgb, roughness=0.3, emission_strength=strength, emission_color=rgb)
    return {"created_materials": [name]}


def op_create_material(params):
    name = params["name"]
    H.make_material(
        name,
        color=tuple(params.get("base_color", [0.6, 0.6, 0.6, 1.0])),
        metallic=float(params.get("metallic", 0.0)),
        roughness=float(params.get("roughness", 0.5)),
        emission_strength=float(params.get("emission_strength", 0.0)),
    )
    return {"created_materials": [name]}


def op_apply_material(params):
    obj = bpy.data.objects.get(params["object_name"])
    mat = bpy.data.materials.get(params["material_name"])
    if not obj:
        raise ValueError(f"Object '{params['object_name']}' not found.")
    if not mat:
        raise ValueError(f"Material '{params['material_name']}' not found.")
    H.assign_material(obj, mat)
    return {"object": obj.name, "material": mat.name}


def op_apply_style_preset(params):
    preset = params.get("preset", "stylized_cartoon")
    if preset in ("modern_villa", "luxury_apartment", "minimalist_interior", "office_interior", "retail_store"):
        _build_lib(ARCHVIZ_LIB)
        default = "White_Plaster"
    elif preset in ("product_render",):
        _build_lib(PRODUCT_LIB)
        default = "Studio_White"
    else:
        _build_lib(STYLIZED_LIB)
        default = "Cartoon_Concrete"
    mat = bpy.data.materials.get(default)
    skinned = 0
    for obj in H.all_mesh_objects():
        if not obj.data.materials:
            H.assign_material(obj, mat)
            skinned += 1
    return {"preset": preset, "objects_skinned": skinned}


def ensure_default_material(name="Default_Surface"):
    return H.make_material(name, color=(0.7, 0.7, 0.72), roughness=0.6)
