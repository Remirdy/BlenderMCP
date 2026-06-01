"""Export operations. All paths are confined to the workspace output tree."""
from __future__ import annotations

import os

import bpy

from . import helpers as H

OUTPUT_SUBDIRS = ("blends", "renders", "exports", "thumbnails")


def get_workspace_root() -> str:
    """Workspace root is configured on the add-on preferences; fall back to env/home."""
    root = None
    try:
        prefs = bpy.context.preferences.addons.get("remirdy_blender_studio")
        if prefs and prefs.preferences.workspace_path:
            root = bpy.path.abspath(prefs.preferences.workspace_path)
    except Exception:
        root = None
    if not root:
        root = os.environ.get("REMIRDY_WORKSPACE", os.path.join(os.path.expanduser("~"), "RemirdyWorkspace"))
    for sub in OUTPUT_SUBDIRS:
        os.makedirs(os.path.join(root, "outputs", sub), exist_ok=True)
    return root


def workspace_output(category: str, filename: str) -> str:
    if category not in OUTPUT_SUBDIRS:
        raise ValueError(f"Unknown output category '{category}'.")
    safe_name = os.path.basename(filename)  # prevent path traversal
    return os.path.join(get_workspace_root(), "outputs", category, safe_name)


def _select_for_export(selected_only: bool):
    if selected_only:
        return  # caller manages selection
    bpy.ops.object.select_all(action="SELECT")


def op_export_blend(params):
    path = workspace_output("blends", params.get("filename", "scene.blend"))
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    return {"export_path": path, "format": "blend"}


def op_export_glb(params):
    path = workspace_output("exports", params.get("filename", "scene.glb"))
    target = params.get("target", "generic")
    _select_for_export(params.get("selected_only", False))
    kwargs = dict(filepath=path, export_format="GLB",
                  use_selection=params.get("selected_only", False),
                  export_apply=True, export_yup=True)
    if target == "unity":
        kwargs["export_cameras"] = False
        kwargs["export_lights"] = False
    bpy.ops.export_scene.gltf(**kwargs)
    return {"export_path": path, "format": "glb", "target": target}


def op_export_fbx(params):
    path = workspace_output("exports", params.get("filename", "scene.fbx"))
    target = params.get("target", "generic")
    _select_for_export(params.get("selected_only", False))
    kwargs = dict(filepath=path, use_selection=params.get("selected_only", False),
                  apply_unit_scale=True, bake_space_transform=(target == "unreal"),
                  object_types={"MESH", "EMPTY"} if target in ("unity", "unreal") else {"MESH", "EMPTY", "CAMERA", "LIGHT", "ARMATURE"})
    bpy.ops.export_scene.fbx(**kwargs)
    return {"export_path": path, "format": "fbx", "target": target}


def op_export_obj(params):
    path = workspace_output("exports", params.get("filename", "scene.obj"))
    try:
        bpy.ops.wm.obj_export(filepath=path, export_selected_objects=False)
    except AttributeError:
        bpy.ops.export_scene.obj(filepath=path, use_selection=False)
    return {"export_path": path, "format": "obj"}


def op_generate_html_catalog(params):
    """Automatically scans the workspace outputs and generates a premium responsive HTML catalog gallery."""
    root = get_workspace_root()
    export_dir = os.path.join(root, "outputs", "exports")
    render_dir = os.path.join(root, "outputs", "renders")

    exports = os.listdir(export_dir) if os.path.exists(export_dir) else []
    renders = os.listdir(render_dir) if os.path.exists(render_dir) else []

    html_path = os.path.join(root, "index.html")

    cards_html = ""
    for f in exports:
        stem = os.path.splitext(f)[0]
        # Match with preview render if available
        preview = next((r for r in renders if stem in r), "")
        preview_src = f"outputs/renders/{preview}" if preview else "https://placehold.co/360x270/2a2a2a/f5f5f5?text=3D+Model"

        cards_html += f"""
        <div class="card">
            <img src="{preview_src}" alt="{stem}" class="card-img" />
            <div class="card-body">
                <h3>{stem}</h3>
                <p class="meta">Format: {os.path.splitext(f)[1].upper()} | Size: {round(os.path.getsize(os.path.join(export_dir, f)) / (1024*1024), 2)} MB</p>
                <div class="actions">
                    <a href="outputs/exports/{f}" download class="btn">Download Model</a>
                </div>
            </div>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Remirdy Asset Portfolio Catalog</title>
    <style>
        body {{
            background: #121214;
            color: #f3f4f6;
            font-family: 'Outfit', 'Inter', sans-serif;
            margin: 0;
            padding: 40px;
        }}
        h1 {{
            background: linear-gradient(135deg, #00f0ff, #ff007f);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.8rem;
            margin-bottom: 8px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 30px;
            margin-top: 40px;
        }}
        .card {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            overflow: hidden;
            transition: all 0.3s ease;
        }}
        .card:hover {{
            transform: translateY(-8px);
            border-color: #00f0ff;
            box-shadow: 0 10px 20px rgba(0, 240, 255, 0.1);
        }}
        .card-img {{
            width: 100%;
            height: 220px;
            object-fit: cover;
            background: #1a1a1c;
        }}
        .card-body {{
            padding: 20px;
        }}
        .card-body h3 {{
            margin: 0 0 8px 0;
            color: #ffffff;
        }}
        .meta {{
            font-size: 0.85rem;
            color: #9ca3af;
            margin: 0 0 20px 0;
        }}
        .btn {{
            display: inline-block;
            background: linear-gradient(135deg, #00c6ff, #0072ff);
            color: #ffffff;
            text-decoration: none;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: 600;
            transition: opacity 0.2s;
        }}
        .btn:hover {{
            opacity: 0.9;
        }}
    </style>
</head>
<body>
    <h1>Remirdy Asset Portfolio</h1>
    <p>Procedural & AI-generated Blender game asset catalogs</p>
    <div class="grid">
        {cards_html or '<p>No exported assets found in workspace outputs yet.</p>'}
    </div>
</body>
</html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return {"ok": True, "catalog_path": html_path, "total_cards": len(exports)}
