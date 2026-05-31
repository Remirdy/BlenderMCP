"""Scene understanding: screenshots and scene graph metadata."""
from __future__ import annotations

import math
import os

import bpy
from mathutils import Vector

from . import helpers as H
from .export_ops import get_workspace_root


def _screenshot_path(filename: str) -> str:
    root = get_workspace_root()
    out = os.path.join(root, "outputs", "screenshots")
    os.makedirs(out, exist_ok=True)
    return os.path.join(out, os.path.basename(filename))


def _bounds(obj):
    if obj.type != "MESH":
        return None
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    mins = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    maxs = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return {
        "min": [round(mins.x, 3), round(mins.y, 3), round(mins.z, 3)],
        "max": [round(maxs.x, 3), round(maxs.y, 3), round(maxs.z, 3)],
    }


def _set_temp_camera(view: str):
    from . import render_ops as R

    center, radius = R._scene_bounds()
    cam_data = bpy.data.cameras.new(f"Screenshot_{view}_Camera")
    cam = bpy.data.objects.new(f"Screenshot_{view}_Camera", cam_data)
    H.get_or_create_collection("Cameras").objects.link(cam)
    cam.data.type = "ORTHO" if view in {"front", "side", "top"} else "PERSP"
    cam.data.ortho_scale = radius * 2.4
    if view == "front":
        cam.location = center + Vector((0, -radius * 3, 0))
    elif view == "side":
        cam.location = center + Vector((radius * 3, 0, 0))
    elif view == "top":
        cam.location = center + Vector((0, 0, radius * 3))
    else:
        cam.data.lens = 45
        cam.location = center + Vector((radius * 1.5, -radius * 2.0, radius * 1.1))
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return cam


def op_capture_viewport_screenshot(params):
    view = params.get("view", "camera")
    width = int(params.get("width", 1280))
    height = int(params.get("height", 720))
    path = _screenshot_path(params.get("filename", f"{view}_screenshot.png"))
    scene = bpy.context.scene
    old_camera = scene.camera
    old_x, old_y = scene.render.resolution_x, scene.render.resolution_y
    temp_camera = None
    try:
        if view != "camera" or scene.camera is None:
            temp_camera = _set_temp_camera(view)
            scene.camera = temp_camera
        scene.render.resolution_x = width
        scene.render.resolution_y = height
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = path
        try:
            bpy.ops.render.opengl(write_still=True, view_context=False)
            if not os.path.exists(path):
                raise RuntimeError("OpenGL capture did not produce a file")
        except Exception:
            scene.render.filepath = path
            bpy.ops.render.render(write_still=True)
        return {"screenshot_path": path, "view": view, "width": width, "height": height}
    finally:
        scene.camera = old_camera
        scene.render.resolution_x, scene.render.resolution_y = old_x, old_y
        if temp_camera is not None:
            bpy.data.objects.remove(temp_camera, do_unlink=True)


def op_get_scene_graph(params):
    objects = []
    for obj in bpy.context.scene.objects:
        item = {
            "name": obj.name,
            "type": obj.type,
            "parent": obj.parent.name if obj.parent else None,
            "collections": [c.name for c in obj.users_collection],
            "location": [round(v, 3) for v in obj.location],
            "rotation": [round(math.degrees(v), 3) for v in obj.rotation_euler],
            "scale": [round(v, 3) for v in obj.scale],
            "bounds": _bounds(obj),
        }
        if obj.type == "MESH":
            item["polygons"] = len(obj.data.polygons)
            item["materials"] = [m.name for m in obj.data.materials if m]
        elif obj.type == "ARMATURE":
            item["bones"] = [b.name for b in obj.data.bones]
        objects.append(item)
    return {
        "collections": [
            {"name": c.name, "objects": [o.name for o in c.objects], "children": [ch.name for ch in c.children]}
            for c in bpy.data.collections
        ],
        "objects": objects,
        "object_count": len(objects),
    }


def op_capture_scene_contact_sheet(params):
    views = params.get("views", ["camera", "front", "side", "top"])
    captures = []
    for view in views:
        captures.append(op_capture_viewport_screenshot({
            "view": view,
            "width": int(params.get("width", 960)),
            "height": int(params.get("height", 540)),
            "filename": f"contact_{view}.png",
        }))
    return {"captures": captures}


def op_analyze_scene_visuals(params):
    graph = op_get_scene_graph({})
    shot = op_capture_viewport_screenshot({
        "view": params.get("view", "camera"),
        "width": int(params.get("width", 1280)),
        "height": int(params.get("height", 720)),
    })
    mesh_count = len([o for o in graph["objects"] if o["type"] == "MESH"])
    material_count = len({m for o in graph["objects"] for m in o.get("materials", [])})
    return {
        "screenshot": shot,
        "object_count": graph["object_count"],
        "mesh_count": mesh_count,
        "material_count": material_count,
        "has_camera": any(o["type"] == "CAMERA" for o in graph["objects"]),
        "has_lights": any(o["type"] == "LIGHT" for o in graph["objects"]),
    }
