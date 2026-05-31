"""Product render asset creator: original premium product models + studio stage."""
from __future__ import annotations

import math

import bpy

from . import asset_ops
from . import helpers as H
from . import material_ops as M
from . import render_ops as R

LAST_PRODUCT: dict = {}


def _product_mats():
    M.op_create_product_materials({})
    return {n: bpy.data.materials[n] for n in (
        "Studio_White", "Matte_Black", "Brushed_Metal", "Soft_Plastic", "Premium_Glass", "Warm_Emissive")}


def _headphones(name, mats, coll):
    metal, plastic, dark = mats["Brushed_Metal"], mats["Soft_Plastic"], mats["Matte_Black"]
    band = H.add_cylinder(f"{name}_band", radius=0.5, depth=0.06, location=(0, 0, 0.5), verts=24, mat=metal, collection=coll)
    band.rotation_euler = (math.radians(90), 0, 0)
    parts = [band]
    for dx in (-1, 1):
        cup = H.add_cylinder(f"{name}_cup", radius=0.18, depth=0.12, location=(dx * 0.5, 0, 0.1), verts=20, mat=dark, collection=coll)
        cup.rotation_euler = (0, math.radians(90), 0)
        parts.append(cup)
    return H.join_objects(name, parts, coll, dark)


def _smartwatch(name, mats, coll):
    metal, glass, dark = mats["Brushed_Metal"], mats["Premium_Glass"], mats["Matte_Black"]
    body = H.add_box(f"{name}_body", size=(0.3, 0.36, 0.08), location=(0, 0, 0.04), mat=metal, collection=coll)
    screen = H.add_box(f"{name}_screen", size=(0.26, 0.32, 0.02), location=(0, 0, 0.09), mat=glass, collection=coll)
    band1 = H.add_box(f"{name}_band", size=(0.22, 0.5, 0.03), location=(0, 0, 0.02), mat=dark, collection=coll)
    return H.join_objects(name, [body, screen, band1], coll, metal)


def _speaker(name, mats, coll):
    plastic, metal = mats["Soft_Plastic"], mats["Brushed_Metal"]
    body = H.add_cylinder(f"{name}_body", radius=0.25, depth=0.6, location=(0, 0, 0), verts=28, mat=plastic, collection=coll)
    top = H.add_cylinder(f"{name}_top", radius=0.24, depth=0.04, location=(0, 0, 0.6), verts=28, mat=metal, collection=coll)
    return H.join_objects(name, [body, top], coll, plastic)


def _perfume(name, mats, coll):
    glass, metal = mats["Premium_Glass"], mats["Brushed_Metal"]
    body = H.add_box(f"{name}_body", size=(0.24, 0.24, 0.5), location=(0, 0, 0), mat=glass, collection=coll)
    neck = H.add_cylinder(f"{name}_neck", radius=0.05, depth=0.08, location=(0, 0, 0.5), verts=16, mat=metal, collection=coll)
    cap = H.add_box(f"{name}_cap", size=(0.12, 0.12, 0.16), location=(0, 0, 0.58), mat=metal, collection=coll)
    return H.join_objects(name, [body, neck, cap], coll, glass)


def _packaging_box(name, mats, coll):
    white = mats["Studio_White"]
    box = H.add_box(f"{name}_box", size=(0.5, 0.35, 0.6), location=(0, 0, 0), mat=white, collection=coll)
    return H.join_objects(name, [box], coll, white)


def _device(name, mats, coll):
    metal, glass = mats["Brushed_Metal"], mats["Premium_Glass"]
    body = H.add_box(f"{name}_body", size=(0.5, 0.25, 1.0), location=(0, 0, 0), mat=metal, collection=coll)
    screen = H.add_box(f"{name}_screen", size=(0.42, 0.02, 0.85), location=(0, -0.14, 0.5), mat=glass, collection=coll)
    return H.join_objects(name, [body, screen], coll, metal)


PRODUCTS = {
    "device": _device, "headphones": _headphones, "smartwatch": _smartwatch,
    "speaker": _speaker, "perfume": _perfume, "perfume_bottle": _perfume,
    "cosmetic": _perfume, "packaging": _packaging_box, "packaging_box": _packaging_box,
}


def op_setup_product_render_stage(params):
    mats = _product_mats()
    bg = params.get("background", "white")
    env = H.get_or_create_collection("ProductStage")
    bg_mat = {"white": mats["Studio_White"], "gray": H.make_material("Studio_Gray", color=(0.5, 0.5, 0.52), roughness=0.6),
              "black": mats["Matte_Black"]}.get(bg, mats["Studio_White"])
    H.add_plane("Stage_Floor", size=(20, 20), mat=bg_mat, collection=env)
    H.add_box("Stage_Backdrop", size=(20, 0.1, 12), location=(0, 5, 0), mat=bg_mat, collection=env)
    R.op_setup_product_camera({"focal_length": 85, "depth_of_field": params.get("depth_of_field", True)})
    R.op_setup_three_point_lighting({"strength": 1.3})
    R.op_apply_render_preset({"preset": "product_render"})
    if bg == "transparent":
        bpy.context.scene.render.film_transparent = True
    return {"stage": "ready", "background": bg}


def op_create_product_asset(params):
    ptype = params.get("product", "device").lower().replace(" ", "_")
    builder = PRODUCTS.get(ptype, _device)
    mats = _product_mats()
    props = H.get_or_create_collection("ProductAssets")
    name = params.get("name", ptype.title())
    obj = builder(name, mats, props)
    LAST_PRODUCT.clear()
    LAST_PRODUCT.update({"name": obj.name, "type": ptype, "polycount": H.poly_count(obj)})
    if params.get("setup_stage", True):
        op_setup_product_render_stage({"background": params.get("background", "white"),
                                       "depth_of_field": params.get("depth_of_field", True)})
    # register as a single-asset pack for packaging/scoring reuse
    asset_ops.LAST_PACK.clear()
    asset_ops.LAST_PACK.update({
        "name": f"{name}_Product", "theme": f"product_{ptype}", "style": "modern_interior",
        "assets": [{"name": obj.name, "category": "Product", "polycount": H.poly_count(obj),
                    "materials": [m.name for m in obj.data.materials if m]}],
        "materials": [m.name for m in obj.data.materials if m],
        "collection": props.name, "assets_collection": props.name,
    })
    return {"created": obj.name, "type": ptype, "polycount": H.poly_count(obj),
            "suggested_next": ["render_product_thumbnail", "render_product_turntable", "export_product_model"]}


def op_create_product_variations(params):
    return asset_ops.op_generate_asset_variations({"asset_name": LAST_PRODUCT.get("name"), "variants": params.get("variants", 3)})


def op_create_packaging_mockup(params):
    mats = _product_mats()
    props = H.get_or_create_collection("ProductAssets")
    obj = _packaging_box(params.get("name", "Packaging"), mats, props)
    return {"created": obj.name}


def op_render_product_thumbnail(params):
    from .packaging_ops import pack_dir
    import os
    pack = asset_ops.LAST_PACK
    name = LAST_PRODUCT.get("name", "Product")
    fp = os.path.join(pack_dir(pack.get("name", f"{name}_Product"), "thumbnails"), f"{name}.png")
    prev = bpy.context.scene.render.film_transparent
    bpy.context.scene.render.film_transparent = params.get("transparent", True)
    R._render_to(fp, int(params.get("size", 1024)), int(params.get("size", 1024)))
    bpy.context.scene.render.film_transparent = prev
    return {"thumbnail": fp}


def op_render_product_turntable(params):
    return R.op_export_turntable_animation({"filename": f"{LAST_PRODUCT.get('name','product')}_turntable.mp4",
                                            "frames": params.get("frames", 48)})


def op_export_product_model(params):
    from . import export_ops
    name = LAST_PRODUCT.get("name", "product")
    fmt = params.get("format", "glb")
    if fmt == "fbx":
        return export_ops.op_export_fbx({"filename": f"{name}.fbx", "target": params.get("target", "generic")})
    return export_ops.op_export_glb({"filename": f"{name}.glb", "target": params.get("target", "generic")})
