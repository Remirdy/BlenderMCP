"""Scene organization, transform cleanup and quality control."""
from __future__ import annotations

import os
import bpy
from mathutils import Vector

from . import helpers as H
from . import material_ops as M
from . import render_ops as R
from .export_ops import get_workspace_root

HIGH_POLY_THRESHOLD = 500_000

# Map keyword -> target collection for organization.
_ORG_RULES = (
    (("Wall", "Floor", "Ceiling", "Roof", "House", "Building", "Partition", "Stair", "Win", "Door", "Facade", "Corridor", "Panel", "Mod_"), "Architecture"),
    (("Sofa", "Table", "Chair", "Bed", "Cabinet", "Wardrobe", "Desk", "Counter", "Island", "Shelf", "Rug", "TV", "Plant", "Nightstand", "Fridge", "Headboard"), "Furniture"),
    (("Tree", "Road", "Ground", "Lawn", "Pool", "Pathway", "Studio", "Cine_Floor"), "Environment"),
)


def op_organize_scene(params):
    moved = 0
    for obj in list(bpy.context.scene.objects):
        if obj.type == "CAMERA":
            H.link_to_collection(obj, H.get_or_create_collection("Cameras")); moved += 1; continue
        if obj.type == "LIGHT":
            H.link_to_collection(obj, H.get_or_create_collection("Lighting")); moved += 1; continue
        if obj.type != "MESH":
            continue
        target = "Props"
        for keys, coll in _ORG_RULES:
            if any(k in obj.name for k in keys):
                target = coll
                break
        H.link_to_collection(obj, H.get_or_create_collection(target))
        moved += 1
    return {"objects_organized": moved, "collections": [c.name for c in bpy.data.collections]}


def op_rename_objects_professionally(params):
    prefix = params.get("prefix", "")
    counts: dict[str, int] = {}
    renamed = 0
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            base = next((k for keys, c in _ORG_RULES for k in keys if k in obj.name), None)
            category = base.rstrip("_") if base else "Prop"
        else:
            category = obj.type.title()
        counts[category] = counts.get(category, 0) + 1
        new = f"{prefix}{category}_{counts[category]:02d}" if prefix else f"{category}_{counts[category]:02d}"
        if obj.name != new:
            obj.name = new
            renamed += 1
    return {"renamed": renamed}


def op_set_origins_and_pivots(params):
    mode = params.get("mode", "bottom_center")
    done = 0
    for obj in H.all_mesh_objects():
        try:
            if mode == "geometry":
                H.select_only([obj])
                bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY")
            else:
                H.set_origin_bottom_center(obj)
            done += 1
        except Exception:
            continue
    return {"origins_set": done, "mode": mode}


def op_fix_transforms(params):
    fixed = 0
    for obj in bpy.context.scene.objects:
        changed = False
        for i in range(3):
            if obj.location[i] != obj.location[i]:  # NaN check
                obj.location[i] = 0.0; changed = True
            if abs(obj.rotation_euler[i]) < 1e-4 and obj.rotation_euler[i] != 0.0:
                obj.rotation_euler[i] = 0.0; changed = True
        if changed:
            fixed += 1
    return {"transforms_fixed": fixed}


def op_apply_scale_rotation(params):
    meshes = H.all_mesh_objects()
    H.select_only(meshes)
    if meshes:
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return {"objects_applied": len(meshes)}


def op_scene_quality_check(params):
    scene = bpy.context.scene
    objs = list(scene.objects)
    meshes = [o for o in objs if o.type == "MESH"]
    issues = []

    if not any(o.type == "CAMERA" for o in objs):
        issues.append({"severity": "error", "code": "no_camera", "message": "Scene has no camera."})
    if not any(o.type == "LIGHT" for o in objs) and (scene.world is None):
        issues.append({"severity": "error", "code": "no_light", "message": "Scene has no lights or world lighting."})

    no_mat = [o.name for o in meshes if not o.data.materials]
    if no_mat:
        issues.append({"severity": "warning", "code": "missing_materials",
                       "message": f"{len(no_mat)} object(s) without materials.", "objects": no_mat[:20]})

    default_named = [o.name for o in meshes if o.name.split(".")[0] in ("Cube", "Sphere", "Plane", "Cylinder", "Object")]
    if default_named:
        issues.append({"severity": "warning", "code": "default_names",
                       "message": f"{len(default_named)} object(s) with default names.", "objects": default_named[:20]})

    total_poly = sum(len(o.data.polygons) for o in meshes)
    if total_poly > HIGH_POLY_THRESHOLD:
        issues.append({"severity": "warning", "code": "high_polycount",
                       "message": f"High polycount: {total_poly} faces (> {HIGH_POLY_THRESHOLD})."})

    bad_scale = [o.name for o in meshes if any(abs(s) > 100 or (0 < abs(s) < 0.001) for s in o.scale)]
    if bad_scale:
        issues.append({"severity": "warning", "code": "bad_scale",
                       "message": "Extreme object scales detected.", "objects": bad_scale[:20]})

    only_master = all(set(o.users_collection) == {scene.collection} for o in meshes) if meshes else False
    if only_master:
        issues.append({"severity": "info", "code": "unorganized",
                       "message": "Objects are not organized into collections."})

    score = max(0, 100 - sum({"error": 30, "warning": 12, "info": 4}[i["severity"]] for i in issues))
    return {"issues": issues, "issue_count": len(issues), "quality_score": score,
            "total_polygons": total_poly, "passed": not any(i["severity"] == "error" for i in issues)}


def op_auto_fix_scene(params):
    report = op_scene_quality_check({})
    actions = []
    codes = {i["code"] for i in report["issues"]}

    if "no_camera" in codes:
        R.op_setup_camera({}); actions.append("added_camera")
    if "no_light" in codes:
        R.op_setup_lighting({"style": "soft"}); actions.append("added_lighting")
    if "missing_materials" in codes:
        default = M.ensure_default_material()
        n = 0
        for o in H.all_mesh_objects():
            if not o.data.materials:
                H.assign_material(o, default); n += 1
        actions.append(f"assigned_materials:{n}")
    if "default_names" in codes:
        op_rename_objects_professionally({}); actions.append("renamed_objects")
    if "unorganized" in codes:
        op_organize_scene({}); actions.append("organized_scene")
    if params.get("aggressive"):
        op_set_origins_and_pivots({"mode": "bottom_center"}); actions.append("set_origins")

    after = op_scene_quality_check({})
    return {"actions": actions, "quality_score_before": report["quality_score"],
            "quality_score_after": after["quality_score"], "remaining_issues": after["issue_count"]}


def _mesh_bounds(meshes):
    if not meshes:
        return Vector((0, 0, 0)), Vector((0, 0, 0)), Vector((0, 0, 0))
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    for obj in meshes:
        for corner in obj.bound_box:
            point = obj.matrix_world @ Vector(corner)
            mins = Vector((min(mins.x, point.x), min(mins.y, point.y), min(mins.z, point.z)))
            maxs = Vector((max(maxs.x, point.x), max(maxs.y, point.y), max(maxs.z, point.z)))
    return mins, maxs, (mins + maxs) / 2.0


def op_normalize_imported_asset(params):
    """Normalize selected/all meshes to a target max dimension and ground origin."""
    meshes = [o for o in bpy.context.selected_objects if o.type == "MESH"] if params.get("selected_only") else H.all_mesh_objects()
    if not meshes:
        return {"normalized": 0, "message": "No mesh objects found."}
    target = float(params.get("target_size", 2.0))
    mins, maxs, center = _mesh_bounds(meshes)
    dims = maxs - mins
    max_dim = max(dims.x, dims.y, dims.z, 1e-6)
    scale_factor = target / max_dim
    root = bpy.data.objects.new(params.get("name", "NormalizedAssetRoot"), None)
    bpy.context.scene.collection.objects.link(root)
    root.location = center
    for obj in meshes:
        world = obj.matrix_world.copy()
        obj.parent = root
        obj.matrix_world = world
    root.scale = (scale_factor, scale_factor, scale_factor)
    bpy.context.view_layer.update()
    mins2, _, _ = _mesh_bounds(meshes)
    root.location.z -= mins2.z
    return {"normalized": len(meshes), "target_size": target, "scale_factor": round(scale_factor, 5), "root": root.name}


def op_repair_materials(params):
    """Assign missing materials and make material names/render settings consistent."""
    default = H.make_material("M_Default_Repaired", color=(0.55, 0.55, 0.58, 1), roughness=0.75)
    repaired = 0
    renamed = 0
    for obj in H.all_mesh_objects():
        if not obj.data.materials:
            H.assign_material(obj, default)
            repaired += 1
        for slot in obj.material_slots:
            mat = slot.material
            if mat and not mat.name.startswith("M_"):
                mat.name = f"M_{mat.name}"
                renamed += 1
            if mat:
                mat.use_nodes = True
    return {"materials_assigned": repaired, "materials_renamed": renamed}


def op_decimate_asset(params):
    """Add decimate modifiers to high-poly meshes or apply when requested."""
    ratio = float(params.get("ratio", 0.5))
    apply = bool(params.get("apply", False))
    changed = []
    for obj in H.all_mesh_objects():
        if len(obj.data.polygons) < int(params.get("min_faces", 1000)):
            continue
        mod = obj.modifiers.new("remirdy_decimate", "DECIMATE")
        mod.ratio = max(0.05, min(ratio, 1.0))
        if apply:
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except Exception:
                pass
            obj.select_set(False)
        changed.append(obj.name)
    return {"objects": changed, "count": len(changed), "ratio": ratio, "applied": apply}


def op_generate_lods(params):
    """Duplicate meshes into LOD collections with decimate modifiers."""
    ratios = params.get("ratios", [0.6, 0.3, 0.12])
    if isinstance(ratios, str):
        ratios = [float(x.strip()) for x in ratios.split(",") if x.strip()]
    meshes = H.all_mesh_objects()
    created = []
    for idx, ratio in enumerate(ratios, start=1):
        coll = H.get_or_create_collection(f"LOD{idx}")
        for obj in meshes:
            dup = obj.copy()
            dup.data = obj.data.copy()
            dup.name = f"{obj.name}_LOD{idx}"
            bpy.context.scene.collection.objects.link(dup)
            H.link_to_collection(dup, coll)
            mod = dup.modifiers.new("lod_decimate", "DECIMATE")
            mod.ratio = max(0.03, min(float(ratio), 1.0))
            created.append(dup.name)
    return {"lod_objects": created, "count": len(created), "ratios": ratios}


def op_create_collision_proxies(params):
    """Create simple box collision proxy meshes for every mesh object."""
    coll = H.get_or_create_collection("Collision")
    created = []
    for obj in H.all_mesh_objects():
        if obj.name.startswith("COL_"):
            continue
        mins, maxs, center = _mesh_bounds([obj])
        dims = maxs - mins
        proxy = H.add_box(
            f"COL_{obj.name}",
            size=(max(dims.x, 0.02), max(dims.y, 0.02), max(dims.z, 0.02)),
            location=(center.x, center.y, mins.z),
            collection=coll,
            mat=H.make_material("M_Collision_Proxy", color=(0.1, 0.8, 0.2, 0.22)),
        )
        proxy.display_type = "WIRE"
        proxy.hide_render = True
        proxy["remirdy_collision_for"] = obj.name
        created.append(proxy.name)
    return {"collision_proxies": created, "count": len(created), "mode": "box"}


def op_check_engine_readiness(params):
    target = params.get("target", "unity")
    meshes = H.all_mesh_objects()
    issues = []
    total_faces = sum(len(o.data.polygons) for o in meshes)
    if not meshes:
        issues.append({"severity": "error", "code": "no_meshes", "message": "No mesh objects to export."})
    if total_faces > int(params.get("max_faces", 100000)):
        issues.append({"severity": "warning", "code": "poly_budget", "message": f"Face count {total_faces} exceeds budget."})
    missing_mats = [o.name for o in meshes if not o.data.materials]
    if missing_mats:
        issues.append({"severity": "warning", "code": "missing_materials", "objects": missing_mats[:25]})
    unapplied = [o.name for o in meshes if any(abs(v - 1.0) > 1e-3 for v in o.scale)]
    if unapplied:
        issues.append({"severity": "info", "code": "unapplied_scale", "objects": unapplied[:25]})
    if target in {"unity", "unreal"} and not any(c.name == "Collision" for c in bpy.data.collections):
        issues.append({"severity": "info", "code": "no_collision", "message": "No collision proxy collection found."})
    armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    score = max(0, 100 - sum({"error": 35, "warning": 12, "info": 4}[i["severity"]] for i in issues))
    return {
        "target": target,
        "ready": not any(i["severity"] == "error" for i in issues),
        "score": score,
        "issues": issues,
        "mesh_count": len(meshes),
        "armature_count": len(armatures),
        "total_faces": total_faces,
    }


def op_check_license_metadata(params):
    root = os.path.join(get_workspace_root(), "outputs", "imports")
    found = []
    missing = []
    for dirpath, _, filenames in os.walk(root):
        files = set(filenames)
        if not files:
            continue
        if {"attribution.json", "metadata.json", "download.json"} & files:
            found.append(dirpath)
        elif any(name.lower().endswith((".glb", ".gltf", ".fbx", ".obj", ".blend", ".zip")) for name in files):
            missing.append(dirpath)
    return {
        "metadata_dirs": found,
        "missing_metadata_dirs": missing,
        "passed": not missing,
        "checked_root": root,
    }


def op_apply_quad_remesh(params):
    """Run Blender's built-in Voxel Remesher on dense AI meshes to generate a clean quad layout."""
    voxel_size = float(params.get("voxel_size", 0.035))
    selected_only = bool(params.get("selected_only", True))

    targets = [o for o in bpy.context.selected_objects if o.type == 'MESH'] if selected_only else H.all_mesh_objects()
    applied = 0

    for obj in targets:
        if obj.name.startswith("COL_"):
            continue

        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        # Set voxel size and run remeshing
        obj.data.remesh_voxel_size = voxel_size
        try:
            bpy.ops.object.voxel_remesh()
            applied += 1
        except Exception:
            pass

    return {"ok": True, "meshes_remeshed": applied, "voxel_size": voxel_size}


def op_apply_voxel_blockout(params):
    """Dynamically reconstruct selected models as highly stylized voxel blocks utilizing Remesh modifiers."""
    depth = int(params.get("depth", 6))
    selected_only = bool(params.get("selected_only", True))

    targets = [o for o in bpy.context.selected_objects if o.type == 'MESH'] if selected_only else H.all_mesh_objects()
    applied = 0

    for obj in targets:
        if obj.name.startswith(("COL_", "Studio_Base", "Ground_")):
            continue

        mod = obj.modifiers.get("Remirdy_Voxelizer") or obj.modifiers.new("Remirdy_Voxelizer", "REMESH")
        mod.mode = 'BLOCKS'
        mod.octree_depth = depth
        mod.use_remove_disconnected = True

        # Shade flat to look like beautiful cubes
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        try:
            bpy.ops.object.shade_flat()
        except Exception:
            pass

        applied += 1

    return {"ok": True, "voxelized_objects": applied, "depth": depth}


def op_prepare_for_3d_printing(params):
    """
    Professional 3D printing preparation pipeline.
    - Detects non-manifold geometry
    - Suggests / applies minimum wall thickness via Solidify
    - Decimates for printability if needed
    - Returns detailed printability report
    """
    import bmesh

    target = params.get("target")
    min_thickness = float(params.get("min_thickness_mm", 1.5))

    objects_to_process = []
    if target:
        obj = bpy.data.objects.get(target)
        if obj and obj.type == "MESH":
            objects_to_process = [obj]
    else:
        objects_to_process = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.select_get()]

    if not objects_to_process:
        objects_to_process = [o for o in bpy.context.scene.objects if o.type == "MESH"]

    report = {
        "processed": [],
        "non_manifold_issues": 0,
        "printability_score": 100,
        "recommendations": [],
    }

    for obj in objects_to_process:
        if obj.type != "MESH":
            continue

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.edges.ensure_lookup_table()

        non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
        bm.free()

        issues = []
        score = 100

        if non_manifold > 0:
            issues.append(f"{non_manifold} non-manifold edges")
            score -= min(40, non_manifold * 2)
            report["non_manifold_issues"] += non_manifold

        # Very crude volume / scale check
        dims = obj.dimensions
        min_dim = min(dims)
        if min_dim < 0.02:  # 2cm in Blender units
            issues.append("Very thin features detected")
            score -= 15

        # Auto Solidify for thin walls (conservative)
        if min_dim < (min_thickness / 1000) and not any(m.type == "SOLIDIFY" for m in obj.modifiers):
            try:
                mod = obj.modifiers.new("Print_Thickness", "SOLIDIFY")
                mod.thickness = max(0.0015, min_thickness / 1000)
                mod.use_even_offset = True
                issues.append(f"Added Solidify modifier ({min_thickness}mm)")
            except Exception:
                pass

        report["processed"].append({
            "name": obj.name,
            "non_manifold": non_manifold,
            "issues": issues,
            "score": max(30, score),
        })

        if issues:
            report["recommendations"].extend(issues)

    avg_score = sum(p["score"] for p in report["processed"]) / max(1, len(report["processed"]))
    report["printability_score"] = round(avg_score)

    if report["non_manifold_issues"] > 0:
        report["recommendations"].append("Run 'Make Manifold' or manual cleanup before printing")

    return {
        "ok": True,
        "printability_score": report["printability_score"],
        "details": report,
        "message": f"3D Print preparation complete. Overall score: {report['printability_score']}/100",
    }


# =============================================================================
# PROFESSIONAL OPTIMIZATION & DELIVERY (C Priority)
# =============================================================================

def op_generate_lods_advanced(params):
    """
    Professional multi-level LOD generation for game engines.
    Creates LOD1, LOD2, etc. with sensible decimation.
    """
    ratios = params.get("ratios", [0.5, 0.25, 0.1])
    target = params.get("target")

    objects = []
    if target:
        obj = bpy.data.objects.get(target)
        if obj and obj.type == "MESH":
            objects = [obj]
    else:
        objects = [o for o in bpy.context.selected_objects if o.type == "MESH"]

    if not objects:
        objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]

    created = []

    for obj in objects:
        if obj.type != "MESH":
            continue

        for idx, ratio in enumerate(ratios):
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj

            bpy.ops.object.duplicate()
            lod = bpy.context.object
            lod.name = f"{obj.name}_LOD{idx+1}"

            mod = lod.modifiers.new("LOD_Decimate", "DECIMATE")
            mod.ratio = ratio
            mod.use_collapse_triangulate = True

            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except Exception:
                pass

            created.append(lod.name)

    return {
        "ok": True,
        "lods_created": created,
        "message": f"Generated {len(created)} LOD meshes"
    }


def op_prepare_lightmap_uvs(params):
    """
    Creates a clean second UV channel suitable for lightmaps.
    """
    margin = float(params.get("margin", 0.01))
    target = params.get("target")

    objects = []
    if target:
        obj = bpy.data.objects.get(target)
        if obj and obj.type == "MESH":
            objects = [obj]
    else:
        objects = [o for o in bpy.context.selected_objects if o.type == "MESH"]

    processed = []

    for obj in objects:
        if obj.type != "MESH":
            continue

        mesh = obj.data
        if "Lightmap" not in mesh.uv_layers:
            mesh.uv_layers.new(name="Lightmap")

        mesh.uv_layers["Lightmap"].active = True

        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        try:
            bpy.ops.uv.smart_project(angle_limit=66, island_margin=margin)
        except Exception:
            pass

        processed.append(obj.name)

    return {
        "ok": True,
        "processed": processed,
        "uv_layer": "Lightmap"
    }
