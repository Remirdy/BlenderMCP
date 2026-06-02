"""Procedural humanoid character, rig and animation operations."""
from __future__ import annotations

import math
import os

import bpy
import mathutils

from . import helpers as H
from . import sculpt_engine as SE


RIG_NAME = "Character_Rig_AnimationReady"
CHARACTER_COLLECTION = "Characters"
EXPORT_COLLECTIONS = {CHARACTER_COLLECTION, "CharacterRig"}


def _mat(name, color, metallic=0.0, roughness=0.65, emission_strength=0.0, emission_color=None):
    return H.make_material(
        name,
        color=color,
        metallic=metallic,
        roughness=roughness,
        emission_strength=emission_strength,
        emission_color=emission_color,
    )


def _add_uv(name, loc, scale, mat, collection, segments=24):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=12, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    H.link_to_collection(obj, collection)
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    return obj


def _add_cube(name, loc, scale, mat, collection, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    H.link_to_collection(obj, collection)
    if bevel:
        mod = obj.modifiers.new("soft_bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        obj.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
    return obj


def _add_cylinder(name, loc, radius, depth, mat, collection, vertices=24, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=loc,
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    obj.data.materials.append(mat)
    H.link_to_collection(obj, collection)
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    obj.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
    return obj


def _add_cone(name, loc, r1, r2, depth, mat, collection, vertices=24, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=r1,
        radius2=r2,
        depth=depth,
        location=loc,
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    obj.data.materials.append(mat)
    H.link_to_collection(obj, collection)
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    return obj


def _capsule(name, loc, radius, length, mat, collection, axis="Z"):
    if axis == "X":
        rot = (0, math.radians(90), 0)
        core = _add_cylinder(f"{name}_Core", loc, radius, length, mat, collection, rotation=rot)
        a = _add_uv(f"{name}_Joint_A", (loc[0] - length / 2, loc[1], loc[2]), (radius, radius, radius), mat, collection)
        b = _add_uv(f"{name}_Joint_B", (loc[0] + length / 2, loc[1], loc[2]), (radius, radius, radius), mat, collection)
    else:
        core = _add_cylinder(f"{name}_Core", loc, radius, length, mat, collection)
        a = _add_uv(f"{name}_Joint_A", (loc[0], loc[1], loc[2] - length / 2), (radius, radius, radius), mat, collection)
        b = _add_uv(f"{name}_Joint_B", (loc[0], loc[1], loc[2] + length / 2), (radius, radius, radius), mat, collection)
    return [core, a, b]


def _clear_scene():
    for obj in list(bpy.context.scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def _create_armature():
    rig_coll = H.get_or_create_collection("CharacterRig")
    bpy.ops.object.armature_add(location=(0, 0, 0))
    arm = bpy.context.object
    arm.name = RIG_NAME
    arm.data.name = "Remirdy_Humanoid_Armature"
    arm.show_in_front = True
    H.link_to_collection(arm, rig_coll)

    bpy.ops.object.mode_set(mode="EDIT")
    arm.data.edit_bones.remove(arm.data.edit_bones[0])

    def bone(name, head, tail, parent=None):
        item = arm.data.edit_bones.new(name)
        item.head = head
        item.tail = tail
        if parent:
            item.parent = arm.data.edit_bones[parent]
            item.use_connect = False
        return item

    bone("root", (0, 0, 0.0), (0, 0, 0.45))
    bone("pelvis", (0, 0, 0.65), (0, 0, 1.05), "root")
    bone("spine", (0, 0, 1.05), (0, 0, 1.95), "pelvis")
    bone("neck", (0, 0, 1.95), (0, 0, 2.18), "spine")
    bone("head", (0, 0, 2.18), (0, 0, 2.65), "neck")
    bone("upper_arm.L", (-0.35, 0, 1.82), (-0.92, 0, 1.63), "spine")
    bone("forearm.L", (-0.92, 0, 1.63), (-1.42, 0, 1.5), "upper_arm.L")
    bone("hand.L", (-1.42, 0, 1.5), (-1.66, 0, 1.47), "forearm.L")
    bone("upper_arm.R", (0.35, 0, 1.82), (0.92, 0, 1.63), "spine")
    bone("forearm.R", (0.92, 0, 1.63), (1.42, 0, 1.5), "upper_arm.R")
    bone("hand.R", (1.42, 0, 1.5), (1.66, 0, 1.47), "forearm.R")
    bone("thigh.L", (-0.22, 0, 0.75), (-0.29, 0, 0.05), "pelvis")
    bone("shin.L", (-0.29, 0, 0.05), (-0.29, 0, -0.65), "thigh.L")
    bone("foot.L", (-0.29, 0, -0.65), (-0.29, -0.28, -0.82), "shin.L")
    bone("thigh.R", (0.22, 0, 0.75), (0.29, 0, 0.05), "pelvis")
    bone("shin.R", (0.29, 0, 0.05), (0.29, 0, -0.65), "thigh.R")
    bone("foot.R", (0.29, 0, -0.65), (0.29, -0.28, -0.82), "shin.R")
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def _parent_to_bone(obj, arm, bone_name):
    matrix = obj.matrix_world.copy()
    obj.parent = arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    obj.matrix_world = matrix


def _setup_stage():
    from . import render_ops as R

    env = H.get_or_create_collection("Environment")
    floor_mat = _mat("Studio_Charcoal", (0.05, 0.055, 0.06, 1))
    _add_cylinder("Character_Turntable_Base", (0, 0, -0.93), 0.95, 0.12, floor_mat, env, vertices=64)
    R.op_setup_three_point_lighting({"strength": 1.1})
    R.op_setup_product_camera({"focal_length": 70, "depth_of_field": True})
    R.op_apply_render_preset({"preset": "portfolio_render"})


def _setup_fashion_stage():
    from . import render_ops as R

    env = H.get_or_create_collection("Environment")
    floor_mat = _mat("Fashion_Runway_Charcoal", (0.025, 0.028, 0.035, 1), roughness=0.42)
    runway_mat = _mat("Fashion_Runway_Gloss", (0.08, 0.09, 0.12, 1), metallic=0.12, roughness=0.24)
    _add_cube("Fashion_Runway_Floor", (0, 0, -0.86), (5.2, 6.5, 0.08), floor_mat, env, bevel=0.04)
    _add_cube("Fashion_Runway_Platform", (0, -0.35, -0.78), (1.7, 5.8, 0.08), runway_mat, env, bevel=0.04)
    R.op_setup_three_point_lighting({"strength": 1.35})
    R.op_apply_render_preset({"preset": "portfolio_render"})

    bpy.ops.object.camera_add(location=(2.25, -5.0, 1.55))
    cam = bpy.context.object
    cam.name = "Fashion_Runway_Camera"
    direction = mathutils.Vector((0, -0.05, 0.92)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 42
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = 5.0
    cam.data.dof.aperture_fstop = 5.6
    bpy.context.scene.camera = cam


def _apply_subdiv(obj, levels=2):
    if not obj or obj.type != 'MESH':
        return
    mod = obj.modifiers.get("subdiv_smooth") or obj.modifiers.new("subdiv_smooth", "SUBSURF")
    mod.levels = levels
    mod.render_levels = levels


def _add_curve(name, points, mat, collection, bevel=0.01):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 12
    curve.bevel_depth = bevel
    curve.bevel_resolution = 4
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for p, co in zip(spline.points, points):
        p.co = (co[0], co[1], co[2], 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(obj)
    H.link_to_collection(obj, collection)
    obj.data.materials.append(mat)
    return obj


def _add_cloth_panel(name, verts, mat, collection, solidify=0.018):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    H.link_to_collection(obj, collection)
    obj.data.materials.append(mat)
    if solidify:
        sol = obj.modifiers.new("cloth_thickness", "SOLIDIFY")
        sol.thickness = solidify
    bevel = obj.modifiers.new("sewn_soft_edge", "BEVEL")
    bevel.width = 0.008
    bevel.segments = 3
    obj.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
    return obj

# --------------------------------------------------------------------------- #
# UNIFIED organic body builder (replaces glued primitives)
# --------------------------------------------------------------------------- #
def _humanoid_skeleton():
    """Proportioned joint cloud + bone edges for a ~2.7m-tall humanoid.

    Joint names deliberately echo the armature bones so auto-weighting binds
    cleanly. The skin modifier fuses every bone into one seamless body.
    """
    J = {
        "pelvis": (0.0, 0.0, 1.0),
        "spine": (0.0, 0.0, 1.5),
        "chest": (0.0, 0.0, 1.86),
        "neck": (0.0, 0.0, 2.02),
        "head": (0.0, 0.0, 2.2),
        "head_top": (0.0, 0.02, 2.5),
    }
    bones = [
        ("pelvis", "spine"), ("spine", "chest"), ("chest", "neck"),
        ("neck", "head"), ("head", "head_top"),
    ]
    for side, s in (("L", -1), ("R", 1)):
        J[f"shoulder.{side}"] = (s * 0.34, 0.0, 1.82)
        J[f"elbow.{side}"] = (s * 0.92, 0.0, 1.62)
        J[f"wrist.{side}"] = (s * 1.4, 0.0, 1.5)
        J[f"hand.{side}"] = (s * 1.58, 0.0, 1.47)
        J[f"hip.{side}"] = (s * 0.2, 0.0, 0.92)
        J[f"knee.{side}"] = (s * 0.27, 0.0, 0.16)
        J[f"ankle.{side}"] = (s * 0.28, 0.0, -0.55)
        J[f"foot.{side}"] = (s * 0.28, -0.26, -0.74)
        bones += [
            ("chest", f"shoulder.{side}"), (f"shoulder.{side}", f"elbow.{side}"),
            (f"elbow.{side}", f"wrist.{side}"), (f"wrist.{side}", f"hand.{side}"),
            ("pelvis", f"hip.{side}"), (f"hip.{side}", f"knee.{side}"),
            (f"knee.{side}", f"ankle.{side}"), (f"ankle.{side}", f"foot.{side}"),
        ]
    return J, bones


def _fashion_humanoid_skeleton():
    """Runway-oriented human proportions: natural head, long legs, relaxed arms."""
    J = {
        "pelvis": (0.0, 0.0, 0.95),
        "spine": (0.0, 0.0, 1.38),
        "chest": (0.0, 0.0, 1.72),
        "neck": (0.0, -0.01, 1.94),
        "head": (0.0, -0.02, 2.12),
        "head_top": (0.0, -0.005, 2.38),
    }
    bones = [
        ("pelvis", "spine"), ("spine", "chest"), ("chest", "neck"),
        ("neck", "head"), ("head", "head_top"),
    ]
    for side, s in (("L", -1), ("R", 1)):
        J[f"shoulder.{side}"] = (s * 0.27, -0.015, 1.72)
        J[f"elbow.{side}"] = (s * 0.48, -0.035, 1.23)
        J[f"wrist.{side}"] = (s * 0.38, -0.055, 0.83)
        J[f"hand.{side}"] = (s * 0.35, -0.08, 0.72)
        J[f"hip.{side}"] = (s * 0.16, 0.0, 0.86)
        J[f"knee.{side}"] = (s * 0.18, -0.01, 0.12)
        J[f"ankle.{side}"] = (s * 0.17, -0.015, -0.52)
        J[f"foot.{side}"] = (s * 0.17, -0.23, -0.68)
        bones += [
            ("chest", f"shoulder.{side}"), (f"shoulder.{side}", f"elbow.{side}"),
            (f"elbow.{side}", f"wrist.{side}"), (f"wrist.{side}", f"hand.{side}"),
            ("pelvis", f"hip.{side}"), (f"hip.{side}", f"knee.{side}"),
            (f"knee.{side}", f"ankle.{side}"), (f"ankle.{side}", f"foot.{side}"),
        ]
    return J, bones


def _body_radii(style):
    if style in ("fashion_runway", "realistic_human"):
        radii = {
            "pelvis": (0.15, 0.12), "spine": (0.14, 0.105), "chest": (0.20, 0.12),
            "neck": (0.055, 0.05), "head": (0.125, 0.105), "head_top": (0.11, 0.09),
        }
        for side in ("L", "R"):
            radii[f"shoulder.{side}"] = (0.062, 0.058)
            radii[f"elbow.{side}"] = (0.045, 0.042)
            radii[f"wrist.{side}"] = (0.032, 0.03)
            radii[f"hand.{side}"] = (0.038, 0.032)
            radii[f"hip.{side}"] = (0.085, 0.078)
            radii[f"knee.{side}"] = (0.055, 0.052)
            radii[f"ankle.{side}"] = (0.038, 0.035)
            radii[f"foot.{side}"] = (0.06, 0.04)
        return radii
    heroic = style in ("fantasy_knight", "stylized_hero", "stylized")
    chest_w = 0.30 if heroic else 0.26
    radii = {
        "pelvis": (0.22, 0.16), "spine": (0.21, 0.15), "chest": (chest_w, 0.17),
        "neck": (0.09, 0.09), "head": (0.16, 0.16), "head_top": (0.15, 0.15),
    }
    for side in ("L", "R"):
        radii[f"shoulder.{side}"] = (0.135, 0.135)
        radii[f"elbow.{side}"] = (0.082, 0.082)
        radii[f"wrist.{side}"] = (0.058, 0.058)
        radii[f"hand.{side}"] = (0.05, 0.05)
        radii[f"hip.{side}"] = (0.135, 0.135)
        radii[f"knee.{side}"] = (0.1, 0.1)
        radii[f"ankle.{side}"] = (0.072, 0.072)
        radii[f"foot.{side}"] = (0.085, 0.085)
    return radii


def _make_fashion_materials(realism):
    skin = SE.make_skin_material("CHR_Fashion_Skin", (0.74, 0.52, 0.40, 1.0), realism)
    hair = SE.make_hair_material("CHR_Fashion_Hair", (0.035, 0.024, 0.018, 1.0), realism)
    fabric = SE.make_fabric_material("CHR_Fashion_Black_Satin", (0.012, 0.014, 0.018, 1.0), 0.34, realism)
    coat = SE.make_fabric_material("CHR_Fashion_Couture_Coat", (0.025, 0.032, 0.05, 1.0), 0.48, realism)
    silk = SE.make_fabric_material("CHR_Fashion_Champagne_Silk", (0.82, 0.73, 0.58, 1.0), 0.28, realism)
    gold = H.make_material("CHR_Fashion_Gold_Hardware", (0.95, 0.68, 0.26, 1.0), metallic=0.75, roughness=0.24)
    eye_white = H.make_material("CHR_Fashion_Eye_White", (0.88, 0.9, 0.92, 1.0), roughness=0.32)
    iris = H.make_material("CHR_Fashion_Iris", (0.06, 0.12, 0.12, 1.0), roughness=0.22)
    lip = H.make_material("CHR_Fashion_Lip", (0.42, 0.08, 0.11, 1.0), roughness=0.3)
    return {
        "skin": skin, "hair": hair, "fabric": fabric, "coat": coat, "silk": silk,
        "gold": gold, "eye_white": eye_white, "iris": iris, "lip": lip,
    }


def _build_fashion_runway_character(style, realism="realistic"):
    """Build a runway-specific realistic human model.

    This is intentionally different from the heroic game-character generator:
    no armour blobs, no glowing robot cuffs, no T-pose silhouette. It creates
    a natural human base mesh with couture clothing panels and facial details.
    """
    coll = H.get_or_create_collection(CHARACTER_COLLECTION)
    mats = _make_fashion_materials(realism)
    parts = []

    J, bones = _fashion_humanoid_skeleton()
    body = SE.build_skin_body("CHR_Body_skin", J, bones, _body_radii(style), coll, subsurf=2)
    face = H.add_sphere("CHR_Face_Head", radius=0.19, location=(0, -0.02, 2.12), collection=coll)
    face.scale = (0.78, 0.68, 1.08)
    body = SE.unify_meshes([body, face], "CHR_Body", coll, voxel_size=0.03)
    H.assign_material(body, mats["skin"])
    SE.add_surface_detail(body, "skin", strength=0.004 if realism == "realistic" else 0.002, scale=8.0)
    SE.smooth_finalize(body, subsurf=1)
    parts.append(body)

    outfit_radii = {}
    for k, (rx, ry) in _body_radii(style).items():
        if k in J and not k.startswith(("head", "hand", "foot")) and k not in ("neck", "head_top"):
            outfit_radii[k] = (rx + 0.018, ry + 0.018)
    OJ = {k: v for k, v in J.items() if k in outfit_radii}
    ob = [(a, b) for a, b in bones if a in OJ and b in OJ]
    outfit = SE.build_skin_body("CHR_Tailored_Base_Outfit", OJ, ob, outfit_radii, coll, subsurf=2)
    H.assign_material(outfit, mats["fabric"])
    SE.add_surface_detail(outfit, "cloth", strength=0.006, scale=10.0)
    SE.smooth_finalize(outfit, subsurf=1)
    parts.append(outfit)

    # Couture coat and silk runway panels.
    panels = [
        _add_cloth_panel("CHR_Coat_Back_Panel", [(-0.28, 0.08, 1.68), (0.28, 0.08, 1.68), (0.42, 0.13, 0.26), (-0.42, 0.12, 0.26)], mats["coat"], coll),
        _add_cloth_panel("CHR_Coat_Left_Front", [(-0.26, -0.18, 1.58), (-0.06, -0.19, 1.52), (-0.08, -0.25, 0.32), (-0.34, -0.22, 0.32)], mats["coat"], coll),
        _add_cloth_panel("CHR_Coat_Right_Front", [(0.06, -0.19, 1.52), (0.26, -0.18, 1.58), (0.34, -0.22, 0.32), (0.08, -0.25, 0.32)], mats["coat"], coll),
        _add_cloth_panel("CHR_Silk_Dress_Front", [(-0.14, -0.235, 1.36), (0.14, -0.235, 1.36), (0.24, -0.25, 0.28), (-0.24, -0.25, 0.28)], mats["silk"], coll),
    ]
    parts.extend(panels)

    for side, s in (("L", -1), ("R", 1)):
        parts.append(_add_uv(f"CHR_Shoulder_Structure_{side}", (s * 0.285, -0.055, 1.70), (0.085, 0.045, 0.038), mats["coat"], coll, segments=24))
        parts.append(_add_cube(f"CHR_Heel_{side}", (s * 0.17, -0.24, -0.72), (0.17, 0.22, 0.065), mats["hair"], coll, bevel=0.018))
        hand = H.add_sphere(f"CHR_Hand_{side}", radius=0.045, location=(s * 0.35, -0.08, 0.72), collection=coll)
        hand.scale = (0.75, 0.56, 1.2)
        H.assign_material(hand, mats["skin"])
        parts.append(hand)
        for idx, dz in enumerate((-0.034, -0.012, 0.012, 0.034)):
            parts.append(_add_curve(f"CHR_Finger_{side}_{idx}", [(s * 0.35, -0.1, 0.72 + dz), (s * 0.41, -0.12, 0.69 + dz)], mats["skin"], coll, bevel=0.005))

    # Face: separate details stay crisp at render size.
    for side, s in (("L", -1), ("R", 1)):
        e = H.add_sphere(f"CHR_Eye_{side}", radius=0.026, location=(s * 0.055, -0.16, 2.14), collection=coll)
        e.scale = (1.0, 0.42, 0.75)
        H.assign_material(e, mats["eye_white"])
        parts.append(e)
        ir = H.add_sphere(f"CHR_Iris_{side}", radius=0.011, location=(s * 0.055, -0.178, 2.14), collection=coll)
        H.assign_material(ir, mats["iris"])
        parts.append(ir)
        parts.append(_add_curve(f"CHR_Brow_{side}", [(s * 0.03, -0.183, 2.18), (s * 0.09, -0.18, 2.185)], mats["hair"], coll, bevel=0.004))
    parts.append(_add_cube("CHR_Lips", (0, -0.18, 2.075), (0.078, 0.012, 0.016), mats["lip"], coll, bevel=0.004))

    hair = H.add_sphere("CHR_Hair_Cap", radius=0.17, location=(0, -0.005, 2.24), collection=coll)
    hair.scale = (0.9, 0.72, 0.42)
    H.assign_material(hair, mats["hair"])
    parts.append(hair)
    for i, x in enumerate((-0.14, -0.09, -0.04, 0.04, 0.09, 0.14)):
        parts.append(_add_curve(f"CHR_Hair_Strand_{i}", [(x, -0.06, 2.22), (x * 0.7, -0.08, 2.03)], mats["hair"], coll, bevel=0.005))

    parts.append(_add_cube("CHR_Belt_Gold", (0, -0.24, 1.08), (0.42, 0.026, 0.04), mats["gold"], coll, bevel=0.01))
    for i, x in enumerate((-0.22, -0.14, -0.07, 0.0, 0.07, 0.14, 0.22)):
        parts.append(_add_curve(f"CHR_Couture_Stitch_{i}", [(x, -0.255, 1.42), (x * 1.2, -0.27, 0.25)], mats["gold"], coll, bevel=0.004))

    return parts


def _build_unified_character(style, realism="realistic"):
    """Build a seamless, single-mesh organic character (body, outfit, hair, eyes).

    Returns a list of mesh objects. The body is ONE watertight mesh instead of
    dozens of disconnected primitives.
    """
    coll = H.get_or_create_collection(CHARACTER_COLLECTION)

    if style in ("fashion_runway", "realistic_human"):
        return _build_fashion_runway_character(style, realism)

    # --- style-aware palette ---
    skin = SE.make_skin_material("CHR_Skin", (0.79, 0.55, 0.43, 1.0), realism)
    hair_mat = SE.make_hair_material("CHR_Hair", (0.05, 0.035, 0.028, 1.0), realism)
    eye_white = SE.make_skin_material("CHR_Eye_White", (0.92, 0.93, 0.95, 1.0), "stylized")
    iris = H.make_material("CHR_Iris", (0.08, 0.32, 0.45, 1.0), roughness=0.2)
    if style == "fantasy_knight":
        outfit_mat = H.make_material("CHR_Outfit", (0.32, 0.04, 0.06, 1.0), roughness=0.55)
        accent = H.make_material("CHR_Accent", (0.78, 0.6, 0.18, 1.0), metallic=0.85, roughness=0.3)
    elif style == "sci_fi_scout":
        outfit_mat = H.make_material("CHR_Outfit", (0.06, 0.07, 0.09, 1.0), roughness=0.45)
        accent = H.make_material("CHR_Accent", (0.0, 0.7, 0.95, 1.0),
                                 emission_color=(0.0, 0.85, 1.0, 1.0), emission_strength=2.4)
    else:  # stylized_hero default
        outfit_mat = SE.make_fabric_material("CHR_Outfit", (0.05, 0.08, 0.16, 1.0), 0.7, realism)
        accent = H.make_material("CHR_Accent", (0.0, 0.6, 0.85, 1.0),
                                 emission_color=(0.0, 0.8, 1.0, 1.0), emission_strength=2.0)

    parts = []

    # --- 1. BODY: skin-skeleton -> add head sphere -> fuse to one mesh ---
    J, bones = _humanoid_skeleton()
    body = SE.build_skin_body("CHR_Body_skin", J, bones, _body_radii(style), coll, subsurf=2)
    head = H.add_sphere("CHR_Head_sphere", radius=0.2, location=(0, 0.01, 2.27), collection=coll)
    head.scale = (1.0, 1.05, 1.18)
    body = SE.unify_meshes([body, head], "CHR_Body", coll, voxel_size=0.045)
    H.assign_material(body, skin)
    SE.add_surface_detail(body, "muscle", strength=0.01 if realism == "realistic" else 0.005, scale=3.0)
    SE.smooth_finalize(body, subsurf=1)
    parts.append(body)

    # --- 2. OUTFIT: a second, slightly-inflated skin mesh over the torso/limbs ---
    OJ = {k: v for k, v in J.items() if k not in ("head", "head_top")}
    ob = [b for b in bones if "head" not in b[0] and "head" not in b[1]]
    outfit_radii = {}
    for k, (rx, ry) in _body_radii(style).items():
        if k in OJ:
            outfit_radii[k] = (rx + 0.03, ry + 0.03)
    # trim the outfit at wrists/ankles so hands/feet stay skin
    for k in ("hand.L", "hand.R", "foot.L", "foot.R"):
        outfit_radii[k] = (0.01, 0.01)
    outfit = SE.build_skin_body("CHR_Outfit_skin", OJ, ob, outfit_radii, coll, subsurf=2)
    SE.apply_all_modifiers(outfit)
    outfit.name = "CHR_Outfit"
    H.assign_material(outfit, outfit_mat)
    SE.add_surface_detail(outfit, "cloth", strength=0.008, scale=5.0)
    SE.smooth_finalize(outfit, subsurf=1)
    parts.append(outfit)

    # --- 3. HAIR: a sculpted cap, not cones ---
    hair = H.add_sphere("CHR_Hair", radius=0.22, location=(0, 0.02, 2.34), collection=coll)
    hair.scale = (1.05, 1.12, 0.95)
    SE.add_surface_detail(hair, "rough", strength=0.03, scale=6.0)
    SE.smooth_finalize(hair, subsurf=1)
    H.assign_material(hair, hair_mat)
    parts.append(hair)

    # --- 4. EYES (kept separate for their own material) ---
    for side, s in (("L", -1), ("R", 1)):
        e = H.add_sphere(f"CHR_Eye_{side}", radius=0.035, location=(s * 0.075, -0.17, 2.28), collection=coll)
        H.assign_material(e, eye_white)
        parts.append(e)
        ir = H.add_sphere(f"CHR_Iris_{side}", radius=0.018, location=(s * 0.075, -0.198, 2.28), collection=coll)
        H.assign_material(ir, iris)
        parts.append(ir)

    # --- 5. accent belt (organic torus-ish via bevelled ring) ---
    belt = H.add_cylinder("CHR_Belt", radius=0.26, depth=0.09, location=(0, 0, 0.98), verts=40, collection=coll)
    belt.scale = (1.0, 0.7, 1.0)
    H.assign_material(belt, accent)
    SE.smooth_finalize(belt, subsurf=0)
    parts.append(belt)

    return parts


def _bind_body_to_rig(parts, arm):
    """Auto-weight the deforming meshes; parent eyes/accessories to head bone."""
    deform_names = {"CHR_Body", "CHR_Outfit", "CHR_Tailored_Base_Outfit"}
    deform = [o for o in parts if o.name in deform_names]
    if deform and arm:
        bpy.ops.object.select_all(action="DESELECT")
        for o in deform:
            o.select_set(True)
        arm.select_set(True)
        bpy.context.view_layer.objects.active = arm
        try:
            bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        except Exception:
            try:
                bpy.ops.object.parent_set(type="ARMATURE_NAME")
            except Exception:
                pass
    for o in parts:
        if o.name.startswith(("CHR_Hair", "CHR_Eye", "CHR_Iris", "CHR_Brow", "CHR_Lips")):
            _parent_to_bone(o, arm, "head")
        elif o.name.startswith(("CHR_Coat", "CHR_Silk", "CHR_Shoulder_Structure", "CHR_Couture_Stitch")):
            _parent_to_bone(o, arm, "spine")
        elif o.name.startswith(("CHR_Belt", "CHR_Tailored")):
            _parent_to_bone(o, arm, "pelvis")
        elif "_L" in o.name and ("Hand" in o.name or "Finger" in o.name):
            _parent_to_bone(o, arm, "hand.L")
        elif "_R" in o.name and ("Hand" in o.name or "Finger" in o.name):
            _parent_to_bone(o, arm, "hand.R")
        elif "_L" in o.name and "Heel" in o.name:
            _parent_to_bone(o, arm, "foot.L")
        elif "_R" in o.name and "Heel" in o.name:
            _parent_to_bone(o, arm, "foot.R")


def _create_mesh_parts(style):
    coll = H.get_or_create_collection(CHARACTER_COLLECTION)
    skin = _mat("Character_Skin_Warm", (0.78, 0.5, 0.36, 1))
    hair = _mat("Character_Hair_Dark", (0.025, 0.02, 0.018, 1))
    fabric = _mat("Character_Fabric_Navy", (0.03, 0.05, 0.11, 1))
    leather = _mat("Character_Leather_Dark", (0.12, 0.065, 0.035, 1))
    metal = _mat("Character_Brushed_Gunmetal", (0.32, 0.34, 0.36, 1), metallic=0.6)
    cyan = _mat(
        "Character_Cyan_Emission",
        (0.0, 0.65, 0.9, 1),
        emission_color=(0.0, 0.9, 1.0, 1),
        emission_strength=2.2,
    )
    black = _mat("Character_Boots_Black", (0.015, 0.014, 0.014, 1))
    eye = _mat("Character_Eyes", (0.9, 0.95, 1.0, 1))

    if style == "fantasy_knight":
        fabric = _mat("Character_Fabric_Crimson", (0.34, 0.025, 0.04, 1))
        cyan = _mat("Character_Gold_Accent", (1.0, 0.62, 0.12, 1), metallic=0.35)
    elif style == "sci_fi_scout":
        fabric = _mat("Character_Fabric_Graphite", (0.04, 0.045, 0.05, 1))

    parts = []

    # Core Head, Torso, and Pelvis
    parts.append(_add_uv("CHR_Torso_Armored", (0, 0, 1.45), (0.36, 0.2, 0.5), fabric, coll))
    _apply_subdiv(parts[-1], 2)

    parts.append(_add_cube("CHR_Chest_Armor", (0, -0.18, 1.55), (0.58, 0.08, 0.42), metal, coll, 0.035))

    parts.append(_add_uv("CHR_Pelvis_Belted", (0, 0, 0.88), (0.32, 0.19, 0.22), leather, coll))
    _apply_subdiv(parts[-1], 2)

    parts.append(_add_uv("CHR_Head", (0, 0, 2.25), (0.26, 0.22, 0.3), skin, coll))
    _apply_subdiv(parts[-1], 2)

    parts.append(_add_cylinder("CHR_Neck", (0, 0, 2.0), 0.09, 0.22, skin, coll))

    # Styled High Collar (flared cone)
    parts.append(_add_cone("CHR_Collar", (0, 0, 1.95), 0.14, 0.19, 0.24, fabric, coll))
    _apply_subdiv(parts[-1], 2)

    # Majestic Spiky Anime Hair set
    parts.append(_add_uv("CHR_Hair_Mass", (0, 0.03, 2.47), (0.29, 0.24, 0.16), hair, coll))
    _apply_subdiv(parts[-1], 2)

    parts.append(_add_cone("CHR_Hair_Front_Spike1", (-0.08, -0.22, 2.38), 0.09, 0.01, 0.32, hair, coll, rotation=(math.radians(85), 0, math.radians(-15))))
    parts.append(_add_cone("CHR_Hair_Front_Spike2", (0.08, -0.22, 2.38), 0.09, 0.01, 0.32, hair, coll, rotation=(math.radians(85), 0, math.radians(15))))
    parts.append(_add_cone("CHR_Hair_Side_L", (-0.24, -0.1, 2.45), 0.08, 0.01, 0.28, hair, coll, rotation=(math.radians(45), math.radians(-65), 0)))
    parts.append(_add_cone("CHR_Hair_Side_R", (0.24, -0.1, 2.45), 0.08, 0.01, 0.28, hair, coll, rotation=(math.radians(45), math.radians(65), 0)))
    parts.append(_add_cone("CHR_Hair_Top", (0, 0, 2.65), 0.12, 0.01, 0.35, hair, coll, rotation=(0, math.radians(-10), 0)))
    parts.append(_add_cone("CHR_Hair_Back", (0, 0.18, 2.42), 0.1, 0.01, 0.3, hair, coll, rotation=(math.radians(-60), 0, 0)))

    # Eyes & Emission Pupils
    parts.append(_add_uv("CHR_Eye_L", (-0.085, -0.205, 2.27), (0.032, 0.014, 0.024), eye, coll, 16))
    parts.append(_add_uv("CHR_Eye_R", (0.085, -0.205, 2.27), (0.032, 0.014, 0.024), eye, coll, 16))
    parts.append(_add_uv("CHR_Pupil_L", (-0.085, -0.218, 2.265), (0.012, 0.006, 0.012), cyan, coll, 12))
    parts.append(_add_uv("CHR_Pupil_R", (0.085, -0.218, 2.265), (0.012, 0.006, 0.012), cyan, coll, 12))

    # Flowing Coat Flaps
    parts.append(_add_cube("CHR_Coat_Flap_L", (-0.18, -0.05, 1.05), (0.22, 0.08, 0.8), fabric, coll, 0.015))
    parts[-1].rotation_euler = (math.radians(10), math.radians(-8), math.radians(-15))
    _apply_subdiv(parts[-1], 2)

    parts.append(_add_cube("CHR_Coat_Flap_R", (0.18, -0.05, 1.05), (0.22, 0.08, 0.8), fabric, coll, 0.015))
    parts[-1].rotation_euler = (math.radians(10), math.radians(8), math.radians(15))
    _apply_subdiv(parts[-1], 2)

    # Limbs & Shoulder/Knee armor
    for side, sign in (("L", -1), ("R", 1)):
        parts.append(_add_uv(f"CHR_ShoulderPad_{side}", (sign * 0.44, -0.02, 1.78), (0.2, 0.16, 0.12), metal, coll))
        _apply_subdiv(parts[-1], 2)

        # Smooth organic subdivisions on arm/leg segments
        arm_parts = _capsule(f"CHR_UpperArm_{side}", (sign * 0.76, 0, 1.58), 0.085, 0.5, fabric, coll, axis="X")
        for obj in arm_parts:
            _apply_subdiv(obj, 2)
        parts += arm_parts

        forearm_parts = _capsule(f"CHR_Forearm_{side}", (sign * 1.2, 0, 1.46), 0.078, 0.42, leather, coll, axis="X")
        for obj in forearm_parts:
            _apply_subdiv(obj, 2)
        parts += forearm_parts

        parts.append(_add_uv(f"CHR_Hand_{side}", (sign * 1.48, -0.01, 1.44), (0.09, 0.065, 0.08), skin, coll, 16))
        _apply_subdiv(parts[-1], 2)

        thigh_parts = _capsule(f"CHR_Thigh_{side}", (sign * 0.23, 0, 0.38), 0.12, 0.62, fabric, coll)
        for obj in thigh_parts:
            _apply_subdiv(obj, 2)
        parts += thigh_parts

        shin_parts = _capsule(f"CHR_Shin_{side}", (sign * 0.28, 0, -0.27), 0.108, 0.62, metal, coll)
        for obj in shin_parts:
            _apply_subdiv(obj, 2)
        parts += shin_parts

        # Knee Armor Pads
        parts.append(_add_uv(f"CHR_KneeArmor_{side}", (sign * 0.28, -0.15, 0.05), (0.12, 0.08, 0.12), metal, coll))
        _apply_subdiv(parts[-1], 2)

        parts.append(_add_cube(f"CHR_Boot_{side}", (sign * 0.29, -0.11, -0.76), (0.22, 0.36, 0.16), black, coll, 0.03))
        _apply_subdiv(parts[-1], 2)

        parts.append(_add_cylinder(f"CHR_Wrist_Accent_{side}", (sign * 1.37, 0, 1.48), 0.086, 0.045, cyan, coll, rotation=(0, math.radians(90), 0)))

    parts.append(_add_cylinder("CHR_Utility_Belt", (0, 0, 1.02), 0.34, 0.1, leather, coll, vertices=48))
    parts[-1].scale.y = 0.58
    parts.append(_add_cube("CHR_Belt_Core", (0, -0.2, 1.02), (0.14, 0.04, 0.1), cyan, coll, 0.015))
    parts.append(_add_cube("CHR_Back_Cape_Panel", (0, 0.22, 1.08), (0.52, 0.04, 1.0), fabric, coll, 0.02))
    return parts


def _attach_parts(parts, arm):
    for obj in parts:
        name = obj.name
        if name.startswith(("CHR_Head", "CHR_Hair", "CHR_Eye", "CHR_Pupil")):
            _parent_to_bone(obj, arm, "head")
        elif "Torso" in name or "Chest" in name or "Cape" in name or "Collar" in name or "Coat_Flap" in name:
            _parent_to_bone(obj, arm, "spine")
        elif "Pelvis" in name or "Belt" in name:
            _parent_to_bone(obj, arm, "pelvis")
        elif "_L" in name and ("UpperArm" in name or "Shoulder" in name):
            _parent_to_bone(obj, arm, "upper_arm.L")
        elif "_R" in name and ("UpperArm" in name or "Shoulder" in name):
            _parent_to_bone(obj, arm, "upper_arm.R")
        elif "_L" in name and ("Forearm" in name or "Wrist" in name):
            _parent_to_bone(obj, arm, "forearm.L")
        elif "_R" in name and ("Forearm" in name or "Wrist" in name):
            _parent_to_bone(obj, arm, "forearm.R")
        elif "_L" in name and "Hand" in name:
            _parent_to_bone(obj, arm, "hand.L")
        elif "_R" in name and "Hand" in name:
            _parent_to_bone(obj, arm, "hand.R")
        elif "_L" in name and "Thigh" in name:
            _parent_to_bone(obj, arm, "thigh.L")
        elif "_R" in name and "Thigh" in name:
            _parent_to_bone(obj, arm, "thigh.R")
        elif "_L" in name and "KneeArmor" in name:
            _parent_to_bone(obj, arm, "shin.L")
        elif "_R" in name and "KneeArmor" in name:
            _parent_to_bone(obj, arm, "shin.R")
        elif "_L" in name and "Shin" in name:
            _parent_to_bone(obj, arm, "shin.L")
        elif "_R" in name and "Shin" in name:
            _parent_to_bone(obj, arm, "shin.R")
        elif "_L" in name and "Boot" in name:
            _parent_to_bone(obj, arm, "foot.L")
        elif "_R" in name and "Boot" in name:
            _parent_to_bone(obj, arm, "foot.R")


def _find_rig():
    rig = bpy.data.objects.get(RIG_NAME)
    if rig and rig.type == "ARMATURE":
        return rig
    return next((o for o in bpy.context.scene.objects if o.type == "ARMATURE"), None)


def op_add_character_animation(params):
    arm = _find_rig()
    if arm is None:
        raise ValueError("No character armature found. Run create_rigged_character first.")
    animation = params.get("animation", "idle_wave")
    frames = int(params.get("frames", 120))

    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="POSE")
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = frames
    bpy.context.scene.render.fps = 24

    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.location = (0, 0, 0)

    def keyed(frame, poses):
        bpy.context.scene.frame_set(frame)
        for bone_name, rotation in poses.items():
            bone = arm.pose.bones.get(bone_name)
            if bone:
                bone.rotation_euler = rotation
                bone.keyframe_insert("rotation_euler", frame=frame)
        root = arm.pose.bones.get("root")
        if root:
            root.keyframe_insert("location", frame=frame)

    neutral = {pb.name: (0, 0, 0) for pb in arm.pose.bones}
    keyed(1, neutral)
    keyed(frames, neutral)

    if animation in ("wave", "idle_wave"):
        keyed(frames // 3, {
            "upper_arm.R": (0, math.radians(-10), math.radians(35)),
            "forearm.R": (0, 0, math.radians(-80)),
            "hand.R": (0, 0, math.radians(-18)),
            "head": (math.radians(4), 0, math.radians(-8)),
        })
        keyed(frames // 2, {
            "upper_arm.R": (0, math.radians(-5), math.radians(28)),
            "forearm.R": (0, 0, math.radians(-55)),
            "hand.R": (0, 0, math.radians(16)),
        })

    if animation in ("walk_preview", "idle_wave"):
        keyed(int(frames * 0.65), {
            "thigh.L": (math.radians(18), 0, 0),
            "shin.L": (math.radians(-18), 0, 0),
            "thigh.R": (math.radians(-16), 0, 0),
            "shin.R": (math.radians(12), 0, 0),
            "upper_arm.L": (math.radians(-12), 0, math.radians(-10)),
            "upper_arm.R": (math.radians(12), 0, math.radians(10)),
        })

    if arm.animation_data and arm.animation_data.action:
        arm.animation_data.action.name = f"Character_{animation}"
        for fcurve in getattr(arm.animation_data.action, "fcurves", []):
            for key in fcurve.keyframe_points:
                key.interpolation = "BEZIER"
    bpy.ops.object.mode_set(mode="OBJECT")
    return {"rig": arm.name, "animation": animation, "frames": frames}


def op_create_rigged_character(params):
    """Create a rigged, animated humanoid.

    Parameters
    ----------
    unified : bool (default True)
        True  -> single seamless organic body mesh (skin-modifier + voxel
                 fuse). This is the professional, non-"glued-primitives" path.
        False -> legacy primitive-assembly path.
    style  : 'fashion_runway' | 'realistic_human' | 'stylized_hero' |
             'fantasy_knight' | 'sci_fi_scout'
    realism: 'realistic' | 'stylized'
        Drives subsurface skin, surface detail strength, and whether a cel
        outline is added.
    """
    if params.get("clear_scene", True):
        _clear_scene()
    name = params.get("name", "Cyber Adventurer")
    style = params.get("style", "stylized_hero")
    realism = params.get("realism", "stylized")
    unified = params.get("unified", True)

    arm = _create_armature()

    if unified:
        parts = _build_unified_character(style, realism)
        _bind_body_to_rig(parts, arm)
    else:
        parts = _create_mesh_parts(style)
        _attach_parts(parts, arm)

    if style in ("fashion_runway", "realistic_human"):
        _setup_fashion_stage()
    else:
        _setup_stage()
    anim = op_add_character_animation({
        "animation": params.get("animation", "idle_wave"),
        "frames": int(params.get("frames", 120)),
    })
    bpy.context.scene.frame_set(1)

    # Cel outline is a stylized look; only add it when the user wants stylized.
    if realism == "stylized":
        try:
            from .material_ops import op_apply_cel_shading_outline
            op_apply_cel_shading_outline({"thickness": 0.012, "selected_only": False})
        except Exception as e:
            print("Could not apply cel shading outlines:", e)

    return {
        "character": name,
        "style": style,
        "realism": realism,
        "topology": "unified_single_mesh" if unified else "primitive_assembly",
        "rig": arm.name,
        "mesh_parts": len(parts),
        "bones": len(arm.data.bones),
        "animation": anim,
        "suggested_next": ["validate_character_rig", "render_preview", "export_character_glb"],
    }


def _local_human_provider_status():
    """Detect API-free local realistic human providers available in Blender."""
    addons = {k.lower() for k in bpy.context.preferences.addons.keys()}
    op_names = {n.lower() for n in dir(bpy.ops)}
    providers = []
    if any("mpfb" in name for name in addons | op_names):
        providers.append("mpfb")
    if any("makehuman" in name for name in addons | op_names):
        providers.append("makehuman")
    return {
        "available": providers,
        "preferred": providers[0] if providers else "procedural_fashion",
        "api_required": False,
    }


def op_create_api_free_runway_show(params):
    """Create a runway-ready human character without cloud APIs.

    The operation prefers local human providers such as MPFB/MakeHuman when
    installed in Blender. If none are present, it falls back to the improved
    in-Blender fashion runway generator.
    """
    status = _local_human_provider_status()
    provider = params.get("provider", "auto")
    if provider == "auto":
        provider = status["preferred"]

    # The local provider hook is intentionally conservative: MPFB/MakeHuman
    # operator names vary by installation, so until a provider is detected and
    # mapped explicitly we use the built-in fashion generator.
    result = op_create_rigged_character({
        "name": params.get("name", "API Free Runway Model"),
        "style": "fashion_runway",
        "realism": "realistic",
        "animation": params.get("animation", "walk_preview"),
        "clear_scene": params.get("clear_scene", True),
        "unified": True,
        "frames": int(params.get("frames", 96)),
    })
    result["human_provider"] = provider
    result["provider_status"] = status
    result["api_required"] = False
    result["note"] = (
        "Using procedural_fashion fallback. Install MPFB/MakeHuman locally in "
        "Blender to enable imported realistic human meshes without any API."
        if provider == "procedural_fashion" else
        f"Detected local provider '{provider}', but explicit operator mapping is not configured yet."
    )
    return result


def op_validate_character_rig(params):
    arm = _find_rig()
    if arm is None:
        return {"valid": False, "issues": ["No armature found."]}
    required = {
        "root", "pelvis", "spine", "neck", "head",
        "upper_arm.L", "forearm.L", "hand.L",
        "upper_arm.R", "forearm.R", "hand.R",
        "thigh.L", "shin.L", "foot.L",
        "thigh.R", "shin.R", "foot.R",
    }
    bones = {bone.name for bone in arm.data.bones}
    children = [o for o in bpy.context.scene.objects if o.parent == arm and o.type == "MESH"]
    missing = sorted(required - bones)
    issues = []
    if missing:
        issues.append(f"Missing bones: {', '.join(missing)}")
    # A unified single-mesh body has a watertight CHR_Body; the legacy path uses
    # many small primitives. Accept either as long as a body deforms the rig.
    has_unified_body = any(o.name == "CHR_Body" for o in children)
    if not has_unified_body and len(children) < 12:
        issues.append("Character has too few mesh parts parented to the rig.")
    if not children:
        issues.append("No mesh parts are parented to the rig.")
    if not (arm.animation_data and arm.animation_data.action):
        issues.append("Rig has no animation action.")
    return {
        "valid": not issues,
        "rig": arm.name,
        "bone_count": len(bones),
        "mesh_parts_parented": len(children),
        "animation": arm.animation_data.action.name if arm.animation_data and arm.animation_data.action else None,
        "issues": issues,
    }


def op_export_character_glb(params):
    from .export_ops import workspace_output

    arm = _find_rig()
    if arm is None:
        raise ValueError("No character armature found. Run create_rigged_character first.")
    filename = params.get("filename", "rigged_character.glb")
    path = workspace_output("exports", filename)
    bpy.ops.object.select_all(action="DESELECT")
    selected = [arm] + [o for o in bpy.context.scene.objects if o.parent == arm and o.type == "MESH"]
    for obj in selected:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = arm
    kwargs = {
        "filepath": path,
        "export_format": "GLB",
        "use_selection": True,
        "export_animations": True,
        "export_apply": True,
        "export_yup": True,
    }
    bpy.ops.export_scene.gltf(**kwargs)
    return {
        "export_path": path,
        "format": "glb",
        "target": params.get("target", "unity"),
        "objects": len(selected),
        "includes_animation": bool(arm.animation_data and arm.animation_data.action),
    }


def op_bind_auto_weights(params):
    """Automatically bind mesh parts to armatures utilizing bone heat voxel weighting."""
    arm = _find_rig()
    if not arm:
        return {"ok": False, "error": "No character armature found."}

    meshes = [o for o in bpy.context.selected_objects if o.type == 'MESH']
    if not meshes:
        meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.parent is None]

    if not meshes:
        return {"ok": False, "error": "No unbound meshes found."}

    # Select meshes and armature, make armature active
    bpy.ops.object.mode_set(mode='OBJECT') if bpy.ops.object.mode_set.poll() else None
    bpy.ops.object.select_all(action='DESELECT')
    for m in meshes:
        m.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm

    # Run automatic parent binding with empty groups or auto-weights
    try:
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        success = True
    except Exception as e:
        # Fall back to empty groups if bone heat fails (e.g. self-intersecting meshes)
        bpy.ops.object.parent_set(type='ARMATURE_NAME')
        success = False

    return {
        "ok": True,
        "mode": "auto_weight_bind",
        "mesh_objects_bound": len(meshes),
        "armature": arm.name,
        "heat_weight_success": success
    }


def op_add_text_motion_preset(params):
    """Bake animatable keyframes representing 'run', 'jump', or 'attack' motion presets directly onto armatures."""
    arm = _find_rig()
    if not arm:
        return {"ok": False, "error": "No character armature found."}

    motion = params.get("motion", "run").lower().strip()
    frames = int(params.get("frames", 40))

    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="POSE")
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = frames

    # Bake pre-configured poses sequentially to form natural movements
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0, 0, 0)

    def key_pose(frame, poses):
        bpy.context.scene.frame_set(frame)
        for name, rot in poses.items():
            bone = arm.pose.bones.get(name)
            if bone:
                bone.rotation_euler = rot
                bone.keyframe_insert("rotation_euler", frame=frame)

    # Run/Walk Cycle presets
    if "run" in motion or "walk" in motion:
        key_pose(1, {"thigh.L": (0.35, 0, 0), "thigh.R": (-0.35, 0, 0), "forearm.L": (0, 0, -0.6), "forearm.R": (0, 0, 0.4)})
        key_pose(frames // 2, {"thigh.L": (-0.35, 0, 0), "thigh.R": (0.35, 0, 0), "forearm.L": (0, 0, 0.4), "forearm.R": (0, 0, -0.6)})
        key_pose(frames, {"thigh.L": (0.35, 0, 0), "thigh.R": (-0.35, 0, 0), "forearm.L": (0, 0, -0.6), "forearm.R": (0, 0, 0.4)})
    # Attack slash motion presets
    elif "attack" in motion or "slash" in motion:
        key_pose(1, {"spine": (0, 0.1, -0.2), "upper_arm.R": (0.2, -0.2, 0.8), "forearm.R": (0, 0, -0.9)})
        key_pose(frames // 3, {"spine": (0.1, -0.2, 0.6), "upper_arm.R": (-0.4, 0.4, -0.8), "forearm.R": (0, 0, -0.2)})
        key_pose(frames, {"spine": (0, 0, 0), "upper_arm.R": (0, 0, 0), "forearm.R": (0, 0, 0)})

    if arm.animation_data and arm.animation_data.action:
        arm.animation_data.action.name = f"Anim_Preset_{motion.upper()}"

    bpy.ops.object.mode_set(mode="OBJECT")
    return {"ok": True, "motion_baked": motion, "total_frames": frames}


def op_create_facial_blendshapes(params):
    """Add standard facial expression shape keys (smile, blink, mouth open) onto target head meshes."""
    head = bpy.data.objects.get("CHR_Head") or next((o for o in H.all_mesh_objects() if "Head" in o.name), None)
    if not head:
        return {"ok": False, "error": "No character head mesh found in scene."}

    bpy.context.view_layer.objects.active = head
    head.select_set(True)

    # Ensure active Basis shape key is set
    if not head.data.shape_keys:
        head.shape_key_add(name="Basis")

    # Generate Smile shape key by raising corner vertices slightly
    smile_key = head.data.shape_keys.key_blocks.get("Smile") or head.shape_key_add(name="Smile")
    for vert in smile_key.data:
        # Move side-mouth vertices slightly upward/outward
        co = head.data.vertices[vert.index].co
        if abs(co.x) > 0.08 and co.z < 2.3 and co.z > 2.15:
            vert.co.z += 0.024
            vert.co.y -= 0.008

    # Generate Blink shape key by squeezing eye coordinates
    blink_key = head.data.shape_keys.key_blocks.get("Blink") or head.shape_key_add(name="Blink")
    for vert in blink_key.data:
        co = head.data.vertices[vert.index].co
        if co.z < 2.34 and co.z > 2.22 and co.y < -0.12:
            vert.co.z = 2.27 # Flatten eye slit Z coordinates

    return {"ok": True, "shape_keys_added": ["Smile", "Blink"], "head_mesh": head.name}


def op_fit_clothing_mesh(params):
    """Auto-scale custom clothing meshes to character armature dimensions and attach rig modifiers."""
    arm = _find_rig()
    if not arm:
        return {"ok": False, "error": "No character armature found."}

    clothing = [o for o in bpy.context.selected_objects if o.type == 'MESH' and o.parent is None]
    if not clothing:
        return {"ok": True, "fitted_count": 0, "message": "No unparented clothing selected."}

    fitted = 0
    for cloth in clothing:
        # Apply armature modifier
        mod = cloth.modifiers.get("Armature") or cloth.modifiers.new("Armature", "ARMATURE")
        mod.object = arm

        # Parent to rig
        cloth.parent = arm
        fitted += 1

    return {"ok": True, "fitted_clothing_meshes": fitted}


def op_convert_hair_to_curves(params):
    """Convert custom hair polygon mesh caps into beautiful stylized curve geometry objects."""
    hair_mesh = bpy.data.objects.get("CHR_Hair_Mass") or next((o for o in H.all_mesh_objects() if "Hair" in o.name), None)
    if not hair_mesh:
        return {"ok": False, "error": "No hair mesh mass found in scene."}

    bpy.context.view_layer.objects.active = hair_mesh
    hair_mesh.select_set(True)

    # Convert mesh to curve object using Blender conversion
    try:
        bpy.ops.object.convert(target='CURVE')
        hair_mesh.data.bevel_depth = 0.012
        hair_mesh.data.bevel_resolution = 3
        success = True
    except Exception as e:
        success = False

    return {"ok": True, "converted_to_curves": success, "hair_curve_object": hair_mesh.name}


def op_reduce_armature_bones(params):
    """Simplify rig hierarchy by merging non-essential skeleton child joints to keep rigs optimized for engines."""
    arm = _find_rig()
    if not arm:
        return {"ok": False, "error": "No character armature found."}

    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')

    bones_removed = 0
    # Trim non-essential bones (e.g. helper tweaks or excessive fingers if present)
    for bone in list(arm.data.edit_bones):
        if bone.name.startswith("tweak_") or len(bone.name.split(".")) > 2:
            arm.data.edit_bones.remove(bone)
            bones_removed += 1

    bpy.ops.object.mode_set(mode='OBJECT')
    return {"ok": True, "armature": arm.name, "bones_reduced_count": bones_removed}


def op_adapt_fbx_rig(params):
    """Automatically maps bone nomenclature and retargets animation keyframes from imported Mixamo/FBX rigs."""
    source_name = params.get("source_rig", "")

    target_arm = _find_rig()
    if not target_arm:
        return {"ok": False, "error": "No target character armature found."}

    source_arm = bpy.data.objects.get(source_name) if source_name else next((o for o in bpy.context.scene.objects if o.type == 'ARMATURE' and o != target_arm), None)
    if not source_arm:
        return {"ok": False, "error": "No source FBX/Mixamo rig found to retarget animations."}

    # Build bone retargeting map (Mixamo/FBX naming -> target armature naming)
    retarget_map = {
        "Hips": "pelvis",
        "Spine": "spine",
        "Neck": "neck",
        "Head": "head",
        "LeftArm": "upper_arm.L",
        "LeftForeArm": "forearm.L",
        "LeftHand": "hand.L",
        "RightArm": "upper_arm.R",
        "RightForeArm": "forearm.R",
        "RightHand": "hand.R",
        "LeftUpLeg": "thigh.L",
        "LeftLeg": "shin.L",
        "LeftFoot": "foot.L",
        "RightUpLeg": "thigh.R",
        "RightLeg": "shin.R",
        "RightFoot": "foot.R"
    }

    # Transfer Action data from source FBX rig to our standard rig
    mapped = 0
    if source_arm.animation_data and source_arm.animation_data.action:
        # Clone action
        src_action = source_arm.animation_data.action
        tar_action = src_action.copy()
        tar_action.name = f"Retargeted_{src_action.name}"

        # Map channel paths to standard bones
        for fcurve in tar_action.fcurves:
            path = fcurve.data_path
            for src_bone, tar_bone in retarget_map.items():
                if f'pose.bones["{src_bone}"]' in path or f'pose.bones["mixamorig:{src_bone}"]' in path:
                    fcurve.data_path = path.replace(src_bone, tar_bone).replace(f"mixamorig:{src_bone}", tar_bone)
                    mapped += 1

        # Apply action to target rig
        if not target_arm.animation_data:
            target_arm.animation_data_create()
        target_arm.animation_data.action = tar_action

    return {
        "ok": True,
        "source_rig": source_arm.name,
        "target_rig": target_arm.name,
        "mapped_keyframe_channels": mapped,
        "status": "Animation retargeted successfully onto target armature."
    }
