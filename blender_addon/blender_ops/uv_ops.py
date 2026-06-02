"""UV unwrapping toolkit.

Procedural and image-based materials only look right if the mesh has sane UVs.
Until now the add-on assigned materials but never unwrapped, so textures
stretched or tiled wrong. These ops give the AI proper unwrap control.

Ops:
  * smart_uv_project  — one-click angle-based unwrap (great default for props).
  * unwrap            — conformal/angle-based unwrap of existing seams.
  * mark_seams_by_angle — auto-mark sharp edges as seams, then unwrap.
  * pack_islands      — repack UV islands to use the 0–1 space efficiently.

All ops handle edit/object mode transitions and selection defensively.
"""
from __future__ import annotations

import bpy


def _get_mesh_object(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"object '{name}' not found")
    if obj.type != "MESH":
        raise ValueError(f"object '{name}' is not a mesh")
    return obj


def _activate(obj):
    try:
        bpy.context.view_layer.objects.active = obj
        for o in bpy.context.selected_objects:
            o.select_set(False)
        obj.select_set(True)
    except (AttributeError, RuntimeError):
        pass


def _ensure_uv_layer(obj):
    if not obj.data.uv_layers:
        obj.data.uv_layers.new(name="UVMap")


def _edit_mode():
    try:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        return True
    except RuntimeError:
        return False


def _object_mode():
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except RuntimeError:
        pass


def op_smart_uv_project(params: dict) -> dict:
    """Angle-based automatic unwrap — the best one-call default for props.

    params: object, angle_limit (deg, default 66), island_margin (default 0.02).
    """
    try:
        obj = _get_mesh_object(params.get("object"))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    _activate(obj)
    _ensure_uv_layer(obj)
    if not _edit_mode():
        return {"ok": False, "error": "could not enter edit mode (no 3D context?)"}
    import math
    try:
        bpy.ops.uv.smart_project(
            angle_limit=math.radians(float(params.get("angle_limit", 66.0))),
            island_margin=float(params.get("island_margin", 0.02)),
        )
        ok = True
    except (RuntimeError, TypeError):
        ok = False
    _object_mode()
    return {"ok": ok, "object": obj.name, "method": "smart_uv_project"}


def op_unwrap(params: dict) -> dict:
    """Unwrap using existing seams. params: object, method (ANGLE_BASED|CONFORMAL),
    margin (default 0.02)."""
    try:
        obj = _get_mesh_object(params.get("object"))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    _activate(obj)
    _ensure_uv_layer(obj)
    if not _edit_mode():
        return {"ok": False, "error": "could not enter edit mode"}
    try:
        bpy.ops.uv.unwrap(method=params.get("method", "ANGLE_BASED").upper(),
                          margin=float(params.get("margin", 0.02)))
        ok = True
    except (RuntimeError, TypeError):
        ok = False
    _object_mode()
    return {"ok": ok, "object": obj.name, "method": "unwrap"}


def op_mark_seams_by_angle(params: dict) -> dict:
    """Auto-mark sharp edges as UV seams then unwrap. params: object,
    angle (deg, default 40)."""
    try:
        obj = _get_mesh_object(params.get("object"))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    _activate(obj)
    _ensure_uv_layer(obj)
    if not _edit_mode():
        return {"ok": False, "error": "could not enter edit mode"}
    import math
    marked = False
    try:
        bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.mesh.edges_select_sharp(sharpness=math.radians(float(params.get("angle", 40.0))))
        bpy.ops.mesh.mark_seam(clear=False)
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.02)
        marked = True
    except (RuntimeError, TypeError):
        pass
    _object_mode()
    return {"ok": marked, "object": obj.name, "method": "mark_seams_by_angle"}


def op_pack_uv_islands(params: dict) -> dict:
    """Repack UV islands into the 0–1 space. params: object, margin (default 0.02)."""
    try:
        obj = _get_mesh_object(params.get("object"))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    _activate(obj)
    if not obj.data.uv_layers:
        return {"ok": False, "error": "object has no UVs to pack; unwrap first"}
    if not _edit_mode():
        return {"ok": False, "error": "could not enter edit mode"}
    try:
        bpy.ops.uv.select_all(action="SELECT")
        bpy.ops.uv.pack_islands(margin=float(params.get("margin", 0.02)))
        ok = True
    except (RuntimeError, TypeError):
        ok = False
    _object_mode()
    return {"ok": ok, "object": obj.name, "method": "pack_islands"}
