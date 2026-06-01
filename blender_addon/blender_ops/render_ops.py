"""Camera, lighting and render operations."""
from __future__ import annotations

import math
import os

import bpy
from mathutils import Vector

from . import helpers as H


# --------------------------------------------------------------------------- #
# Scene bounds / framing
# --------------------------------------------------------------------------- #
def _scene_bounds():
    meshes = H.all_mesh_objects()
    if not meshes:
        return Vector((0, 0, 0)), 6.0
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    for o in meshes:
        for corner in o.bound_box:
            wc = o.matrix_world @ Vector(corner)
            mins = Vector((min(mins.x, wc.x), min(mins.y, wc.y), min(mins.z, wc.z)))
            maxs = Vector((max(maxs.x, wc.x), max(maxs.y, wc.y), max(maxs.z, wc.z)))
    center = (mins + maxs) / 2.0
    radius = max((maxs - mins).length / 2.0, 2.0)
    return center, radius


def _ensure_camera(name="Camera_Main"):
    cam = next((o for o in bpy.context.scene.objects if o.type == "CAMERA"), None)
    if cam is None:
        data = bpy.data.cameras.new(name)
        cam = bpy.data.objects.new(name, data)
        H.get_or_create_collection("Cameras").objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def _point_at(obj, target: Vector):
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def op_setup_camera(params):
    center, radius = _scene_bounds()
    cam = _ensure_camera()
    cam.data.lens = float(params.get("focal_length", 50.0))
    cam.data.type = "PERSP"
    cam.location = center + Vector((radius * 1.6, -radius * 1.8, radius * 1.1))
    _point_at(cam, center)
    return {"camera": cam.name, "focal_length": cam.data.lens}


def op_setup_isometric_camera(params):
    center, radius = _scene_bounds()
    cam = _ensure_camera("Camera_Isometric")
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = radius * 3.2
    angle = math.radians(float(params.get("angle", 45.0)))
    dist = float(params.get("distance", 18.0))
    cam.location = center + Vector((dist * math.cos(angle), -dist * math.sin(angle), dist * 0.8))
    _point_at(cam, center)
    return {"camera": cam.name, "type": "ortho_isometric"}


def op_setup_archviz_camera(params):
    center, radius = _scene_bounds()
    cam = _ensure_camera("Camera_Archviz")
    cam.data.type = "PERSP"
    cam.data.lens = float(params.get("focal_length", 24.0))
    eye = float(params.get("eye_level", 1.6))
    cam.location = Vector((center.x + radius * 1.4, center.y - radius * 1.6, eye))
    _point_at(cam, Vector((center.x, center.y, eye)))
    return {"camera": cam.name, "focal_length": cam.data.lens}


def op_setup_product_camera(params):
    center, radius = _scene_bounds()
    cam = _ensure_camera("Camera_Product")
    cam.data.type = "PERSP"
    cam.data.lens = float(params.get("focal_length", 85.0))
    cam.location = center + Vector((0, -radius * 3.0, radius * 0.8))
    _point_at(cam, center)
    if params.get("depth_of_field", True):
        cam.data.dof.use_dof = True
        cam.data.dof.focus_distance = (cam.location - center).length
        cam.data.dof.aperture_fstop = 2.8
    return {"camera": cam.name, "dof": params.get("depth_of_field", True)}


# --------------------------------------------------------------------------- #
# Lighting
# --------------------------------------------------------------------------- #
def _add_light(name, ltype, energy, location, collection):
    data = bpy.data.lights.new(name, ltype)
    data.energy = energy
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.location = location
    return obj


def _world_strength(value, color=(0.05, 0.06, 0.08)):
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Strength"].default_value = value
        bg.inputs["Color"].default_value = (*color, 1.0)


def op_setup_lighting(params):
    center, radius = _scene_bounds()
    coll = H.get_or_create_collection("Lighting")
    style = params.get("style", "soft")
    strength = float(params.get("strength", 1.0))
    sun = _add_light("Sun_Key", "SUN", 3.0 * strength, center + Vector((radius, -radius, radius * 2)), coll)
    _point_at(sun, center)
    _world_strength(0.6 if style == "bright" else (0.2 if style == "moody" else 0.4))
    return {"lights": [sun.name], "style": style}


def op_setup_three_point_lighting(params):
    center, radius = _scene_bounds()
    coll = H.get_or_create_collection("Lighting")
    s = float(params.get("strength", 1.0))
    key = _add_light("Key", "AREA", 800 * s, center + Vector((radius * 1.5, -radius * 1.5, radius * 1.5)), coll)
    fill = _add_light("Fill", "AREA", 300 * s, center + Vector((-radius * 1.8, -radius, radius)), coll)
    rim = _add_light("Rim", "AREA", 500 * s, center + Vector((0, radius * 1.8, radius * 1.4)), coll)
    for l in (key, fill, rim):
        l.data.size = radius
        _point_at(l, center)
    _world_strength(0.3)
    return {"lights": [key.name, fill.name, rim.name]}


def op_setup_archviz_lighting(params):
    center, radius = _scene_bounds()
    coll = H.get_or_create_collection("Lighting")
    tod = params.get("time_of_day", "midday")
    energy = {"sunrise": 2.0, "midday": 5.0, "sunset": 2.5, "night": 0.2}.get(tod, 5.0)
    sun = _add_light("Sun_Archviz", "SUN", energy, center + Vector((radius * 2, -radius * 2, radius * 3)), coll)
    sun.data.angle = math.radians(0.5)
    _point_at(sun, center)
    _world_strength(1.0 if not params.get("interior") else 0.5, color=(0.5, 0.6, 0.75))
    return {"lights": [sun.name], "time_of_day": tod}


def op_setup_cinematic_lighting(params):
    center, radius = _scene_bounds()
    coll = H.get_or_create_collection("Lighting")
    key = _add_light("Cine_Key", "SPOT", 2000, center + Vector((radius * 1.5, -radius * 2, radius * 2)), coll)
    key.data.spot_size = math.radians(50)
    _point_at(key, center)
    rim = _add_light("Cine_Rim", "AREA", 700, center + Vector((-radius, radius * 2, radius)), coll)
    _point_at(rim, center)
    _world_strength(0.05)
    if params.get("volumetrics"):
        bpy.context.scene.eevee.use_volumetric_lights = True
    return {"lights": [key.name, rim.name], "mood": params.get("mood", "dramatic")}


# --------------------------------------------------------------------------- #
# Render presets / rendering
# --------------------------------------------------------------------------- #
def _engine_available(engine):
    try:
        return engine in {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    except Exception:
        return engine == "BLENDER_EEVEE"


def _pick_eevee():
    for cand in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        if _engine_available(cand):
            return cand
    return "BLENDER_EEVEE"


def op_apply_render_preset(params):
    scene = bpy.context.scene
    preset = params.get("preset", "portfolio_render")
    scene.view_settings.view_transform = "Filmic" if "Filmic" in [
        t.name for t in bpy.types.ColorManagedViewSettings.bl_rna.properties["view_transform"].enum_items
    ] else "Standard"

    if preset == "fast_preview":
        scene.render.engine = _pick_eevee()
        scene.eevee.taa_render_samples = 16
    elif preset in ("archviz_render", "cinematic_render"):
        if _engine_available("CYCLES"):
            scene.render.engine = "CYCLES"
            scene.cycles.samples = 256 if preset == "archviz_render" else 200
        else:
            scene.render.engine = _pick_eevee()
            scene.eevee.taa_render_samples = 128
    else:  # portfolio_render, product_render
        scene.render.engine = _pick_eevee()
        scene.eevee.taa_render_samples = 128
        if hasattr(scene.eevee, "use_gtao"):
            scene.eevee.use_gtao = True

    scene.render.film_transparent = preset == "product_render"
    return {"preset": preset, "engine": scene.render.engine}


def _render_to(filepath, width, height, samples=None):
    scene = bpy.context.scene
    if scene.camera is None:
        op_setup_camera({})
    scene.render.resolution_x = int(width)
    scene.render.resolution_y = int(height)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    if samples and scene.render.engine == "CYCLES":
        scene.cycles.samples = int(samples)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)
    return filepath


def op_render_preview(params):
    from .export_ops import workspace_output
    path = workspace_output("renders", params.get("filename", "preview.png"))
    if bpy.context.scene.render.engine not in ("CYCLES",):
        bpy.context.scene.eevee.taa_render_samples = min(
            getattr(bpy.context.scene.eevee, "taa_render_samples", 16), 32)
    _render_to(path, params.get("width", 960), params.get("height", 540))
    return {"render_path": path}


def op_render_final(params):
    from .export_ops import workspace_output
    path = workspace_output("renders", params.get("filename", "final.png"))
    _render_to(path, params.get("width", 1920), params.get("height", 1080), params.get("samples", 128))
    return {"render_path": path}


def op_export_render_image(params):
    from .export_ops import workspace_output
    path = workspace_output("renders", params.get("filename", "render.png"))
    _render_to(path, params.get("width", 1920), params.get("height", 1080))
    return {"render_path": path}


def op_export_turntable_animation(params):
    from .export_ops import workspace_output
    center, radius = _scene_bounds()
    scene = bpy.context.scene
    cam = _ensure_camera()
    # Parent camera to an empty pivot and spin it.
    pivot = bpy.data.objects.new("TurntablePivot", None)
    H.get_or_create_collection("Cameras").objects.link(pivot)
    pivot.location = center
    cam.parent = pivot
    frames = int(params.get("frames", 48))
    scene.frame_start = 1
    scene.frame_end = frames
    pivot.rotation_euler = (0, 0, 0)
    pivot.keyframe_insert("rotation_euler", frame=1)
    pivot.rotation_euler = (0, 0, math.radians(360))
    pivot.keyframe_insert("rotation_euler", frame=frames)
    path = workspace_output("renders", params.get("filename", "turntable.mp4"))
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.filepath = path
    bpy.ops.render.render(animation=True)
    return {"render_path": path, "frames": frames}


def op_setup_camera_auto_focus(params):
    """Enable depth of field on the active camera and lock its focus point onto an object or rig."""
    cam = bpy.context.scene.camera
    if not cam:
        cam = _ensure_camera()

    target_name = params.get("target_name")
    target_obj = bpy.data.objects.get(target_name) if target_name else None

    # If no target provided, search for first active armature skeleton in scene
    if not target_obj:
        target_obj = next((o for o in bpy.context.scene.objects if o.type == 'ARMATURE'), None)
    if not target_obj:
        # Or fall back to any active mesh object
        target_obj = next((o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.name.startswith("COL_")), None)

    if not target_obj:
        return {"ok": False, "error": "No mesh or armature found to set focus target."}

    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = target_obj
    cam.data.dof.aperture_fstop = float(params.get("fstop", 2.0))

    return {
        "ok": True,
        "camera": cam.name,
        "focus_target": target_obj.name,
        "fstop": cam.data.dof.aperture_fstop,
    }


# =============================================================================
# GERÇEK ZAMANLI HAVA DURUMU IŞIĞI
# =============================================================================

def op_set_weather_environment(params):
    """OpenWeatherMap verisine göre dünya + güneş + volumetrics ayarlar."""
    import math
    import bpy

    condition = params.get("condition", "clear").lower()
    tod = params.get("time_of_day", "day").lower()
    intensity = float(params.get("intensity", 1.0))
    clouds = float(params.get("clouds", 0))
    location = params.get("location", "")

    # World node tree hazırla
    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("Weather_World")
        bpy.context.scene.world = world

    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links

    # Temizle
    for n in list(nodes):
        if n.name not in {"Background", "World Output"}:
            nodes.remove(n)

    bg = nodes.get("Background") or nodes.new("ShaderNodeBackground")
    out = nodes.get("World Output") or nodes.new("ShaderNodeOutputWorld")
    links.new(bg.outputs[0], out.inputs[0])

    # Renk ve strength kararları
    if tod == "night":
        bg_color = (0.02, 0.025, 0.06)
        strength = 0.15 * intensity
        sun_energy = 0.3
        sun_angle = (1.6, 0.3, 2.8)
    elif tod == "sunset":
        bg_color = (0.85, 0.35, 0.15)
        strength = 0.9 * intensity
        sun_energy = 2.8
        sun_angle = (1.1, -0.4, 2.4)
    else:  # day
        if condition in ("rain", "drizzle", "thunderstorm"):
            bg_color = (0.55, 0.58, 0.65)
            strength = 0.6 * intensity
            sun_energy = 1.8
        elif clouds > 60:
            bg_color = (0.72, 0.78, 0.85)
            strength = 0.75 * intensity
            sun_energy = 2.2
        else:
            bg_color = (0.65, 0.78, 0.95)
            strength = 1.1 * intensity
            sun_energy = 3.5

    bg.inputs[0].default_value = (*bg_color, 1.0)
    bg.inputs[1].default_value = strength

    # Güneş ışığı oluştur / güncelle
    sun = None
    for obj in bpy.data.objects:
        if obj.type == "LIGHT" and obj.data.type == "SUN":
            sun = obj
            break

    if not sun:
        sun_data = bpy.data.lights.new("Weather_Sun", "SUN")
        sun = bpy.data.objects.new("Weather_Sun", sun_data)
        bpy.context.scene.collection.objects.link(sun)

    sun.data.energy = sun_energy
    sun.rotation_euler = sun_angle

    # Basit volumetrics (Cycles için)
    if tod in ("sunset", "night") or condition in ("rain", "clouds"):
        vol = nodes.new("ShaderNodeVolumeScatter")
        vol.inputs[0].default_value = (0.9, 0.92, 0.95, 1.0)
        vol.inputs[1].default_value = 0.02 * (1.5 if tod == "sunset" else 1.0)
        links.new(vol.outputs[0], out.inputs[1])

    # HDRI benzeri basit sky texture (eğer varsa)
    try:
        sky = nodes.new("ShaderNodeTexSky")
        sky.sky_type = "HOSEK_WILKIE"
        sky.sun_direction = (0, 0, 1)
        links.new(sky.outputs[0], bg.inputs[0])
    except Exception:
        pass

    return {
        "ok": True,
        "condition": condition,
        "time_of_day": tod,
        "sun_energy": sun_energy,
        "location": location,
        "message": f"Weather environment applied for {location} ({tod}, {condition})",
    }
