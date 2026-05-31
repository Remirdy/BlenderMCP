"""Scene status, inspection and basic scene management operations."""
from __future__ import annotations

import bpy

from . import helpers as H


def _poly_count(obj) -> int:
    if obj.type != "MESH":
        return 0
    return len(obj.data.polygons)


def op_ping(params):
    return {"pong": True, "addon": "remirdy", "blender": bpy.app.version_string}


def op_get_blender_status(params):
    scene = bpy.context.scene
    return {
        "blender_version": bpy.app.version_string,
        "render_engine": scene.render.engine,
        "frame": scene.frame_current,
        "objects": len(scene.objects),
        "bridge": "online",
    }


def op_get_scene_summary(params):
    scene = bpy.context.scene
    objs = list(scene.objects)
    meshes = [o for o in objs if o.type == "MESH"]
    lights = [o for o in objs if o.type == "LIGHT"]
    cams = [o for o in objs if o.type == "CAMERA"]
    mats = {m.name for o in meshes for m in o.data.materials if m}
    return {
        "object_count": len(objs),
        "mesh_count": len(meshes),
        "total_polygons": sum(_poly_count(o) for o in meshes),
        "collections": [c.name for c in bpy.data.collections],
        "camera": cams[0].name if cams else None,
        "light_count": len(lights),
        "materials": sorted(mats),
    }


def op_inspect_scene(params):
    out = []
    for o in bpy.context.scene.objects:
        out.append({
            "name": o.name,
            "type": o.type,
            "location": [round(c, 3) for c in o.location],
            "scale": [round(c, 3) for c in o.scale],
            "polygons": _poly_count(o),
            "materials": [m.name for m in o.data.materials] if o.type == "MESH" else [],
            "collections": [c.name for c in o.users_collection],
        })
    return {"objects": out, "count": len(out)}


def op_clear_scene(params):
    keep_camera = params.get("keep_camera", False)
    keep_lights = params.get("keep_lights", False)
    removed = 0
    for obj in list(bpy.context.scene.objects):
        if keep_camera and obj.type == "CAMERA":
            continue
        if keep_lights and obj.type == "LIGHT":
            continue
        bpy.data.objects.remove(obj, do_unlink=True)
        removed += 1
    # purge empty user-collections
    for coll in list(bpy.data.collections):
        if not coll.objects and not coll.children:
            try:
                bpy.data.collections.remove(coll)
            except Exception:
                pass
    return {"removed": removed}


def op_create_collection(params):
    coll = H.get_or_create_collection(params["name"])
    return {"collection": coll.name}


def op_create_product_render_scene(params):
    from . import material_ops as M
    from . import render_ops as R
    M.op_create_product_materials({})
    env = H.get_or_create_collection("Environment")
    props = H.get_or_create_collection("Props")
    bg = params.get("background", "studio_white")
    bg_mat = bpy.data.materials.get("Studio_White") if bg == "studio_white" else bpy.data.materials.get("Matte_Black")
    # Curved studio backdrop approximated by a large floor + back wall.
    H.add_plane("Studio_Floor", size=(20, 20), mat=bg_mat, collection=env)
    back = H.add_box("Studio_Backdrop", size=(20, 0.1, 10), location=(0, 6, 0), mat=bg_mat, collection=env)
    # Hero product on a plinth.
    plinth = H.add_cylinder("Plinth", radius=0.8, depth=0.4, verts=32,
                            mat=bpy.data.materials.get("Matte_Black"), collection=props)
    body = bpy.data.materials.get("Brushed_Metal")
    glass = bpy.data.materials.get("Premium_Glass")
    hero = H.add_box("Product_Body", size=(0.5, 0.25, 1.0), location=(0, 0, 0.4),
                     mat=body, collection=props)
    H.add_box("Product_Screen", size=(0.42, 0.02, 0.85), location=(0, -0.14, 0.5),
              mat=glass, collection=props)
    R.op_setup_product_camera({"focal_length": 85, "depth_of_field": True})
    R.op_setup_three_point_lighting({"strength": 1.2})
    R.op_apply_render_preset({"preset": "product_render"})
    return {"created": ["Studio_Floor", "Studio_Backdrop", "Plinth", "Product_Body", "Product_Screen"],
            "product": params.get("product", "device")}


def op_create_cinematic_scene(params):
    from . import render_ops as R
    env = H.get_or_create_collection("Environment")
    props = H.get_or_create_collection("Props")
    ground = H.make_material("Cine_Ground", color=(0.05, 0.05, 0.06), roughness=0.6)
    H.add_plane("Cine_Floor", size=(40, 40), mat=ground, collection=env)
    hero_mat = H.make_material("Cine_Hero", color=(0.6, 0.6, 0.65), metallic=0.8, roughness=0.3)
    H.add_box(params.get("subject", "hero_prop"), size=(1.5, 1.5, 3.0), mat=hero_mat, collection=props)
    R.op_setup_camera({"focal_length": 35})
    R.op_setup_cinematic_lighting({"mood": params.get("mood", "dramatic"), "volumetrics": True})
    R.op_apply_render_preset({"preset": "cinematic_render"})
    return {"created": ["Cine_Floor", params.get("subject", "hero_prop")], "mood": params.get("mood", "dramatic")}
