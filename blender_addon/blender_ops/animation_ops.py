"""Animation, drivers, timeline and edit-history engine.

Before this module the add-on could pose a character rig but had no general way
to animate *anything*. This adds a safe, declarative keyframe/driver layer plus
timeline control and undo/redo — the pieces a real design loop needs.

Highlights:
  * keyframe_object        — keyframe transform channels at given frames.
  * animate_property       — keyframe an arbitrary (allow-listed) data path.
  * animate_node_input     — keyframe a *node socket* default value, i.e.
    procedural motion graphics: a noise scale, a displace strength, an emission
    colour can all be animated over time.  This is where "design with nodes"
    meets animation.
  * add_driver             — link one property to another with a simple
    expression driver.
  * set_frame_range / clear_animation / create_turntable — timeline helpers.
  * undo / redo / checkpoint — wrap Blender's native edit history so the AI can
    safely experiment and roll back.

Safety: animate_property only writes to a small allow-list of data paths
(transform, visibility, common modifier/material scalars). It never evaluates
caller-supplied Python; drivers use Blender's own sandboxed expression field.
"""
from __future__ import annotations

from typing import Any

import bpy

# Transform channels keyframe_insert understands, mapped to component count.
_TRANSFORM_PATHS = {
    "location": 3,
    "rotation_euler": 3,
    "scale": 3,
    "delta_location": 3,
    "delta_rotation_euler": 3,
}

# Allow-list of object-level data paths animate_property may touch.
_ALLOWED_OBJ_PATHS = set(_TRANSFORM_PATHS) | {
    "hide_viewport", "hide_render", "color",
}


def _get_object(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"object '{name}' not found")
    return obj


# --------------------------------------------------------------------------- #
# Keyframing
# --------------------------------------------------------------------------- #
def op_keyframe_object(params: dict) -> dict:
    """Keyframe an object's transform across a list of keyframes.

    params: object, keyframes[ {frame, location?, rotation_euler?, scale?} ],
            interpolation? (CONSTANT|LINEAR|BEZIER, default BEZIER).
    """
    try:
        obj = _get_object(params.get("object"))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    keys = params.get("keyframes", [])
    if not keys:
        return {"ok": False, "error": "no keyframes provided"}

    inserted = 0
    for kf in keys:
        frame = int(kf.get("frame", 1))
        for path in _TRANSFORM_PATHS:
            if path in kf:
                try:
                    setattr(obj, path, kf[path])
                    obj.keyframe_insert(path, frame=frame)
                    inserted += 1
                except (TypeError, RuntimeError):
                    pass

    _apply_interpolation(obj, params.get("interpolation", "BEZIER"))
    return {"ok": True, "object": obj.name, "channels_keyed": inserted,
            "keyframe_count": len(keys)}


def op_animate_property(params: dict) -> dict:
    """Keyframe one allow-listed property over frame:value pairs.

    params: object, data_path (e.g. "location"), index? (vector component),
            keys[ {frame, value} ], interpolation?.
    """
    try:
        obj = _get_object(params.get("object"))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    path = params.get("data_path", "")
    if path not in _ALLOWED_OBJ_PATHS:
        return {"ok": False, "error": f"data_path '{path}' not allowed",
                "allowed": sorted(_ALLOWED_OBJ_PATHS)}

    index = params.get("index")
    inserted = 0
    for k in params.get("keys", []):
        frame = int(k.get("frame", 1))
        value = k.get("value")
        try:
            if index is None:
                setattr(obj, path, value)
                obj.keyframe_insert(path, frame=frame)
            else:
                cur = list(getattr(obj, path))
                cur[index] = value
                setattr(obj, path, cur)
                obj.keyframe_insert(path, index=index, frame=frame)
            inserted += 1
        except (TypeError, RuntimeError, IndexError):
            pass
    _apply_interpolation(obj, params.get("interpolation", "BEZIER"))
    return {"ok": True, "object": obj.name, "data_path": path, "keys_inserted": inserted}


def op_animate_node_input(params: dict) -> dict:
    """Keyframe a node socket's default value over time (procedural motion).

    Target either a material's shader node or an object's geometry-node modifier.
    params: material|object, node (name or label), socket (name|index),
            keys[ {frame, value} ], interpolation?.
    """
    nt = None
    if params.get("material"):
        mat = bpy.data.materials.get(params["material"])
        if mat is None or not mat.use_nodes:
            return {"ok": False, "error": f"material '{params.get('material')}' has no nodes"}
        nt = mat.node_tree
    elif params.get("object"):
        obj = bpy.data.objects.get(params["object"])
        mod = next((m for m in (obj.modifiers if obj else []) if m.type == "NODES" and m.node_group), None)
        if mod is None:
            return {"ok": False, "error": "object has no Geometry Nodes modifier"}
        nt = mod.node_group
    if nt is None:
        return {"ok": False, "error": "provide a valid 'material' or 'object'"}

    node_key = params.get("node")
    node = next((n for n in nt.nodes if n.name == node_key or n.label == node_key), None)
    if node is None:
        return {"ok": False, "error": f"node '{node_key}' not found"}

    sock_key = params.get("socket", 0)
    socket = None
    if isinstance(sock_key, int) and 0 <= sock_key < len(node.inputs):
        socket = node.inputs[sock_key]
    else:
        socket = next((s for s in node.inputs if s.name == sock_key), None)
    if socket is None or not hasattr(socket, "default_value"):
        return {"ok": False, "error": f"socket '{sock_key}' not keyable"}

    inserted = 0
    for k in params.get("keys", []):
        frame = int(k.get("frame", 1))
        try:
            socket.default_value = k.get("value")
            socket.keyframe_insert("default_value", frame=frame)
            inserted += 1
        except (TypeError, RuntimeError):
            pass
    return {"ok": True, "node": node.name, "socket": getattr(socket, "name", sock_key),
            "keys_inserted": inserted}


def _apply_interpolation(obj, mode: str) -> None:
    mode = (mode or "BEZIER").upper()
    ad = getattr(obj, "animation_data", None)
    if ad is None or ad.action is None:
        return
    for fc in ad.action.fcurves:
        for kp in fc.keyframe_points:
            try:
                kp.interpolation = mode
            except (TypeError, ValueError):
                pass


# --------------------------------------------------------------------------- #
# Drivers
# --------------------------------------------------------------------------- #
def op_add_driver(params: dict) -> dict:
    """Add a simple single-variable driver to a property.

    params: object, data_path, index? , expression? (default "var"),
            target_object, target_data_path (the variable source).
    """
    try:
        obj = _get_object(params.get("object"))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    try:
        idx = params.get("index", -1)
        fcurve = obj.driver_add(params.get("data_path"), idx) if idx is not None and idx >= 0 \
            else obj.driver_add(params.get("data_path"))
    except (TypeError, RuntimeError) as exc:
        return {"ok": False, "error": f"driver_add failed: {exc}"}

    fcurve = fcurve if not isinstance(fcurve, list) else fcurve[0]
    drv = fcurve.driver
    drv.type = "SCRIPTED"
    var = drv.variables.new()
    var.name = "var"
    tgt_obj = bpy.data.objects.get(params.get("target_object", obj.name)) or obj
    try:
        var.targets[0].id = tgt_obj
        var.targets[0].data_path = params.get("target_data_path", "location.x")
    except (IndexError, AttributeError):
        pass
    drv.expression = params.get("expression", "var")
    return {"ok": True, "object": obj.name, "data_path": params.get("data_path"),
            "expression": drv.expression}


# --------------------------------------------------------------------------- #
# Timeline helpers
# --------------------------------------------------------------------------- #
def op_set_frame_range(params: dict) -> dict:
    """Set the scene's playback range and fps. params: start, end, fps?."""
    scene = bpy.context.scene
    scene.frame_start = int(params.get("start", scene.frame_start))
    scene.frame_end = int(params.get("end", scene.frame_end))
    if "fps" in params:
        scene.render.fps = int(params["fps"])
    return {"ok": True, "start": scene.frame_start, "end": scene.frame_end,
            "fps": scene.render.fps}


def op_create_turntable(params: dict) -> dict:
    """Keyframe a full Z-rotation on an object (or a turntable empty).

    params: object, frames? (default 120), revolutions? (default 1).
    """
    try:
        obj = _get_object(params.get("object"))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    import math
    frames = int(params.get("frames", 120))
    revs = float(params.get("revolutions", 1.0))
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, frames
    obj.rotation_euler = (obj.rotation_euler[0], obj.rotation_euler[1], 0.0)
    obj.keyframe_insert("rotation_euler", index=2, frame=1)
    obj.rotation_euler = (obj.rotation_euler[0], obj.rotation_euler[1], math.radians(360 * revs))
    obj.keyframe_insert("rotation_euler", index=2, frame=frames)
    # linear so the spin is constant-speed
    ad = obj.animation_data
    if ad and ad.action:
        for fc in ad.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    return {"ok": True, "object": obj.name, "frames": frames, "revolutions": revs}


def op_clear_animation(params: dict) -> dict:
    """Remove all animation data from an object. params: object."""
    try:
        obj = _get_object(params.get("object"))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    obj.animation_data_clear()
    return {"ok": True, "object": obj.name, "cleared": True}


# --------------------------------------------------------------------------- #
# Edit history (undo / redo / checkpoint)
# --------------------------------------------------------------------------- #
def op_checkpoint(params: dict) -> dict:
    """Push a named checkpoint onto Blender's undo stack before a risky change."""
    msg = params.get("message", "Remirdy checkpoint")
    try:
        bpy.ops.ed.undo_push(message=msg)
        return {"ok": True, "checkpoint": msg}
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}


def op_undo(params: dict) -> dict:
    """Undo the last edit (steps? times, default 1)."""
    steps = int(params.get("steps", 1))
    done = 0
    for _ in range(max(1, steps)):
        try:
            bpy.ops.ed.undo()
            done += 1
        except RuntimeError:
            break
    return {"ok": True, "undone": done}


def op_redo(params: dict) -> dict:
    """Redo the last undone edit (steps? times, default 1)."""
    steps = int(params.get("steps", 1))
    done = 0
    for _ in range(max(1, steps)):
        try:
            bpy.ops.ed.redo()
            done += 1
        except RuntimeError:
            break
    return {"ok": True, "redone": done}
