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
