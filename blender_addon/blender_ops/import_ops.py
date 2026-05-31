"""Safe import operations for downloaded/generated assets."""
from __future__ import annotations

import os
from pathlib import Path

import bpy

from . import helpers as H
from .export_ops import get_workspace_root


ALLOWED_EXTENSIONS = {".glb", ".gltf", ".obj", ".fbx", ".blend"}


def _inside_workspace(path: str) -> str:
    root = Path(get_workspace_root()).resolve()
    candidate = Path(path).expanduser().resolve()
    if root not in candidate.parents and candidate != root:
        raise ValueError("Import path must be inside the Remirdy workspace.")
    if candidate.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported import extension: {candidate.suffix}")
    if not candidate.exists():
        raise ValueError(f"Import path does not exist: {candidate}")
    return str(candidate)


def op_import_asset_file(params):
    path = _inside_workspace(params["path"])
    name = params.get("collection", "ImportedAssets")
    before = set(bpy.context.scene.objects)
    ext = Path(path).suffix.lower()
    if ext in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        try:
            bpy.ops.wm.obj_import(filepath=path)
        except AttributeError:
            bpy.ops.import_scene.obj(filepath=path)
    elif ext == ".blend":
        with bpy.data.libraries.load(path, link=False) as (data_from, data_to):
            data_to.objects = data_from.objects
        for obj in data_to.objects:
            if obj:
                bpy.context.collection.objects.link(obj)
    new_objects = [obj for obj in bpy.context.scene.objects if obj not in before]
    coll = H.get_or_create_collection(name)
    for obj in new_objects:
        H.link_to_collection(obj, coll)
        obj["remirdy_source_path"] = os.path.basename(path)
    return {"imported": [o.name for o in new_objects], "count": len(new_objects), "path": path}


def op_set_hdri_environment(params):
    path = _inside_workspace(params["path"])
    if Path(path).suffix.lower() not in {".hdr", ".exr"}:
        raise ValueError("HDRI environment path must be .hdr or .exr")
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    output = nodes.new(type="ShaderNodeOutputWorld")
    bg = nodes.new(type="ShaderNodeBackground")
    env = nodes.new(type="ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(path, check_existing=True)
    bg.inputs["Strength"].default_value = float(params.get("strength", 0.8))
    links.new(env.outputs["Color"], bg.inputs["Color"])
    links.new(bg.outputs["Background"], output.inputs["Surface"])
    return {"hdri_path": path, "world": world.name, "strength": bg.inputs["Strength"].default_value}
