"""Asset pack generation engine.

Builds complete, consistent, game/render-ready prop packs from generic themes,
organizes them, and tracks a manifest used by thumbnails, scoring and packaging.
All designs are original procedural compositions.
"""
from __future__ import annotations

import math

import bpy

from . import helpers as H
from . import prop_library as P
from . import render_ops as R

# --------------------------------------------------------------------------- #
# Palettes  (name -> (rgb, metallic, roughness, emission))
# --------------------------------------------------------------------------- #
PALETTES = {
    "medieval": {
        "wood": ((0.42, 0.27, 0.14), 0.0, 0.6),
        "metal": ((0.35, 0.36, 0.38), 0.8, 0.4),
        "fabric": ((0.6, 0.2, 0.18), 0.0, 0.9),
        "glass": ((0.7, 0.8, 0.85), 0.0, 0.1),
        "emissive": ((1.0, 0.7, 0.3), 0.0, 0.4, 4.0),
        "ceramic": ((0.85, 0.82, 0.76), 0.0, 0.3),
        "leaf": ((0.22, 0.5, 0.24), 0.0, 0.8),
        "trunk": ((0.36, 0.24, 0.14), 0.0, 0.7),
    },
    "low_poly_city": {
        "plaster": ((0.85, 0.82, 0.78), 0.0, 0.7),
        "concrete": ((0.6, 0.6, 0.62), 0.0, 0.6),
        "roof": ((0.7, 0.3, 0.25), 0.0, 0.6),
        "glass": ((0.5, 0.7, 0.85), 0.0, 0.15),
        "paint": ((0.2, 0.5, 0.8), 0.3, 0.4),
        "metal": ((0.4, 0.42, 0.45), 0.8, 0.4),
        "dark": ((0.1, 0.1, 0.11), 0.0, 0.6),
        "road": ((0.22, 0.22, 0.24), 0.0, 0.8),
        "fabric": ((0.8, 0.5, 0.2), 0.0, 0.9),
        "leaf": ((0.25, 0.55, 0.25), 0.0, 0.8),
        "trunk": ((0.36, 0.24, 0.14), 0.0, 0.7),
        "wood": ((0.45, 0.3, 0.16), 0.0, 0.6),
        "emissive": ((1.0, 0.8, 0.4), 0.0, 0.4, 4.0),
    },
    "cafe": {
        "wood": ((0.5, 0.33, 0.18), 0.0, 0.5),
        "metal": ((0.45, 0.46, 0.48), 0.85, 0.35),
        "dark": ((0.12, 0.12, 0.13), 0.0, 0.6),
        "glass": ((0.7, 0.8, 0.85), 0.0, 0.08),
        "ceramic": ((0.92, 0.9, 0.86), 0.0, 0.25),
        "marble": ((0.9, 0.89, 0.86), 0.0, 0.2),
        "white": ((0.95, 0.95, 0.95), 0.0, 0.5),
        "fabric": ((0.55, 0.4, 0.3), 0.0, 0.85),
        "leaf": ((0.2, 0.5, 0.25), 0.0, 0.8),
        "emissive": ((1.0, 0.85, 0.5), 0.0, 0.4, 3.0),
    },
    "modern_interior": {
        "wood": ((0.48, 0.32, 0.18), 0.0, 0.4),
        "fabric": ((0.55, 0.55, 0.58), 0.0, 0.9),
        "leather": ((0.25, 0.16, 0.12), 0.0, 0.5),
        "metal": ((0.6, 0.61, 0.64), 0.9, 0.3),
        "dark": ((0.08, 0.08, 0.09), 0.0, 0.6),
        "marble": ((0.9, 0.89, 0.86), 0.0, 0.18),
        "glass": ((0.8, 0.85, 0.9), 0.0, 0.05),
        "ceramic": ((0.88, 0.86, 0.82), 0.0, 0.3),
        "leaf": ((0.2, 0.5, 0.25), 0.0, 0.8),
    },
}

# --------------------------------------------------------------------------- #
# Catalogs  (theme -> ordered list of (builder, base_name))
# --------------------------------------------------------------------------- #
CATALOGS = {
    "medieval_market": ("medieval", [
        (P.crate, "Crate"), (P.barrel, "Barrel"), (P.market_stand, "MarketStand"),
        (P.sign, "Sign"), (P.lantern, "Lantern"), (P.rug, "Rug"), (P.basket, "Basket"),
        (P.table, "Table"), (P.chair, "Chair"), (P.cart, "Cart"), (P.bench, "Bench"),
        (P.potted_plant, "Plant"), (P.shelf, "Shelf"), (P.lamp_post, "LampPost"),
    ]),
    "low_poly_city": ("low_poly_city", [
        (P.house, "House"), (P.shop, "Shop"), (P.car, "Car"), (P.tree_prop, "Tree"),
        (P.lamp_post, "Lamp"), (P.bench, "Bench"), (P.sign, "Sign"), (P.fence, "Fence"),
        (P.road_tile, "Road"), (P.potted_plant, "Planter"),
    ]),
    "cozy_cafe": ("cafe", [
        (P.table, "Table"), (P.chair, "Chair"), (P.counter, "Counter"),
        (P.menu_board, "MenuBoard"), (P.coffee_cup, "CoffeeCup"), (P.potted_plant, "Plant"),
        (P.shelf, "Shelf"), (P.pastry_display, "PastryDisplay"), (P.lamp_post, "Lamp"),
        (P.sign, "Sign"),
    ]),
    "modern_living_room": ("modern_interior", [
        (P.sofa, "Sofa"), (P.armchair, "Armchair"), (P.coffee_table, "CoffeeTable"),
        (P.tv_wall, "TVWall"), (P.shelf, "Shelf"), (P.potted_plant, "Plant"),
        (P.floor_lamp, "FloorLamp"), (P.carpet, "Carpet"), (P.cabinet, "Cabinet"),
    ]),
}

THEME_ALIASES = {
    "medieval": "medieval_market", "market": "medieval_market", "village": "medieval_market",
    "city": "low_poly_city", "low_poly": "low_poly_city", "mobile": "low_poly_city",
    "cafe": "cozy_cafe", "coffee": "cozy_cafe",
    "living_room": "modern_living_room", "interior": "modern_living_room", "furniture": "modern_living_room",
}

# Tracks the most recent pack for thumbnails/scoring/packaging.
LAST_PACK: dict = {}


def _build_palette(style: str) -> dict:
    out = {}
    spec = PALETTES.get(style, PALETTES["medieval"])
    for key, vals in spec.items():
        rgb = vals[0]
        metallic = vals[1]
        rough = vals[2]
        emit = vals[3] if len(vals) > 3 else 0.0
        out[key] = H.make_material(f"{style.title()}_{key.title()}", color=rgb, metallic=metallic, roughness=rough, emission_strength=emit)
    return out


def resolve_theme(theme: str) -> str:
    t = (theme or "").lower().replace(" ", "_")
    if t in CATALOGS:
        return t
    for k, v in THEME_ALIASES.items():
        if k in t:
            return v
    return "medieval_market"


def op_create_asset_pack(params):
    theme = resolve_theme(params.get("theme", "medieval_market"))
    count = int(params.get("count", 20))
    pack_name = params.get("name") or theme.replace("_", " ").title().replace(" ", "_") + "_Pack"
    style, catalog = CATALOGS[theme]
    mats = _build_palette(style)

    pack_coll = H.get_or_create_collection(pack_name)
    assets_coll = H.get_or_create_collection(f"{pack_name}_Assets")
    if assets_coll.name not in [c.name for c in pack_coll.children]:
        try:
            bpy.context.scene.collection.children.unlink(assets_coll)
        except Exception:
            pass
        if assets_coll.name not in [c.name for c in pack_coll.children]:
            pack_coll.children.link(assets_coll)

    manifest = []
    cols = max(1, int(math.ceil(math.sqrt(count))))
    spacing = 3.0
    counters: dict[str, int] = {}
    for i in range(count):
        builder, base = catalog[i % len(catalog)]
        counters[base] = counters.get(base, 0) + 1
        name = f"{base}_{counters[base]:02d}"
        gx = (i % cols) * spacing - (cols - 1) * spacing / 2
        gy = (i // cols) * spacing
        obj = builder(name, (gx, gy, 0.0), mats, assets_coll)
        if obj is None:
            continue
        manifest.append({
            "name": obj.name,
            "category": base,
            "polycount": H.poly_count(obj),
            "materials": [m.name for m in obj.data.materials if m],
            "location": [round(c, 2) for c in obj.location],
        })

    LAST_PACK.clear()
    LAST_PACK.update({
        "name": pack_name, "theme": theme, "style": style,
        "assets": manifest, "materials": sorted({m for a in manifest for m in a["materials"]}),
        "collection": pack_coll.name, "assets_collection": assets_coll.name,
    })
    return {
        "pack_name": pack_name, "theme": theme, "asset_count": len(manifest),
        "materials": LAST_PACK["materials"], "total_polygons": sum(a["polycount"] for a in manifest),
        "assets": [a["name"] for a in manifest], "collection": pack_coll.name,
        "suggested_next": ["create_asset_pack_thumbnails", "score_asset_pack_quality", "package_asset_for_marketplace"],
    }


def op_generate_asset_variations(params):
    """Create scale/tint variations of existing pack assets."""
    base_name = params.get("asset_name")
    variants = int(params.get("variants", 2))
    targets = []
    if base_name and base_name in bpy.data.objects:
        targets = [bpy.data.objects[base_name]]
    else:
        targets = [bpy.data.objects[a["name"]] for a in LAST_PACK.get("assets", []) if a["name"] in bpy.data.objects][:5]
    assets_coll = H.get_or_create_collection(LAST_PACK.get("assets_collection", "Variations"))
    created = []
    for obj in targets:
        for v in range(1, variants + 1):
            dup = obj.copy()
            dup.data = obj.data.copy()
            dup.name = f"{obj.name}_var{v}"
            assets_coll.objects.link(dup)
            scale_f = 1.0 + 0.12 * v
            dup.scale = tuple(s * scale_f for s in obj.scale)
            dup.location = (obj.location.x, obj.location.y + 3.0 * v, obj.location.z)
            created.append(dup.name)
    return {"created": created, "variants_per_asset": variants}


def _isolate_render(obj, filepath, size=512):
    H.hide_all_except([obj])
    scene = bpy.context.scene
    cam = next((o for o in scene.objects if o.type == "CAMERA"), None)
    if cam is None:
        R.op_setup_camera({})
        cam = scene.camera
    # frame this object
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.view3d.camera_to_view_selected()
    except Exception:
        pass
    prev = scene.render.film_transparent
    scene.render.film_transparent = True
    R._render_to(filepath, size, size)
    scene.render.film_transparent = prev
    H.show_all()
    return filepath


def op_create_asset_pack_thumbnails(params):
    from .packaging_ops import pack_dir
    pack = LAST_PACK
    if not pack.get("assets"):
        raise ValueError("No asset pack in memory. Run create_asset_pack first.")
    R.op_setup_three_point_lighting({"strength": 1.0})
    R.op_apply_render_preset({"preset": "fast_preview"})
    thumbs_dir = pack_dir(pack["name"], "thumbnails")
    size = int(params.get("size", 512))
    limit = int(params.get("limit", len(pack["assets"])))
    paths = []
    import os
    for a in pack["assets"][:limit]:
        obj = bpy.data.objects.get(a["name"])
        if not obj:
            continue
        fp = os.path.join(thumbs_dir, f"{a['name']}.png")
        _isolate_render(obj, fp, size)
        paths.append(fp)
        a["thumbnail"] = fp
    return {"thumbnails": paths, "count": len(paths), "directory": thumbs_dir}


def op_create_game_prop_pack(params):
    p = dict(params)
    p.setdefault("theme", "medieval_market")
    return op_create_asset_pack(p)


def op_create_stylized_prop_set(params):
    p = dict(params)
    p.setdefault("theme", params.get("theme", "cozy_cafe"))
    return op_create_asset_pack(p)


def op_create_low_poly_asset_pack(params):
    p = dict(params)
    p["theme"] = "low_poly_city"
    return op_create_asset_pack(p)


def op_create_mobile_game_asset_pack(params):
    p = dict(params)
    p["theme"] = "low_poly_city"
    p.setdefault("count", 30)
    return op_create_asset_pack(p)


def op_create_interior_asset_pack(params):
    p = dict(params)
    p["theme"] = "modern_living_room"
    return op_create_asset_pack(p)


def op_export_asset_pack_for_unity(params):
    from . import packaging_ops, export_ops
    pack = LAST_PACK
    if not pack:
        raise ValueError("No asset pack in memory.")
    import os
    root = packaging_ops.pack_root(pack["name"])
    packaging_ops._select_collection(pack["assets_collection"])
    glb = os.path.join(root, "exports", "glb", f"{pack['name']}.glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True,
                              export_apply=True, export_yup=True, export_cameras=False, export_lights=False)
    return {"export_path": glb, "target": "unity", "format": "glb"}


def op_export_asset_pack_for_unreal(params):
    from . import packaging_ops
    import os
    pack = LAST_PACK
    if not pack:
        raise ValueError("No asset pack in memory.")
    root = packaging_ops.pack_root(pack["name"])
    packaging_ops._select_collection(pack["assets_collection"])
    fbx = os.path.join(root, "exports", "fbx", f"{pack['name']}.fbx")
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, apply_unit_scale=True,
                             bake_space_transform=True, object_types={"MESH", "EMPTY"})
    return {"export_path": fbx, "target": "unreal", "format": "fbx"}


def op_create_preview_grid(params):
    """Render the whole pack laid out in its grid from an isometric angle."""
    from .packaging_ops import pack_dir
    import os
    R.op_setup_isometric_camera({})
    R.op_setup_lighting({"style": "bright"})
    R.op_apply_render_preset({"preset": "portfolio_render"})
    fp = os.path.join(pack_dir(LAST_PACK.get("name", "Pack"), "renders"), "preview_grid.png")
    R._render_to(fp, int(params.get("width", 1600)), int(params.get("height", 1000)))
    return {"render_path": fp}
