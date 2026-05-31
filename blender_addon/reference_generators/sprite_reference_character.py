"""Reference-driven stylized adventurer character generator.

The first MVP version of this module emitted a generic block mannequin. This
version intentionally builds the design language visible in the supplied sprite
sheet: anime proportions, navy coat panels, cream high collar, bronze shoulder
armor, leather straps and pouches, cyan gems, dark trousers, boots, gloves and
spiky hair. It still is not photogrammetry or true neural reconstruction, but it
creates a usable, named, rigged Blender character instead of a placeholder.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector


WORKSPACE = Path(os.environ.get("REMIRDY_WORKSPACE", str(Path.home() / "RemirdyWorkspace")))
BLEND = WORKSPACE / "outputs" / "blends" / "sprite_reference_hero_3d.blend"
GLB = WORKSPACE / "outputs" / "exports" / "sprite_reference_hero_3d.glb"
PREVIEW = WORKSPACE / "outputs" / "screenshots" / "sprite_reference_hero_3d_preview.png"


def ensure_dirs():
    for path in (BLEND.parent, GLB.parent, PREVIEW.parent):
        path.mkdir(parents=True, exist_ok=True)


def clear():
    bpy.ops.object.mode_set(mode="OBJECT") if bpy.ops.object.mode_set.poll() else None
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _set_input(bsdf, names, value):
    for name in names:
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = value
            return


def mat(name, color, metallic=0.0, roughness=0.58, emission=None, strength=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = color
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = next((node for node in m.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    if bsdf:
        _set_input(bsdf, ("Base Color",), color)
        _set_input(bsdf, ("Metallic",), metallic)
        _set_input(bsdf, ("Roughness",), roughness)
        if emission:
            _set_input(bsdf, ("Emission Color", "Emission"), emission)
            _set_input(bsdf, ("Emission Strength",), strength)
    return m


def bevel(obj, width=0.018, segments=2):
    mod = obj.modifiers.new("soft_bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.affect = "EDGES"
    obj.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
    return obj


def smooth(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    try:
        bpy.ops.object.shade_smooth()
    finally:
        obj.select_set(False)
    return obj


def ellipsoid(name, loc, scale, material, rot=(0, 0, 0), segments=32):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=16, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(material)
    return smooth(obj)


def capsule(name, a, b, radius, material, rot=0.0, vertices=24):
    a = Vector(a)
    b = Vector(b)
    mid = (a + b) * 0.5
    direction = b - a
    length = direction.length
    if length <= 0:
        return ellipsoid(name, mid, (radius, radius, radius), material)
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=length, location=mid)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    obj.rotation_euler.rotate_axis("Z", rot)
    obj.data.materials.append(material)
    smooth(obj)
    for cap in (
        ellipsoid(f"{name}_cap_A", a, (radius, radius, radius), material, segments=vertices),
        ellipsoid(f"{name}_cap_B", b, (radius, radius, radius), material, segments=vertices),
    ):
        world = cap.matrix_world.copy()
        cap.parent = obj
        cap.matrix_world = world
    return obj


def box(name, loc, scale, material, rot=(0, 0, 0), b=0.0):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if b:
        bevel(obj, b)
    return obj


def cone(name, loc, r1, r2, depth, material, rot=(0, 0, 0), vertices=12):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=r1, radius2=r2, depth=depth, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    return smooth(obj)


def torus(name, loc, major, minor, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=36, minor_segments=8, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    return smooth(obj)


def panel(name, verts, material, thickness=0.018, b=0.01):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], [tuple(range(len(verts)))])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    solid = obj.modifiers.new("cloth_panel_thickness", "SOLIDIFY")
    solid.thickness = thickness
    solid.offset = 0.0
    if b:
        bevel(obj, b, 2)
    return obj


def trim_curve(name, points, material, width=0.012):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 3
    curve.bevel_depth = width
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points):
        point.co = (co[0], co[1], co[2], 1.0)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def analyze_reference_image(reference_image: str | None) -> dict:
    """Extract lightweight, deterministic metadata from the reference image."""
    info = {"source": reference_image, "loaded": False, "non_black_bbox": None, "sampled_palette": []}
    if not reference_image:
        return info
    path = Path(reference_image).expanduser()
    if not path.exists():
        info["error"] = "missing reference image"
        return info
    try:
        image = bpy.data.images.load(str(path), check_existing=True)
        width, height = image.size
        pixels = image.pixels[:]
        step = max(1, int(min(width, height) / 160))
        min_x, min_y, max_x, max_y = width, height, 0, 0
        buckets: dict[tuple[int, int, int], int] = {}
        for y in range(0, height, step):
            for x in range(0, width, step):
                idx = (y * width + x) * 4
                r, g, b, a = pixels[idx], pixels[idx + 1], pixels[idx + 2], pixels[idx + 3]
                if a < 0.2 or (r + g + b) < 0.08:
                    continue
                min_x, min_y = min(min_x, x), min(min_y, y)
                max_x, max_y = max(max_x, x), max(max_y, y)
                key = (round(r * 10), round(g * 10), round(b * 10))
                buckets[key] = buckets.get(key, 0) + 1
        if max_x > min_x and max_y > min_y:
            info["non_black_bbox"] = [min_x, min_y, max_x, max_y]
        palette = sorted(buckets.items(), key=lambda kv: kv[1], reverse=True)[:10]
        info["sampled_palette"] = [
            {"rgb": [round(k[0] / 10, 2), round(k[1] / 10, 2), round(k[2] / 10, 2)], "weight": v}
            for k, v in palette
        ]
        info["width"] = width
        info["height"] = height
        info["loaded"] = True
    except Exception as exc:  # noqa: BLE001 - keep asset generation resilient
        info["error"] = f"{type(exc).__name__}: {exc}"
    return info


def make_armature():
    bpy.ops.object.armature_add(location=(0, 0, 0))
    arm = bpy.context.object
    arm.name = "SpriteHero_Rig"
    arm.data.name = "SpriteHero_Armature"
    arm.show_in_front = True
    bpy.ops.object.mode_set(mode="EDIT")
    arm.data.edit_bones.remove(arm.data.edit_bones[0])

    def bone(name, head, tail, parent=None):
        b = arm.data.edit_bones.new(name)
        b.head = head
        b.tail = tail
        if parent:
            b.parent = arm.data.edit_bones[parent]
            b.use_connect = False
        return b

    bone("root", (0, 0, -0.65), (0, 0, 0.2))
    bone("pelvis", (0, 0, 0.40), (0.03, 0, 0.82), "root")
    bone("spine", (0.03, 0, 0.82), (-0.02, 0, 1.75), "pelvis")
    bone("neck", (-0.02, 0, 1.75), (-0.02, 0, 1.95), "spine")
    bone("head", (-0.02, 0, 1.95), (0.03, 0, 2.40), "neck")
    for side, sign in (("L", -1), ("R", 1)):
        bone(f"upper_arm.{side}", (sign * 0.30, 0, 1.62), (sign * 0.72, -0.03, 1.38), "spine")
        bone(f"forearm.{side}", (sign * 0.72, -0.03, 1.38), (sign * 1.05, -0.08, 1.18), f"upper_arm.{side}")
        bone(f"hand.{side}", (sign * 1.05, -0.08, 1.18), (sign * 1.18, -0.10, 1.08), f"forearm.{side}")
        bone(f"thigh.{side}", (sign * 0.17, 0, 0.42), (sign * 0.27, -0.02, -0.12), "pelvis")
        bone(f"shin.{side}", (sign * 0.27, -0.02, -0.12), (sign * 0.30, -0.04, -0.62), f"thigh.{side}")
        bone(f"foot.{side}", (sign * 0.30, -0.04, -0.62), (sign * 0.30, -0.35, -0.70), f"shin.{side}")
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def parent_bone(obj, arm, bone):
    world = obj.matrix_world.copy()
    obj.parent = arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone
    obj.matrix_world = world


def _parent_parts(parts, arm):
    for obj in parts:
        n = obj.name
        bone = "spine"
        if any(k in n for k in ("Head", "Hair", "Eye", "Brow", "Mouth", "Face")):
            bone = "head"
        elif any(k in n for k in ("Belt", "Pouch", "CoatTail", "Scabbard")):
            bone = "pelvis"
        elif "_L" in n and any(k in n for k in ("Shoulder", "UpperArm", "Sleeve")):
            bone = "upper_arm.L"
        elif "_R" in n and any(k in n for k in ("Shoulder", "UpperArm", "Sleeve")):
            bone = "upper_arm.R"
        elif "_L" in n and any(k in n for k in ("Forearm", "Cuff", "Bracer")):
            bone = "forearm.L"
        elif "_R" in n and any(k in n for k in ("Forearm", "Cuff", "Bracer")):
            bone = "forearm.R"
        elif "_L" in n and any(k in n for k in ("Glove", "Hand")):
            bone = "hand.L"
        elif "_R" in n and any(k in n for k in ("Glove", "Hand")):
            bone = "hand.R"
        elif "_L" in n and any(k in n for k in ("Thigh", "PantsUpper")):
            bone = "thigh.L"
        elif "_R" in n and any(k in n for k in ("Thigh", "PantsUpper")):
            bone = "thigh.R"
        elif "_L" in n and any(k in n for k in ("Shin", "Knee", "Greave")):
            bone = "shin.L"
        elif "_R" in n and any(k in n for k in ("Shin", "Knee", "Greave")):
            bone = "shin.R"
        elif "_L" in n and "Boot" in n:
            bone = "foot.L"
        elif "_R" in n and "Boot" in n:
            bone = "foot.R"
        parent_bone(obj, arm, bone)


def animate(arm):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 120
    bpy.context.scene.render.fps = 24
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0, 0, 0)
        pb.keyframe_insert("rotation_euler", frame=1)
        pb.keyframe_insert("rotation_euler", frame=120)
    poses = {
        "head": (math.radians(2), 0, math.radians(-5)),
        "spine": (0, math.radians(-2), math.radians(2)),
        "upper_arm.R": (math.radians(8), math.radians(-8), math.radians(-22)),
        "forearm.R": (0, math.radians(2), math.radians(-36)),
        "upper_arm.L": (math.radians(-5), math.radians(5), math.radians(18)),
        "forearm.L": (0, 0, math.radians(20)),
    }
    bpy.context.scene.frame_set(60)
    for name, rot in poses.items():
        if name in arm.pose.bones:
            arm.pose.bones[name].rotation_euler = rot
            arm.pose.bones[name].keyframe_insert("rotation_euler", frame=60)
    if arm.animation_data and arm.animation_data.action:
        arm.animation_data.action.name = "SpriteHero_reference_idle_pose"
    bpy.ops.object.mode_set(mode="OBJECT")


def build(reference_image: str | None = None):
    ref_info = analyze_reference_image(reference_image)

    skin = mat("M_ref_warm_skin", (0.78, 0.50, 0.33, 1))
    hair = mat("M_ref_blue_black_spiky_hair", (0.015, 0.016, 0.018, 1), roughness=0.72)
    navy = mat("M_ref_deep_navy_coat", (0.018, 0.070, 0.135, 1), roughness=0.52)
    navy_shadow = mat("M_ref_coat_shadow_teal", (0.010, 0.035, 0.058, 1), roughness=0.68)
    cream = mat("M_ref_ivory_collar_cuffs", (0.86, 0.76, 0.58, 1), roughness=0.50)
    shirt = mat("M_ref_open_warm_white_shirt", (0.90, 0.85, 0.74, 1), roughness=0.62)
    leather = mat("M_ref_worn_brown_leather", (0.25, 0.13, 0.055, 1), roughness=0.45)
    leather_dark = mat("M_ref_dark_boot_leather", (0.10, 0.055, 0.03, 1), roughness=0.50)
    pants = mat("M_ref_charcoal_trousers", (0.070, 0.067, 0.060, 1), roughness=0.75)
    bronze = mat("M_ref_bronze_armor_trim", (0.67, 0.42, 0.20, 1), metallic=0.55, roughness=0.34)
    steel = mat("M_ref_gunmetal_knee_buckles", (0.19, 0.20, 0.21, 1), metallic=0.5, roughness=0.42)
    cyan = mat("M_ref_cyan_gem_glow", (0.0, 0.70, 0.95, 1), emission=(0.0, 0.92, 1.0, 1), strength=2.8)
    black = mat("M_ref_black_gloves_and_linework", (0.008, 0.007, 0.006, 1), roughness=0.7)
    gold = mat("M_ref_gold_embroidery", (0.95, 0.73, 0.25, 1), metallic=0.25, roughness=0.36)

    arm = make_armature()
    parts = []

    # Anime body proportions.
    parts += [
        ellipsoid("Hero_Head_anime_tapered", (0.00, -0.025, 2.12), (0.22, 0.17, 0.285), skin),
        capsule("Hero_Neck", (-0.01, 0, 1.78), (-0.01, 0, 1.96), 0.065, skin),
        ellipsoid("Hero_Torso_white_open_shirt", (0.02, -0.015, 1.36), (0.305, 0.165, 0.485), shirt),
        ellipsoid("Hero_CoatChest_navy_fitted", (0.01, 0.005, 1.37), (0.39, 0.135, 0.53), navy),
        panel("Hero_OpenShirt_front_V", [(-0.16, -0.145, 1.74), (0.16, -0.145, 1.70), (0.10, -0.155, 1.05), (-0.08, -0.155, 1.02)], shirt, 0.012, 0.006),
    ]

    # Coat panels, lapels and flared tails.
    parts += [
        panel("Hero_Lapel_L_ivory_high", [(-0.36, -0.17, 1.88), (-0.17, -0.18, 1.74), (-0.08, -0.17, 1.18), (-0.24, -0.16, 1.05), (-0.40, -0.13, 1.60)], cream, 0.020, 0.014),
        panel("Hero_Lapel_R_ivory_high", [(0.35, -0.17, 1.88), (0.16, -0.18, 1.74), (0.08, -0.17, 1.18), (0.25, -0.16, 1.05), (0.40, -0.13, 1.58)], cream, 0.020, 0.014),
        panel("Hero_Collar_L_tall_flared", [(-0.38, -0.05, 1.82), (-0.14, -0.08, 1.94), (-0.05, 0.02, 1.78), (-0.23, 0.05, 1.62)], cream, 0.035, 0.018),
        panel("Hero_Collar_R_tall_flared", [(0.39, -0.05, 1.82), (0.13, -0.08, 1.94), (0.05, 0.02, 1.78), (0.25, 0.05, 1.62)], cream, 0.035, 0.018),
        panel("Hero_CoatTail_L_long_split", [(-0.42, 0.08, 1.02), (-0.08, 0.05, 0.98), (-0.16, 0.13, -0.26), (-0.60, 0.18, -0.48)], navy, 0.026, 0.014),
        panel("Hero_CoatTail_R_long_split", [(0.40, 0.08, 1.00), (0.08, 0.05, 0.98), (0.16, 0.13, -0.22), (0.58, 0.18, -0.42)], navy_shadow, 0.026, 0.014),
        panel("Hero_BackCoat_center_tail", [(-0.18, 0.17, 1.02), (0.18, 0.17, 1.02), (0.08, 0.25, -0.38), (-0.08, 0.25, -0.40)], navy, 0.024, 0.012),
    ]
    for side, sign in (("L", -1), ("R", 1)):
        parts.append(trim_curve(f"Hero_GoldCoatTrim_{side}", [(sign * 0.36, -0.19, 1.60), (sign * 0.32, -0.19, 1.18), (sign * 0.47, -0.15, 0.20), (sign * 0.55, -0.11, -0.32)], gold, 0.008))

    # Belts, pouches, scabbard-like side strap and buckles.
    parts += [
        trim_curve("Hero_DiagonalChestStrap_brown", [(-0.30, -0.205, 1.72), (-0.06, -0.22, 1.43), (0.17, -0.205, 1.04)], leather, 0.035),
        trim_curve("Hero_WaistBelt_brown", [(-0.42, -0.19, 0.95), (-0.15, -0.21, 0.91), (0.15, -0.21, 0.93), (0.43, -0.19, 0.97)], leather, 0.040),
        box("Hero_BeltBuckle_gunmetal", (0.00, -0.245, 0.93), (0.15, 0.035, 0.10), steel, b=0.010),
        torus("Hero_ChestStrap_ring", (-0.19, -0.235, 1.55), 0.045, 0.008, bronze, rot=(math.radians(90), 0, 0)),
        panel("Hero_SidePouch_L_large", [(-0.58, -0.20, 0.92), (-0.38, -0.21, 0.94), (-0.36, -0.22, 0.62), (-0.58, -0.22, 0.58)], leather, 0.060, 0.018),
        panel("Hero_SidePouch_R_small", [(0.38, -0.20, 0.90), (0.54, -0.21, 0.90), (0.52, -0.22, 0.68), (0.36, -0.22, 0.66)], leather, 0.050, 0.016),
        trim_curve("Hero_HangingStrap_left", [(-0.34, -0.23, 0.88), (-0.46, -0.25, 0.48), (-0.50, -0.22, 0.12)], leather, 0.020),
    ]

    # Arms, shoulder armor, cuffs, gloves.
    for side, sign in (("L", -1), ("R", 1)):
        parts += [
            ellipsoid(f"Hero_ShoulderArmor_{side}_bronze_layer", (sign * 0.43, -0.035, 1.61), (0.20, 0.145, 0.115), bronze, rot=(0, sign * math.radians(8), 0)),
            ellipsoid(f"Hero_ShoulderArmor_{side}_dark_under", (sign * 0.42, -0.015, 1.56), (0.18, 0.12, 0.08), steel),
            ellipsoid(f"Hero_ShoulderGem_{side}_cyan", (sign * 0.45, -0.170, 1.62), (0.040, 0.018, 0.040), cyan, segments=16),
            capsule(f"Hero_UpperArmSleeve_{side}_navy", (sign * 0.50, -0.02, 1.48), (sign * 0.80, -0.04, 1.28), 0.082, navy),
            ellipsoid(f"Hero_Cuff_{side}_ivory_roll", (sign * 0.86, -0.075, 1.22), (0.105, 0.070, 0.075), cream),
            capsule(f"Hero_ForearmBracer_{side}_leather", (sign * 0.88, -0.065, 1.18), (sign * 1.08, -0.085, 1.07), 0.070, leather),
            ellipsoid(f"Hero_GloveHand_{side}_black_fist", (sign * 1.18, -0.105, 1.02), (0.088, 0.062, 0.068), black, segments=20),
            trim_curve(f"Hero_BracerStrap_{side}", [(sign * 0.94, -0.145, 1.16), (sign * 1.05, -0.150, 1.10)], bronze, 0.010),
        ]

    # Pants, knee pads and boots.
    for side, sign in (("L", -1), ("R", 1)):
        parts += [
            capsule(f"Hero_PantsUpper_{side}_baggy", (sign * 0.16, 0.00, 0.55), (sign * 0.28, -0.02, 0.02), 0.125, pants),
            ellipsoid(f"Hero_KneePad_{side}_gunmetal", (sign * 0.30, -0.145, -0.05), (0.110, 0.042, 0.090), steel, segments=20),
            capsule(f"Hero_Shin_{side}_dark_wrapped", (sign * 0.30, -0.03, -0.16), (sign * 0.32, -0.04, -0.58), 0.095, pants),
            ellipsoid(f"Hero_Boot_{side}_brown_high", (sign * 0.32, -0.09, -0.66), (0.135, 0.195, 0.095), leather_dark, rot=(0, 0, sign * math.radians(2)), segments=24),
            ellipsoid(f"Hero_BootToe_{side}_brown", (sign * 0.32, -0.255, -0.69), (0.145, 0.105, 0.060), leather, segments=20),
            trim_curve(f"Hero_BootStrap_{side}", [(sign * 0.22, -0.19, -0.58), (sign * 0.42, -0.19, -0.58)], bronze, 0.012),
            ellipsoid(f"Hero_BootGem_{side}_cyan", (sign * 0.33, -0.340, -0.63), (0.030, 0.012, 0.030), cyan, segments=12),
        ]

    # Face and hair silhouette.
    parts += [
        ellipsoid("Hero_Eye_L_sharp_black", (-0.072, -0.178, 2.15), (0.034, 0.010, 0.014), black, segments=12),
        ellipsoid("Hero_Eye_R_sharp_black", (0.068, -0.178, 2.15), (0.034, 0.010, 0.014), black, segments=12),
        trim_curve("Hero_BrowLine_angry", [(-0.12, -0.188, 2.205), (-0.04, -0.197, 2.19), (0.04, -0.197, 2.19), (0.12, -0.188, 2.205)], black, 0.006),
        trim_curve("Hero_MouthLine_subtle", [(-0.035, -0.185, 2.035), (0.040, -0.188, 2.035)], black, 0.004),
        ellipsoid("Hero_HairMass_blue_black", (0.00, -0.010, 2.36), (0.245, 0.205, 0.150), hair, segments=32),
    ]
    spikes = [
        (-0.20, -0.13, 2.44, 0.080, 0.34, -48),
        (-0.10, -0.17, 2.53, 0.075, 0.38, -24),
        (0.03, -0.18, 2.55, 0.080, 0.40, 6),
        (0.16, -0.14, 2.48, 0.070, 0.34, 32),
        (0.23, -0.04, 2.38, 0.060, 0.25, 58),
        (-0.03, 0.03, 2.55, 0.090, 0.42, 0),
        (-0.18, 0.02, 2.42, 0.065, 0.30, -78),
    ]
    for idx, (x, y, z, r, depth, rz) in enumerate(spikes):
        parts.append(cone(f"Hero_HairSpike_{idx}_jagged", (x, y, z), r, 0.0, depth, hair, rot=(math.radians(70), 0, math.radians(rz)), vertices=9))

    # Optional slash arc from the attack frame as a non-rigged visual accent.
    slash = trim_curve("Hero_AttackArc_reference_yellow", [(0.66, -0.24, 1.50), (0.98, -0.30, 1.44), (1.30, -0.24, 1.56), (1.48, -0.12, 1.72)], gold, 0.018)
    slash["reference_note"] = "Yellow attack arc inspired by the rightmost sprite pose."
    parts.append(slash)

    _parent_parts(parts, arm)
    animate(arm)

    arm["reference_analysis"] = json.dumps(ref_info)
    arm["design_match_notes"] = json.dumps([
        "anime adventurer proportions",
        "deep navy long coat with split tails",
        "cream high collar and cuffs",
        "open warm white shirt",
        "brown diagonal chest strap and utility belt",
        "side pouches and hanging strap",
        "bronze shoulder armor with cyan gems",
        "dark trousers, gunmetal knee pads and brown boots",
        "black gloves and sharp spiky black hair",
        "yellow attack slash accent",
    ])
    return arm


def setup_scene():
    floor_mat = mat("M_matte_charcoal_studio_floor", (0.045, 0.047, 0.050, 1))
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=1.20, depth=0.08, location=(0, 0, -0.82))
    floor = bpy.context.object
    floor.name = "Studio_Base_low_charcoal"
    floor.data.materials.append(floor_mat)

    bpy.ops.object.light_add(type="AREA", location=(0.0, -4.2, 4.2))
    key = bpy.context.object
    key.name = "Large_Softbox_Key"
    key.data.energy = 720
    key.data.size = 4.6

    bpy.ops.object.light_add(type="POINT", location=(-2.4, 1.8, 2.2))
    rim = bpy.context.object
    rim.name = "Cyan_Rim_Accent"
    rim.data.energy = 190
    rim.data.color = (0.12, 0.78, 1.0)

    bpy.ops.object.camera_add(location=(0.05, -4.8, 1.10), rotation=(math.radians(79), 0, 0))
    cam = bpy.context.object
    cam.name = "Camera_full_character_match"
    cam.data.lens = 58
    bpy.context.scene.camera = cam

    engines = {item.identifier for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    if hasattr(bpy.context.scene, "eevee"):
        bpy.context.scene.eevee.taa_render_samples = 128
    bpy.context.scene.render.use_freestyle = True
    bpy.context.scene.render.resolution_x = 1200
    bpy.context.scene.render.resolution_y = 1600
    bpy.context.scene.view_settings.view_transform = "Filmic"
    bpy.context.scene.view_settings.look = "Medium High Contrast"
    bpy.context.scene.frame_set(60)


def main():
    ensure_dirs()
    clear()
    reference_image = os.environ.get("REMIRDY_REFERENCE_IMAGE")
    build(reference_image)
    setup_scene()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    bpy.ops.export_scene.gltf(filepath=str(GLB), export_format="GLB", export_animations=True, export_yup=True)
    bpy.context.scene.render.filepath = str(PREVIEW)
    bpy.ops.render.render(write_still=True)
    print(f"BLEND={BLEND}")
    print(f"GLB={GLB}")
    print(f"PREVIEW={PREVIEW}")


if __name__ == "__main__":
    main()
