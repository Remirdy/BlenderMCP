"""Procedural humanoid character, rig and animation operations."""
from __future__ import annotations

import math
import os

import bpy

from . import helpers as H


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
    parts.append(_add_uv("CHR_Torso_Armored", (0, 0, 1.45), (0.36, 0.2, 0.5), fabric, coll))
    parts.append(_add_cube("CHR_Chest_Armor", (0, -0.18, 1.55), (0.58, 0.08, 0.42), metal, coll, 0.035))
    parts.append(_add_uv("CHR_Pelvis_Belted", (0, 0, 0.88), (0.32, 0.19, 0.22), leather, coll))
    parts.append(_add_uv("CHR_Head", (0, 0, 2.25), (0.26, 0.22, 0.3), skin, coll))
    parts.append(_add_cylinder("CHR_Neck", (0, 0, 2.0), 0.09, 0.22, skin, coll))
    parts.append(_add_uv("CHR_Hair_Mass", (0, 0.03, 2.47), (0.29, 0.24, 0.16), hair, coll))
    parts.append(_add_cone("CHR_Hair_Front_Spike", (0, -0.22, 2.4), 0.12, 0.02, 0.3, hair, coll, rotation=(math.radians(90), 0, 0)))
    parts.append(_add_uv("CHR_Eye_L", (-0.085, -0.205, 2.27), (0.032, 0.014, 0.024), eye, coll, 16))
    parts.append(_add_uv("CHR_Eye_R", (0.085, -0.205, 2.27), (0.032, 0.014, 0.024), eye, coll, 16))
    parts.append(_add_uv("CHR_Pupil_L", (-0.085, -0.218, 2.265), (0.012, 0.006, 0.012), cyan, coll, 12))
    parts.append(_add_uv("CHR_Pupil_R", (0.085, -0.218, 2.265), (0.012, 0.006, 0.012), cyan, coll, 12))

    for side, sign in (("L", -1), ("R", 1)):
        parts.append(_add_uv(f"CHR_ShoulderPad_{side}", (sign * 0.44, -0.02, 1.78), (0.2, 0.16, 0.12), metal, coll))
        parts += _capsule(f"CHR_UpperArm_{side}", (sign * 0.76, 0, 1.58), 0.085, 0.5, fabric, coll, axis="X")
        parts += _capsule(f"CHR_Forearm_{side}", (sign * 1.2, 0, 1.46), 0.078, 0.42, leather, coll, axis="X")
        parts.append(_add_uv(f"CHR_Hand_{side}", (sign * 1.48, -0.01, 1.44), (0.09, 0.065, 0.08), skin, coll, 16))
        parts += _capsule(f"CHR_Thigh_{side}", (sign * 0.23, 0, 0.38), 0.12, 0.62, fabric, coll)
        parts += _capsule(f"CHR_Shin_{side}", (sign * 0.28, 0, -0.27), 0.108, 0.62, metal, coll)
        parts.append(_add_cube(f"CHR_Boot_{side}", (sign * 0.29, -0.11, -0.76), (0.22, 0.36, 0.16), black, coll, 0.03))
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
        elif "Torso" in name or "Chest" in name or "Cape" in name:
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
    if params.get("clear_scene", True):
        _clear_scene()
    name = params.get("name", "Cyber Adventurer")
    style = params.get("style", "stylized_hero")
    arm = _create_armature()
    parts = _create_mesh_parts(style)
    _attach_parts(parts, arm)
    _setup_stage()
    anim = op_add_character_animation({
        "animation": params.get("animation", "idle_wave"),
        "frames": int(params.get("frames", 120)),
    })
    bpy.context.scene.frame_set(1)
    return {
        "character": name,
        "style": style,
        "rig": arm.name,
        "mesh_parts": len(parts),
        "bones": len(arm.data.bones),
        "animation": anim,
        "suggested_next": ["validate_character_rig", "render_preview", "export_character_glb"],
    }


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
    if len(children) < 12:
        issues.append("Character has too few mesh parts parented to the rig.")
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
