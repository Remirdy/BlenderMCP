"""Marketplace packaging: folder tree, manifest, README, license, catalog."""
from __future__ import annotations

import datetime
import json
import os

import bpy

from . import asset_ops
from . import export_ops
from . import helpers as H

PACK_SUBDIRS = (
    "source", "exports/glb", "exports/fbx", "exports/obj",
    "textures", "renders", "thumbnails", "documentation",
)


def pack_root(pack_name: str) -> str:
    safe = os.path.basename(pack_name)
    root = os.path.join(export_ops.get_workspace_root(), "outputs", "asset_packs", safe)
    for sub in PACK_SUBDIRS:
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    return root


def pack_dir(pack_name: str, sub: str) -> str:
    mapping = {
        "source": "source", "glb": "exports/glb", "fbx": "exports/fbx", "obj": "exports/obj",
        "textures": "textures", "renders": "renders", "thumbnails": "thumbnails",
        "documentation": "documentation", "docs": "documentation",
    }
    return os.path.join(pack_root(pack_name), mapping.get(sub, sub))


def _select_collection(coll_name):
    bpy.ops.object.select_all(action="DESELECT")
    coll = bpy.data.collections.get(coll_name)
    n = 0
    if coll:
        for o in coll.objects:
            o.select_set(True)
            n += 1
            bpy.context.view_layer.objects.active = o
    return n


def op_generate_asset_manifest(params):
    pack = asset_ops.LAST_PACK
    if not pack:
        raise ValueError("No asset pack in memory.")
    root = pack_root(pack["name"])
    manifest = {
        "pack_name": pack["name"],
        "theme": pack["theme"],
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "generator": "Remirdy Blender Studio MCP",
        "originality": "All assets are original procedural designs. No third-party/branded content.",
        "asset_count": len(pack["assets"]),
        "materials": pack.get("materials", []),
        "total_polygons": sum(a["polycount"] for a in pack["assets"]),
        "assets": [
            {
                "name": a["name"],
                "category": a["category"],
                "polycount_estimate": a["polycount"],
                "materials": a["materials"],
                "thumbnail": os.path.relpath(a["thumbnail"], root) if a.get("thumbnail") else None,
                "suggested_usage": _usage_hint(a["category"]),
                "notes": "Game-ready: clean pivot, applied transforms, single material slot group.",
            }
            for a in pack["assets"]
        ],
    }
    path = os.path.join(root, "documentation", "asset_manifest.json")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    return {"manifest_path": path, "asset_count": manifest["asset_count"]}


def _usage_hint(category: str) -> str:
    hints = {
        "House": "Background or playable building for low-poly towns.",
        "Car": "Street dressing / traffic prop.",
        "Tree": "Environment scatter.",
        "Sofa": "Hero furniture for living-room archviz.",
        "Crate": "Stackable gameplay prop / loot container.",
        "Lantern": "Atmospheric light prop.",
    }
    return hints.get(category, f"Decoration / environment prop ({category}).")


def op_generate_pack_readme(params):
    pack = asset_ops.LAST_PACK
    root = pack_root(pack["name"])
    title = pack["name"].replace("_", " ")
    cats = sorted({a["category"] for a in pack["assets"]})
    lines = [
        f"# {title}",
        "",
        f"An original **{pack['theme'].replace('_', ' ')}** asset pack generated with Remirdy Blender Studio MCP.",
        "",
        "## Contents",
        f"- {len(pack['assets'])} game/render-ready assets",
        f"- Categories: {', '.join(cats)}",
        f"- {len(pack.get('materials', []))} shared materials",
        f"- ~{sum(a['polycount'] for a in pack['assets'])} total polygons",
        "",
        "## Folder structure",
        "```",
        "source/        Blender source (.blend)",
        "exports/glb    glTF Binary (Unity-ready)",
        "exports/fbx    FBX (Unreal-ready)",
        "exports/obj    Wavefront OBJ",
        "renders/       hero + preview renders",
        "thumbnails/    per-asset thumbnails",
        "documentation/ manifest, usage guide, license",
        "```",
        "",
        "## Standards",
        "Every asset has a clean name, correct bottom-center pivot, applied transforms,",
        "assigned materials and collection organization. Optimized for real-time engines.",
        "",
        "## Originality",
        "All designs are original procedural compositions inspired only by broad generic",
        "categories. No copyrighted asset pack, brand, artist or marketplace listing is copied.",
        "",
        "## License",
        "See documentation/license.txt.",
    ]
    path = os.path.join(root, "documentation", "README.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return {"readme_path": path}


def op_generate_usage_guide(params):
    pack = asset_ops.LAST_PACK
    root = pack_root(pack["name"])
    lines = [
        f"# Usage Guide — {pack['name'].replace('_', ' ')}",
        "",
        "## Unity",
        "1. Import `exports/glb/*.glb` (or the combined pack GLB) into your project.",
        "2. Models use meters scale with applied transforms; drop straight into a scene.",
        "3. Materials import as readable named materials; swap to URP/HDRP shaders as needed.",
        "",
        "## Unreal",
        "1. Import `exports/fbx/*.fbx` as Static Meshes (scale 1.0).",
        "2. Pivots are bottom-center for easy snapping to the floor.",
        "",
        "## Blender",
        "Open `source/*.blend` to edit originals. Each asset is one object in the pack collection.",
        "",
        "## Tips",
        "- Use the thumbnails/ sheet to browse the pack.",
        "- Re-run `score_asset_pack_quality` after edits to keep it marketplace-ready.",
    ]
    path = os.path.join(root, "documentation", "usage_guide.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return {"usage_guide_path": path}


def op_generate_license_template(params):
    pack = asset_ops.LAST_PACK
    root = pack_root(pack["name"])
    year = datetime.date.today().year
    holder = params.get("holder", "the pack author")
    text = (
        f"Remirdy Asset Pack License (template)\n"
        f"Copyright (c) {year} {holder}\n\n"
        "These assets are original works generated procedurally. You may use them in\n"
        "personal and commercial projects (games, renders, visualizations). You may not\n"
        "resell or redistribute the assets as a standalone asset pack.\n\n"
        "Provided 'as is' without warranty of any kind.\n"
        "Replace this template with your chosen license before distribution.\n"
    )
    path = os.path.join(root, "documentation", "license.txt")
    with open(path, "w") as f:
        f.write(text)
    return {"license_path": path}


def op_create_asset_catalog(params):
    """An HTML catalog that embeds thumbnails for quick browsing."""
    pack = asset_ops.LAST_PACK
    root = pack_root(pack["name"])
    cards = []
    for a in pack["assets"]:
        thumb = os.path.relpath(a["thumbnail"], root) if a.get("thumbnail") else ""
        img = f'<img src="{thumb}" alt="{a["name"]}">' if thumb else '<div class="noimg">no thumb</div>'
        cards.append(
            f'<div class="card">{img}<div class="meta"><b>{a["name"]}</b>'
            f'<span>{a["category"]} · {a["polycount"]} polys</span></div></div>'
        )
    html = (
        "<!doctype html><meta charset='utf-8'><title>" + pack["name"] + "</title>"
        "<style>body{font-family:system-ui;background:#111;color:#eee;margin:24px}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:16px}"
        ".card{background:#1c1c1f;border-radius:10px;overflow:hidden}"
        ".card img{width:100%;display:block;background:#222}"
        ".meta{padding:8px 10px;display:flex;flex-direction:column}"
        ".meta span{color:#9aa;font-size:12px}.noimg{height:160px;display:grid;place-items:center;color:#666}"
        "</style>"
        f"<h1>{pack['name'].replace('_',' ')}</h1>"
        f"<p>{len(pack['assets'])} assets · {pack['theme'].replace('_',' ')}</p>"
        "<div class='grid'>" + "".join(cards) + "</div>"
    )
    path = os.path.join(root, "documentation", "catalog.html")
    with open(path, "w") as f:
        f.write(html)
    return {"catalog_path": path}


def op_generate_thumbnail_sheet(params):
    """Render a single contact sheet of the whole pack."""
    res = asset_ops.op_create_preview_grid({"width": 1600, "height": 1000})
    return {"thumbnail_sheet": res["render_path"]}


def op_package_asset_for_marketplace(params):
    """Full marketplace packaging: exports + renders + thumbnails + docs."""
    pack = asset_ops.LAST_PACK
    if not pack:
        raise ValueError("No asset pack in memory. Run create_asset_pack first.")
    name = pack["name"]
    root = pack_root(name)
    steps = {}

    # 1. source blend
    blend_path = os.path.join(root, "source", f"{name}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, copy=True)
    steps["source_blend"] = blend_path

    # 2. combined exports of the asset collection
    _select_collection(pack["assets_collection"])
    glb = os.path.join(root, "exports", "glb", f"{name}.glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True,
                              export_apply=True, export_yup=True,
                              export_cameras=False, export_lights=False)
    steps["glb"] = glb
    if params.get("fbx", True):
        _select_collection(pack["assets_collection"])
        fbx = os.path.join(root, "exports", "fbx", f"{name}.fbx")
        bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, apply_unit_scale=True,
                                 object_types={"MESH", "EMPTY"})
        steps["fbx"] = fbx

    # 3. thumbnails (if not already rendered) + grid
    if params.get("render_thumbnails", True):
        asset_ops.op_create_asset_pack_thumbnails({"size": params.get("thumb_size", 512)})
    grid = asset_ops.op_create_preview_grid({})
    steps["preview_grid"] = grid["render_path"]
    # rename grid to hero
    hero = os.path.join(root, "renders", "hero_render.png")
    try:
        if os.path.exists(grid["render_path"]) and grid["render_path"] != hero:
            import shutil
            shutil.copyfile(grid["render_path"], hero)
            steps["hero_render"] = hero
    except Exception:
        pass

    # 4. documentation
    steps["manifest"] = op_generate_asset_manifest({})["manifest_path"]
    steps["readme"] = op_generate_pack_readme({})["readme_path"]
    steps["usage_guide"] = op_generate_usage_guide({})["usage_guide_path"]
    steps["license"] = op_generate_license_template(params)["license_path"]
    steps["catalog"] = op_create_asset_catalog({})["catalog_path"]

    return {"pack_root": root, "package": steps,
            "message": f"Marketplace package created for '{name}' at {root}."}


def op_generate_preview_renders(params):
    from . import render_ops as R
    import os
    pack = asset_ops.LAST_PACK
    root = pack_root(pack["name"])
    R.op_setup_three_point_lighting({})
    R.op_apply_render_preset({"preset": "portfolio_render"})
    paths = []
    for i, ang in enumerate(((1.6, -1.8, 1.1), (-1.8, -1.6, 1.0)), start=1):
        cam = R._ensure_camera()
        from mathutils import Vector
        center, radius = R._scene_bounds()
        cam.location = center + Vector((radius * ang[0], radius * ang[1], radius * ang[2]))
        R._point_at(cam, center)
        fp = os.path.join(root, "renders", f"preview_{i:02d}.png")
        R._render_to(fp, 1280, 800)
        paths.append(fp)
    return {"renders": paths}
