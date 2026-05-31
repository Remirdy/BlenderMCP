"""Asset & asset-pack quality scoring and auto-fix."""
from __future__ import annotations

import bpy

from . import asset_ops
from . import helpers as H
from . import quality_ops as Q

GAME_POLY_BUDGET = 8000       # per game-ready asset
ARCHVIZ_POLY_BUDGET = 60000   # per archviz asset


def _asset_objects(pack):
    coll = bpy.data.collections.get(pack.get("assets_collection", "")) if pack else None
    if coll:
        return [o for o in coll.objects if o.type == "MESH"]
    return H.all_mesh_objects()


def _score_object(obj, budget):
    checks = {}
    checks["named"] = not obj.name.split(".")[0] in ("Cube", "Sphere", "Plane", "Cylinder", "Object")
    checks["has_material"] = bool(obj.data.materials)
    checks["scale_applied"] = all(abs(s - 1.0) < 0.01 for s in obj.scale)
    checks["origin_ok"] = abs(obj.location.z) < 2.0  # rough: not floating wildly
    checks["polycount_ok"] = H.poly_count(obj) <= budget
    return checks


def op_score_asset_quality(params):
    name = params.get("asset_name")
    obj = bpy.data.objects.get(name) if name else None
    if obj is None:
        objs = _asset_objects(asset_ops.LAST_PACK)
        obj = objs[0] if objs else None
    if obj is None:
        raise ValueError("No asset to score.")
    budget = GAME_POLY_BUDGET if params.get("game", True) else ARCHVIZ_POLY_BUDGET
    checks = _score_object(obj, budget)
    score = round(100 * sum(checks.values()) / len(checks))
    return {"asset": obj.name, "polycount": H.poly_count(obj), "checks": checks, "score": score}


def _pack_report(pack, budget):
    objs = _asset_objects(pack)
    warnings = []
    high_poly = [o.name for o in objs if H.poly_count(o) > budget]
    no_mat = [o.name for o in objs if not o.data.materials]
    unscaled = [o.name for o in objs if any(abs(s - 1.0) > 0.01 for s in o.scale)]
    default_named = [o.name for o in objs if o.name.split(".")[0] in ("Cube", "Sphere", "Plane", "Cylinder", "Object")]

    # duplicate / unused materials
    used = {m.name for o in objs for m in o.data.materials if m}
    unused = [m.name for m in bpy.data.materials if m.users == 0 or (m.name in pack.get("materials", []) and m.name not in used)]

    if high_poly:
        warnings.append(f"{len(high_poly)} asset(s) exceed the polycount budget ({budget}).")
    if no_mat:
        warnings.append(f"{len(no_mat)} asset(s) missing materials.")
    if unscaled:
        warnings.append(f"{len(unscaled)} asset(s) have non-applied scale.")
    if default_named:
        warnings.append(f"{len(default_named)} asset(s) have default names.")
    if unused:
        warnings.append(f"{len(unused)} unused material(s).")

    has_thumbs = all(a.get("thumbnail") for a in pack.get("assets", [])) if pack.get("assets") else False
    if pack.get("assets") and not has_thumbs:
        warnings.append("Thumbnails not generated for all assets.")

    # scoring weights
    penalties = (len(high_poly) * 3 + len(no_mat) * 6 + len(unscaled) * 2
                 + len(default_named) * 4 + len(unused) * 1 + (0 if has_thumbs else 6))
    score = max(0, 100 - penalties)
    return {
        "score": score, "asset_count": len(objs),
        "high_poly": high_poly, "missing_materials": no_mat,
        "non_applied_scale": unscaled, "default_names": default_named,
        "unused_materials": unused, "thumbnails_complete": has_thumbs,
        "warnings": warnings,
    }


def op_score_asset_pack_quality(params):
    pack = asset_ops.LAST_PACK
    if not pack:
        raise ValueError("No asset pack in memory.")
    budget = GAME_POLY_BUDGET if params.get("game", True) else ARCHVIZ_POLY_BUDGET
    rep = _pack_report(pack, budget)
    rep["pack_name"] = pack["name"]
    rep["materials"] = len(pack.get("materials", []))
    rep["suggested_next"] = ("auto_fix_asset_pack" if rep["warnings"] else "package_asset_for_marketplace")
    rep["summary"] = f"Asset Pack Quality Score: {rep['score']}/100"
    return rep


def op_check_game_readiness(params):
    rep = _pack_report(asset_ops.LAST_PACK, GAME_POLY_BUDGET)
    ready = not rep["high_poly"] and not rep["missing_materials"] and not rep["non_applied_scale"]
    return {"game_ready": ready, "blocking": {
        "high_poly": rep["high_poly"], "missing_materials": rep["missing_materials"],
        "non_applied_scale": rep["non_applied_scale"]}, "score": rep["score"]}


def op_check_archviz_readiness(params):
    rep = _pack_report(asset_ops.LAST_PACK, ARCHVIZ_POLY_BUDGET)
    has_cam = any(o.type == "CAMERA" for o in bpy.context.scene.objects)
    has_light = any(o.type == "LIGHT" for o in bpy.context.scene.objects)
    ready = not rep["missing_materials"] and has_cam and has_light
    return {"archviz_ready": ready, "has_camera": has_cam, "has_light": has_light,
            "missing_materials": rep["missing_materials"], "score": rep["score"]}


def op_check_marketplace_readiness(params):
    pack = asset_ops.LAST_PACK
    rep = _pack_report(pack, GAME_POLY_BUDGET)
    import os
    from .packaging_ops import pack_root
    root = pack_root(pack["name"]) if pack else ""
    docs = os.path.join(root, "documentation")
    needed = {
        "readme": os.path.exists(os.path.join(docs, "README.md")),
        "manifest": os.path.exists(os.path.join(docs, "asset_manifest.json")),
        "license": os.path.exists(os.path.join(docs, "license.txt")),
        "glb_export": os.path.exists(os.path.join(root, "exports", "glb")) and bool(os.listdir(os.path.join(root, "exports", "glb"))) if root else False,
        "thumbnails": rep["thumbnails_complete"],
    }
    ready = all(needed.values()) and rep["score"] >= 70
    return {"marketplace_ready": ready, "requirements": needed, "quality_score": rep["score"],
            "warnings": rep["warnings"]}


def op_auto_fix_asset_pack(params):
    pack = asset_ops.LAST_PACK
    if not pack:
        raise ValueError("No asset pack in memory.")
    before = _pack_report(pack, GAME_POLY_BUDGET)
    objs = _asset_objects(pack)
    actions = []

    # apply scale/rotation
    H.select_only(objs)
    if objs:
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        actions.append("applied_scale_rotation")

    # assign default material where missing
    from . import material_ops as M
    default = M.ensure_default_material("Pack_Default")
    fixed_mat = 0
    for o in objs:
        if not o.data.materials:
            H.assign_material(o, default)
            fixed_mat += 1
    if fixed_mat:
        actions.append(f"assigned_materials:{fixed_mat}")

    # set bottom-center origins
    for o in objs:
        try:
            H.set_origin_bottom_center(o)
        except Exception:
            pass
    actions.append("set_origins")

    # decimate high-poly assets
    decimated = 0
    for o in objs:
        if H.poly_count(o) > GAME_POLY_BUDGET:
            mod = o.modifiers.new("Decimate", "DECIMATE")
            mod.ratio = max(0.2, GAME_POLY_BUDGET / max(1, H.poly_count(o)))
            H.select_only([o])
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
                decimated += 1
            except Exception:
                pass
    if decimated:
        actions.append(f"decimated:{decimated}")

    # purge unused data
    try:
        bpy.ops.outliner.orphans_purge(do_recursive=True)
        actions.append("purged_unused_data")
    except Exception:
        pass

    after = _pack_report(pack, GAME_POLY_BUDGET)
    return {"actions": actions, "score_before": before["score"], "score_after": after["score"],
            "remaining_warnings": after["warnings"]}
