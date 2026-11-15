from __future__ import annotations

import argparse
from array import array
import bmesh
import importlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Quaternion, Vector
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree


ROOT = Path(__file__).resolve().parents[1]
TAU = math.tau
PERIOD = 120
ASSETS = ROOT / "outputs" / "couture" / "source_assets"
FRAMES = 144
BODY_BVH = None
BIND_KD = None
BIND_WEIGHTS = []
CLOTH_OBJECTS = []


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs' / 'couture')
    parser.add_argument('--assets', type=Path, default=ASSETS)
    parser.add_argument('--device', choices=('CPU', 'METAL'), default='CPU')
    parser.add_argument('--engine', choices=('CYCLES', 'BLENDER_EEVEE'), default='CYCLES')
    parser.add_argument('--cloth-frames', type=int, default=FRAMES)
    parser.add_argument('--mode', choices=('build', 'still', 'animation'), default='still')
    parser.add_argument('--shot', choices=('gallery', 'detail'), default='gallery')
    parser.add_argument('--width', type=int, default=1440)
    parser.add_argument('--samples', type=int, default=64)
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--end', type=int, default=FRAMES)
    return parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])


def material(name, color, metallic=0.0, roughness=0.4):
    mat = bpy.data.materials.new(name)
    mat.use_fake_user = True
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    shader = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    shader.name = 'Principled BSDF'
    output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = roughness
    return mat


def fabric(name, color):
    mat = material(name, color, 0.05, 0.34)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Anisotropic'].default_value = 0.45
    bsdf.inputs['Sheen Weight'].default_value = 0.4
    bsdf.inputs['Sheen Roughness'].default_value = 0.35
    tex = nodes.new('ShaderNodeTexCoord')
    warp = nodes.new('ShaderNodeTexWave')
    warp.bands_direction = 'X'
    warp.inputs['Scale'].default_value = 22
    weft = nodes.new('ShaderNodeTexWave')
    weft.bands_direction = 'Y'
    weft.inputs['Scale'].default_value = 25
    for wave in (warp, weft):
        links.new(tex.outputs['UV'], wave.inputs['Vector'])
    cross = nodes.new('ShaderNodeMath')
    cross.operation = 'MULTIPLY'
    links.new(warp.outputs['Color'], cross.inputs[0])
    links.new(weft.outputs['Color'], cross.inputs[1])
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.26
    bump.inputs['Distance'].default_value = 0.0007
    links.new(cross.outputs[0], bump.inputs['Height'])
    links.new(bump.outputs[0], bsdf.inputs['Normal'])
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 130
    links.new(tex.outputs['UV'], noise.inputs['Vector'])
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*(c * 0.65 for c in color), 1)
    ramp.color_ramp.elements[1].color = (*(min(c * 1.15, 1) for c in color), 1)
    links.new(noise.outputs['Fac'], ramp.inputs[0])
    links.new(ramp.outputs[0], bsdf.inputs['Base Color'])
    return mat


def mesh(name, vertices, faces, mat, parent=None, uv=None):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    if mat:
        data.materials.append(mat)
    obj.parent = parent
    for face in data.polygons:
        face.use_smooth = True
    if uv:
        layer = data.uv_layers.new(name='Tailoring UV')
        for poly in data.polygons:
            for index in poly.loop_indices:
                layer.data[index].uv = uv[data.loops[index].vertex_index]
    return obj


def curves(name, paths, radius, mat, parent=None):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '3D'
    data.bevel_depth = radius
    data.bevel_resolution = 2
    for path in paths:
        spline = data.splines.new('POLY')
        spline.points.add(len(path) - 1)
        for p, co in zip(spline.points, path):
            p.co = (*co, 1)
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    data.materials.append(mat)
    obj.parent = parent
    return obj


def box(name, location, dimensions, mat, bevel=0.02):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        modifier = obj.modifiers.new('Machined edges', 'BEVEL')
        modifier.width = bevel
        modifier.segments = 3
        obj.modifiers.new('Weighted corner normals', 'WEIGHTED_NORMAL')
    return obj


def cylinder(name, location, radius, depth, mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=radius, depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    bevel = obj.modifiers.new('Turned edge', 'BEVEL')
    bevel.width = 0.008
    bevel.segments = 3
    obj.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return obj


def beads(name, points, mat, parent):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1)
    template = bpy.context.object
    source = [v.co.copy() for v in template.data.vertices]
    faces = [tuple(f.vertices) for f in template.data.polygons]
    bpy.data.objects.remove(template, do_unlink=True)
    vertices, polygons = [], []
    for center, radius in points:
        offset = len(vertices)
        vertices.extend(tuple(Vector(center) + v * radius) for v in source)
        polygons.extend(tuple(i + offset for i in face) for face in faces)
    return mesh(name, vertices, polygons, mat, parent)


def loop_motion(obj, amplitude=0.035, phase=0):
    basis = obj.shape_key_add(name='Tailored rest')
    for label, quarter in (('Bias response', 0), ('Weft response', math.pi / 2)):
        key = obj.shape_key_add(name=label)
        key.slider_min = -1
        for point, rest in zip(key.data, basis.data):
            p = rest.co
            weight = max(0, min(1, (0.99 - p.z) / 0.91)) ** 1.65
            angle = math.atan2(p.y + 0.055, p.x)
            wave = math.sin(angle * 3 + weight * 4 + quarter + phase)
            point.co.x += amplitude * weight * wave
            point.co.y += amplitude * 0.7 * weight * math.cos(angle * 2 + weight * 3 + quarter)
            point.co.z += amplitude * 0.32 * weight * math.sin(angle * 4 + quarter)
        driver = key.driver_add('value').driver
        driver.expression = f'sin(2*pi*(frame-1)/{PERIOD}+{quarter})'


def profile(t):
    stops = [(0, 0.151, 0.106), (0.3, 0.145, 0.112), (0.6, 0.17, 0.132), (1, 0.18, 0.126)]
    for (a, ax, ay), (b, bx, by) in zip(stops, stops[1:]):
        if a <= t <= b:
            w = (t - a) / (b - a)
            w = w * w * (3 - 2 * w)
            return ax * (1 - w) + bx * w, ay * (1 - w) + by * w
    return stops[-1][1:]


def corset_point(t, a, offset=0):
    top = 1.245 + 0.018 * math.cos(a * 2) + 0.014 * math.cos(a * 4)
    z = 0.985 + (top - 0.985) * t
    direction = Vector((math.cos(a), math.sin(a), 0))
    origin = Vector((0, -0.055, z))
    hit = BODY_BVH.ray_cast(origin, direction, 0.4)[0] if BODY_BVH else None
    if hit is not None:
        return tuple(hit + direction * (0.009 + offset))
    rx, ry = profile(t)
    return ((rx + offset) * math.cos(a), -0.055 + (ry + offset) * math.sin(a), z)


def skirt_point(t, a, extra=0, variant=0):
    if variant == 0:
        hip = 0.055 * math.sin(math.pi * min(t / 0.52, 1))
        radius = 0.152 + hip + 0.27 * t ** 3
        length = 0.91
    elif variant == 1:
        radius = 0.152 + 0.24 * t ** 1.4
        length = 0.48
    else:
        radius = 0.152 + 0.08 * math.sin(math.pi * t) + 0.21 * t ** 2
        length = 0.86 + 0.075 * math.sin(a)
    pleat = (0.001 + 0.019 * t ** 2) * math.cos(28 * a + 2 * t + 0.35 * math.sin(3 * a))
    rx = radius + pleat + extra
    ry = radius * 0.78 + pleat + extra
    train = max(0, math.sin(a)) ** 3 * (0.18 if variant != 1 else 0) * t ** 3
    z = 0.987 - length * t + 0.008 * t ** 3 * math.sin(7 * a)
    position = Vector((rx * math.cos(a), -0.055 + ry * math.sin(a) + train, z))
    if t < 0.22 and BODY_BVH:
        direction = Vector((math.cos(a), math.sin(a), 0))
        hit = BODY_BVH.ray_cast(Vector((0, -0.055, z)), direction, 0.4)[0]
        if hit is not None:
            fitted = hit + direction * (0.014 + extra)
            blend = min(1, t / 0.22) ** 2
            position = fitted.lerp(position, blend)
    return tuple(position)


def surface(name, function, rings, segments, mat, parent, animated=False):
    vertices, uv, faces = [], [], []
    for j in range(rings + 1):
        for i in range(segments + 1):
            t, u = j / rings, i / segments
            vertices.append(function(t, TAU * u))
            uv.append((u, t))
    for j in range(rings):
        for i in range(segments):
            k = j * (segments + 1) + i
            faces.append((k, k + 1, k + segments + 2, k + segments + 1))
    obj = mesh(name, vertices, faces, mat, parent, uv)
    if animated:
        loop_motion(obj)
    solid = obj.modifiers.new('Finished fabric edge', 'SOLIDIFY')
    solid.thickness = 0.0013
    return obj


def textured_skin(name, image_path):
    mat = material(name, (0.45, 0.25, 0.16), 0, 0.48)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes['Principled BSDF']
    shader.inputs['Subsurface Weight'].default_value = 0.12
    shader.inputs['Subsurface Radius'].default_value = (1, 0.45, 0.25)
    shader.inputs['Subsurface Scale'].default_value = 0.07
    shader.inputs['Specular IOR Level'].default_value = 0.3
    image = nodes.new('ShaderNodeTexImage')
    image.image = bpy.data.images.load(str(image_path), check_existing=True)
    links.new(image.outputs['Color'], shader.inputs['Base Color'])
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 1200
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.18
    bump.inputs['Distance'].default_value = 0.00015
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], shader.inputs['Normal'])
    return mat


def smooth_value(keys, property_name, time):
    values = sorted((int(frame), data[property_name]['values']) for frame, data in keys.items() if property_name in data)
    if len(values) == 1:
        return values[0][1][:]
    for index, ((start, left), (end, right)) in enumerate(zip(values, values[1:])):
        if start <= time <= end:
            previous_frame, previous = values[max(0, index - 1)]
            next_frame, following = values[min(len(values) - 1, index + 2)]
            u = (time - start) / (end - start)
            h00, h10 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u
            h01, h11 = -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
            output = []
            for a, b, before, after in zip(left, right, previous, following):
                m0 = (b - before) / (end - previous_frame)
                m1 = (after - a) / (next_frame - start)
                output.append(h00 * a + h10 * m0 * (end - start) + h01 * b + h11 * m1 * (end - start))
            return output
    return values[-1][1][:]


def walking_human(parent, variant):
    module_name = 'bl_ext.blender_org.mpfb'
    if module_name not in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_enable(module=module_name)
    human_service = importlib.import_module(module_name + '.services.humanservice').HumanService
    target_service = importlib.import_module(module_name + '.services.targetservice').TargetService
    phenotype = target_service.get_default_macro_info_dict()
    phenotype.update(gender=0.0, weight=0.28, muscle=0.3, cupsize=0.6, firmness=0.65)
    races = ({'african': 0.8, 'asian': 0.1, 'caucasian': 0.1}, {'african': 0.1, 'asian': 0.15, 'caucasian': 0.75}, {'african': 0.05, 'asian': 0.9, 'caucasian': 0.05})
    phenotype['race'] = races[variant]
    body = human_service.create_human(macro_detail_dict=phenotype)
    global BODY_BVH
    evaluated = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    rest_mesh = evaluated.to_mesh()
    BODY_BVH = BVHTree.FromPolygons([v.co for v in rest_mesh.vertices], [tuple(p.vertices) for p in rest_mesh.polygons])
    evaluated.to_mesh_clear()
    body.name = parent.name + ' | model'
    skins = ('young_african_female/young_darkskinned_female_diffuse.png', 'young_caucasian_female2/young_lightskinned_female_diffuse2.png', 'young_asian_female/young_lightskinned_female_diffuse3.png')
    body.data.materials.clear()
    body.data.materials.append(textured_skin(parent.name + ' | skin', ASSETS / 'skins' / skins[variant]))
    rig = human_service.add_builtin_rig(body, 'default_no_toes')
    rig.name = parent.name + ' | walk rig'
    global BIND_KD, BIND_WEIGHTS
    bpy.context.view_layer.update()
    evaluated = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    rest = evaluated.to_mesh()
    BIND_KD = KDTree(len(rest.vertices))
    BIND_WEIGHTS = []
    names = {group.index: group.name for group in body.vertex_groups if group.name in rig.data.bones}
    for vertex in rest.vertices:
        BIND_KD.insert(vertex.co, vertex.index)
        BIND_WEIGHTS.append([(names[g.group], g.weight) for g in vertex.groups if g.group in names and g.weight > 0.001])
    BIND_KD.balance()
    evaluated.to_mesh_clear()
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    helper_settings = importlib.import_module(module_name + '.ui.rigging.righelpers.righelperspanel').SETUP_HELPERS_PROPERTIES
    helper_settings.set_value('arm_helpers_type', 'LOWERUPPER', entity_reference=bpy.context.scene)
    helper_settings.set_value('leg_helpers_type', 'LOWERUPPER', entity_reference=bpy.context.scene)
    bpy.ops.mpfb.add_helpers()
    assets = ('eyes/high-poly/high-poly.mhclo', 'eyebrows/eyebrow001/eyebrow001.mhclo', 'eyelashes/eyelashes01/eyelashes01.mhclo', ('hair/ponytail01/ponytail01.mhclo', 'hair/bob02/bob02.mhclo', 'hair/braid01/braid01.mhclo')[variant])
    for filename in assets:
        before = set(bpy.data.objects)
        human_service.add_mhclo_asset(str(ASSETS / filename), body, asset_type='Eyes' if filename.startswith('eyes/') else 'Hair', subdiv_levels=1)
        if filename.startswith('hair/'):
            for hair in set(bpy.data.objects) - before:
                if hair.type == 'MESH':
                    mat = material(parent.name + ' | natural hair', ((0.008, 0.003, 0.001), (0.09, 0.024, 0.007), (0.005, 0.002, 0.001))[variant], 0, 0.42)
                    shader = mat.node_tree.nodes['Principled BSDF']
                    shader.inputs['Anisotropic'].default_value = 0.4
                    shader.inputs['Roughness'].default_value = 0.55
                    shader.inputs['Specular IOR Level'].default_value = 0.22
                    texture = mat.node_tree.nodes.new('ShaderNodeTexImage')
                    texture.image = bpy.data.images.load(str((ASSETS / filename).parent / (Path(filename).stem + '_diffuse.png')), check_existing=True)
                    mat.node_tree.links.new(texture.outputs['Alpha'], shader.inputs['Alpha'])
                    hair.data.materials.clear()
                    hair.data.materials.append(mat)
    rig.parent = parent
    walk_file = Path(importlib.import_module(module_name).__file__).parent / 'data' / 'walkcycles' / 'crappy_experimental_female.json'
    walk = json.loads(walk_file.read_text())['animation_data']
    for frame in range(1, FRAMES + 1):
        time = (frame - 1) % 40
        cycle = (frame - 1) // 40
        for name, keys in walk.items():
            bone = rig.pose.bones.get(name)
            if bone is None:
                raise RuntimeError('Missing walk control: ' + name)
            bone.rotation_mode = 'XYZ'
            for prop in ('location', 'rotation_euler'):
                if not any(prop in d for d in keys.values()):
                    continue
                value = smooth_value(keys, prop, time)
                if prop == 'location' and '0' in keys and '40' in keys and prop in keys['0'] and prop in keys['40']:
                    first = keys['0'][prop]['values']
                    last = keys['40'][prop]['values']
                    value = [v + cycle * (b - a) for v, a, b in zip(value, first, last)]
                setattr(bone, prop, value)
                bone.keyframe_insert(data_path=prop, frame=frame)
    subdivision = body.modifiers.new('Skin subdivision', 'SUBSURF')
    subdivision.levels = 1
    subdivision.render_levels = 1
    body.modifiers.new('Garment collision surface', 'COLLISION')
    body.collision.thickness_outer = 0.006
    body.collision.thickness_inner = 0.002
    body.collision.cloth_friction = 5
    for face in body.data.polygons:
        face.use_smooth = True
    wardrobe = bpy.data.objects.new(parent.name + ' | fitted wardrobe', None)
    bpy.context.collection.objects.link(wardrobe)
    constraint = wardrobe.constraints.new('CHILD_OF')
    constraint.target = rig
    constraint.subtarget = 'root'
    constraint.inverse_matrix = rig.data.bones['root'].matrix_local.inverted()
    return wardrobe, rig



def bind_tailoring(obj, rig):
    if obj.type == 'CURVE':
        data = bpy.data.meshes.new_from_object(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        replacement = bpy.data.objects.new(obj.name + ' | skinned', data)
        bpy.context.collection.objects.link(replacement)
        bpy.data.objects.remove(obj, do_unlink=True)
        obj = replacement
    if obj.type != 'MESH':
        return obj
    obj.parent = rig
    groups = {}
    for vertex in obj.data.vertices:
        coordinate, index, distance = BIND_KD.find(vertex.co)
        weights = BIND_WEIGHTS[index]
        total = sum(weight for name, weight in weights)
        for name, weight in weights:
            if name not in groups:
                groups[name] = obj.vertex_groups.new(name=name)
            groups[name].add([vertex.index], weight / total, 'REPLACE')
    armature = obj.modifiers.new('Follow the character rig', 'ARMATURE')
    armature.object = rig
    return obj


def prefit_skirt(obj, rig, wardrobe):
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    body = next(child for child in rig.children if child.name.endswith(' | model'))
    evaluated = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data = evaluated.to_mesh()
    transform = wardrobe.matrix_world.inverted() @ evaluated.matrix_world
    collision = BVHTree.FromPolygons([transform @ v.co for v in data.vertices], [tuple(p.vertices) for p in data.polygons])
    evaluated.to_mesh_clear()
    for vertex in obj.data.vertices:
        origin = Vector((0, -0.055, vertex.co.z))
        direction = vertex.co - origin
        distance = direction.length
        if distance < 0.0001:
            continue
        direction.normalize()
        hit = collision.ray_cast(origin + direction * 0.8, -direction, 0.8)[0]
        if hit is not None:
            clearance = (hit - origin).dot(direction) + 0.02
            if clearance > distance:
                vertex.co = origin + direction * clearance
    obj.data.update()


def cloth_skirt(obj, gold):
    obj.shape_key_clear()
    obj.modifiers.clear()
    data = bmesh.new()
    data.from_mesh(obj.data)
    bmesh.ops.remove_doubles(data, verts=list(data.verts), dist=0.000001)
    bmesh.ops.reverse_faces(data, faces=list(data.faces))
    data.to_mesh(obj.data)
    data.free()
    obj.data.update()
    obj.data.materials.append(gold)
    for face in obj.data.polygons:
        if min(obj.data.vertices[i].co.z for i in face.vertices) < 0.075:
            face.material_index = 1
    pin = obj.vertex_groups.new(name='Sewn waistband')
    for vertex in obj.data.vertices:
        weight = max(0, min(1, (vertex.co.z - 0.86) / 0.12))
        if weight:
            pin.add([vertex.index], weight, 'REPLACE')
    modifier = obj.modifiers.new('Silk cloth simulation', 'CLOTH')
    settings = modifier.settings
    settings.quality = 8
    settings.mass = 0.18
    settings.tension_stiffness = 20
    settings.compression_stiffness = 20
    settings.shear_stiffness = 12
    settings.bending_stiffness = 0.18
    settings.tension_damping = 8
    settings.compression_damping = 8
    settings.shear_damping = 8
    settings.bending_damping = 0.5
    settings.air_damping = 2
    settings.vertex_group_mass = pin.name
    settings.pin_stiffness = 1
    modifier.collision_settings.use_collision = True
    modifier.collision_settings.distance_min = 0.008
    modifier.collision_settings.collision_quality = 4
    modifier.collision_settings.use_self_collision = True
    modifier.collision_settings.self_distance_min = 0.006
    modifier.collision_settings.self_friction = 4
    modifier.point_cache.frame_start = 1
    modifier.point_cache.frame_end = FRAMES
    CLOTH_OBJECTS.append(obj)


def bake_fabric(frames):
    captured = {obj: [] for obj in CLOTH_OBJECTS}
    for frame in range(1, frames + 1):
        bpy.context.scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for obj in CLOTH_OBJECTS:
            evaluated = obj.evaluated_get(depsgraph)
            data = evaluated.to_mesh()
            if len(data.vertices) != len(obj.data.vertices):
                raise RuntimeError('Cloth topology changed during simulation')
            coordinates = array('f', [0]) * (len(data.vertices) * 3)
            data.vertices.foreach_get('co', coordinates)
            if any(not math.isfinite(value) or abs(value) > 20 for value in coordinates):
                raise RuntimeError('Unstable cloth simulation: ' + obj.name)
            captured[obj].append(coordinates)
            evaluated.to_mesh_clear()
        if frame % 8 == 0 or frame == 1:
            print(f'CLOTH_SIMULATION {frame}/{frames}', flush=True)
    for obj, samples in captured.items():
        obj.modifiers.clear()
        obj.shape_key_add(name='Tailored rest')
        for frame, coordinates in enumerate(samples, 1):
            key = obj.shape_key_add(name=f'Simulated silk {frame:04d}')
            key.data.foreach_set('co', coordinates)
            key.value = 0
            for output_frame in sorted({1, max(1, frame - 1), frame, min(frames, frame + 1), frames}):
                key.value = 1 if output_frame == frame else 0
                key.keyframe_insert(data_path='value', frame=output_frame)
        subdivision = obj.modifiers.new('Silk surface smoothing', 'SUBSURF')
        subdivision.levels = 1
        subdivision.render_levels = 1
        solid = obj.modifiers.new('Fabric thickness', 'SOLIDIFY')
        solid.thickness = 0.0012
        solid.offset = 0
        obj['motion_source'] = 'Blender Cloth, body collision and self collision; baked to shape keys'
    bpy.context.scene.frame_set(1)


def embroidery(parent, gold, pearl):
    paths, gems = [], []
    for strand in range(18):
        base = TAU * strand / 18
        paths.append([corset_point(j / 60, base + 0.08 * math.sin(j / 60 * 5), 0.0025) for j in range(61)])
        for tier in range(7):
            t = 0.11 + tier * 0.118
            a = base + 0.08 * math.sin(t * 5)
            for side in (-1, 1):
                leaf = []
                for j in range(19):
                    u = j / 18
                    leaf.append(corset_point(t + 0.068 * u, a + side * 0.12 * math.sin(math.pi * u), 0.0036))
                paths.append(leaf)
            gems.append((corset_point(t, a, 0.007), 0.0032))
    for t in (0.025, 0.055, 0.94, 0.985):
        paths.append([corset_point(t, TAU * j / 240, 0.003) for j in range(241)])
        for j in range(100):
            gems.append((corset_point(t, TAU * j / 100, 0.006), 0.0022))
    curves(parent.name + ' | goldwork fern embroidery', paths, 0.0009, gold, parent)
    beads(parent.name + ' | sewn seed pearls', gems, pearl, parent)


def gown(name, location, rotation, color, gold, pearl, finish, variant=0):
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = location
    root.rotation_euler.z = rotation
    model_root = root
    root, rig = walking_human(model_root, variant)
    footwear(rig, name, finish)
    silk = fabric(name + ' | warp and weft silk', color)
    corset = surface(name + ' | sweetheart corset', corset_point, 48, 192, silk, root)
    skirt = surface(name + ' | fitted bias skirt', lambda t, a: skirt_point(t, a, variant=variant), 40, 128, silk, root, False)
    bind_tailoring(corset, rig)
    prefit_skirt(skirt, rig, root)
    cloth_skirt(skirt, gold)
    embroidery(root, gold, pearl)
    necklace = [(0.064 * math.cos(a), -0.024 + 0.066 * math.sin(a), 1.352 + 0.009 * math.sin(a)) for a in [TAU * j / 120 for j in range(121)]]
    curves(name + ' | collar chain', [necklace], 0.0022, gold, root)
    beads(name + ' | necklace pearls', [(p, 0.0035) for p in necklace[::4]], pearl, root)
    for side in (-1, 1):
        paths = [[(side * 0.083 + 0.012 * math.cos(a), -0.047, 1.452 + 0.022 * math.sin(a)) for a in [TAU * j / 60 for j in range(61)]]]
        curves(name + ' | drop earrings', paths, 0.0018, gold, root)
        beads(name + ' | pendant pearls', [((side * 0.083, -0.047, 1.426), 0.006)], pearl, root)
    couture_silhouette(root, variant, silk, gold, pearl)
    for obj in list(root.children):
        if obj != skirt and (obj.type == 'CURVE' or (obj.type == 'MESH' and min((v.co.z for v in obj.data.vertices), default=0) > 0.96)):
            bind_tailoring(obj, rig)
    return model_root



def footwear(rig, name, finish):
    leather = material(name + ' | patent leather', (0.006, 0.008, 0.01), 0.1, 0.2)
    leather.node_tree.nodes['Principled BSDF'].inputs['Coat Weight'].default_value = 0.65
    for side, sign in (('L', 1), ('R', -1)):
        ankle = rig.data.bones['foot.' + side].head_local
        x = ankle.x
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=(x, -0.115, 0.035))
        shoe = bpy.context.object
        shoe.name = name + ' | pointed pump ' + side
        shoe.scale = (0.049, 0.131, 0.037)
        shoe.data.materials.append(leather)
        for poly in shoe.data.polygons:
            poly.use_smooth = True
        heel = box(name + ' | heel ' + side, (x, -0.01, 0.012), (0.025, 0.03, 0.025), finish, 0.005)
        for item in (shoe, heel):
            constraint = item.constraints.new('CHILD_OF')
            constraint.target = rig
            constraint.subtarget = 'foot.' + side
            constraint.inverse_matrix = rig.data.bones['foot.' + side].matrix_local.inverted()


def couture_silhouette(root, variant, silk, gold, pearl):
    organza = fabric(root.name + ' | metallic organza', ((0.012, 0.13, 0.085), (0.65, 0.43, 0.19), (0.19, 0.008, 0.029))[variant])
    organza.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value = 0.38
    paths = []
    if variant == 0:
        for side in (-1, 1):
            for petal in range(7):
                angle = -0.3 + petal * 0.19
                def point(t, a, side=side, angle=angle):
                    u = a / TAU
                    width = math.sin(math.pi * t) ** 0.7 * 0.085
                    x = side * (0.17 + t * (0.17 + angle * 0.035))
                    y = 0.02 + angle * 0.20 + width * math.cos(TAU * u)
                    z = 1.27 + (0.16 + angle * 0.06) * math.sin(t * math.pi * 0.85) + width * math.sin(TAU * u) * 0.4
                    return (x, y, z)
                surface('Verdigris | sculpted wing pleat', point, 28, 24, organza, root)
                paths.append([point(t / 50, 0) for t in range(51)])
    elif variant == 1:
        for petal in range(14):
            angle = TAU * petal / 14
            def point(t, a, angle=angle):
                width = math.sin(math.pi * t) * 0.12 * math.sin(a)
                radius = 0.13 + 0.33 * t
                return (radius * math.cos(angle) + width * math.sin(angle), -0.035 + radius * math.sin(angle) - width * math.cos(angle), 1.0 - 0.43 * t + 0.12 * math.sin(math.pi * t) + 0.02 * math.cos(a))
            surface('Champagne | overlapping orchid petal', point, 32, 24, organza, root, True)
        for side in (-1, 1):
            for petal in range(5):
                def point(t, a, side=side, petal=petal):
                    width = 0.09 * math.sin(math.pi * t)
                    return (side * (0.18 + 0.2 * t) + width * math.sin(a), 0.015 + (petal - 2) * 0.045 + width * math.cos(a), 1.26 + 0.30 * math.sin(t * 2.4) - petal * 0.014)
                surface('Champagne | orchid shoulder', point, 24, 24, organza, root)
    else:
        for layer in range(7):
            def point(t, a, layer=layer):
                u = a / TAU
                angle = -0.1 + u * math.pi * 1.4
                radius = 0.21 + 0.29 * t + 0.055 * math.sin(u * TAU * 4 + t * 3)
                return (radius * math.cos(angle), -0.01 + radius * math.sin(angle), 1.12 - layer * 0.098 - 0.18 * t + 0.075 * math.sin(u * TAU * 3) * t)
            surface('Garnet | cascading bias ruffle', point, 20, 128, organza, root, True)
            paths.append([point(1, TAU * j / 200) for j in range(201)])
    if paths:
        curves(root.name + ' | fine gold piping', paths, 0.0014, gold, root)
    beads(root.name + ' | emerald clasp', [((0, -0.192, 1.18), 0.012)], gold, root)

def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def area(name, location, target, energy, color, size, size_y=None):
    data = bpy.data.lights.new(name, 'AREA')
    data.energy = energy
    data.color = color
    data.shape = 'RECTANGLE'
    data.size = size
    data.size_y = size_y or size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    aim(obj, target)
    return obj


def lettering(name, text, location, size, mat, rotation=(math.pi / 2, 0, 0)):
    data = bpy.data.curves.new(name, 'FONT')
    data.body = text
    data.align_x = 'CENTER'
    data.size = size
    data.space_character = 1.3
    data.extrude = 0.0003
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = rotation
    data.materials.append(mat)
    return obj



def audience_outfit_material(name, asset, variant):
    mat = material(name, (0.04, 0.05, 0.07), 0, 0.6)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    image = nodes.new('ShaderNodeTexImage')
    image.image = bpy.data.images.load(str(ASSETS / 'clothes' / asset / (asset + '_diffuse.png')), check_existing=True)
    tint = nodes.new('ShaderNodeMixRGB')
    tint.blend_type = 'MULTIPLY'
    tint.inputs[0].default_value = 1
    tint.inputs[2].default_value = ((0.72, 0.79, 0.9, 1), (0.35, 0.48, 0.72, 1), (1, 0.83, 0.62, 1), (0.55, 0.56, 0.6, 1))[variant]
    links.new(image.outputs['Color'], tint.inputs[1])
    links.new(tint.outputs[0], nodes['Principled BSDF'].inputs['Base Color'])
    normal_path = ASSETS / 'clothes' / asset / (asset + '_normal.png')
    if normal_path.exists():
        texture = nodes.new('ShaderNodeTexImage')
        texture.image = bpy.data.images.load(str(normal_path), check_existing=True)
        texture.image.colorspace_settings.name = 'Non-Color'
        normal = nodes.new('ShaderNodeNormalMap')
        links.new(texture.outputs['Color'], normal.inputs['Color'])
        links.new(normal.outputs['Normal'], nodes['Principled BSDF'].inputs['Normal'])
    return mat


def seated_audience():
    module_name = 'bl_ext.blender_org.mpfb'
    if module_name not in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_enable(module=module_name)
    human_service = importlib.import_module(module_name + '.services.humanservice').HumanService
    target_service = importlib.import_module(module_name + '.services.targetservice').TargetService
    templates = []
    source_collection = bpy.data.collections.new('Audience | source rigs')
    bpy.context.scene.collection.children.link(source_collection)
    for variant in range(4):
        before = set(bpy.data.objects)
        female = variant % 2 == 0
        phenotype = target_service.get_default_macro_info_dict()
        phenotype.update(gender=0.0 if female else 1.0, age=0.35 + 0.08 * variant, weight=0.37 + 0.04 * variant)
        body = human_service.create_human(macro_detail_dict=phenotype)
        body.data.materials.clear()
        skin_file = 'young_caucasian_female2/young_lightskinned_female_diffuse2.png' if female else 'young_caucasian_male2/young_lightskinned_male_diffuse2.png'
        body.data.materials.append(textured_skin('Guest skin ' + str(variant), ASSETS / 'skins' / skin_file))
        rig = human_service.add_builtin_rig(body, 'default_no_toes')
        hair_asset = 'bob02' if female else 'short04'
        outfit = 'female_elegantsuit01' if variant == 0 else 'male_elegantsuit01'
        filenames = ('eyes/high-poly/high-poly.mhclo', 'eyebrows/eyebrow001/eyebrow001.mhclo', f'hair/{hair_asset}/{hair_asset}.mhclo', f'clothes/{outfit}/{outfit}.mhclo')
        for filename in filenames:
            old = set(bpy.data.objects)
            human_service.add_mhclo_asset(str(ASSETS / filename), body, asset_type='Clothes' if filename.startswith('clothes/') else 'Eyes' if filename.startswith('eyes/') else 'Hair', subdiv_levels=0)
            if filename.startswith('clothes/'):
                for obj in set(bpy.data.objects) - old:
                    if obj.type == 'MESH':
                        obj.data.materials.clear()
                        obj.data.materials.append(audience_outfit_material('Guest | tailored outfit ' + str(variant), outfit, variant))
        for side, sign in (('L', 1), ('R', -1)):
            for name, axis, angle in [('upperleg01.' + side, (1, 0, 0), -1.43), ('lowerleg01.' + side, (1, 0, 0), 1.4), ('upperarm01.' + side, (0, 1, 0), sign * 0.53), ('lowerarm01.' + side, (1, 0, 0), -0.8)]:
                bone = rig.pose.bones[name]
                rest = bone.bone.matrix_local.to_quaternion()
                bone.rotation_mode = 'QUATERNION'
                bone.rotation_quaternion = rest.inverted() @ Quaternion(axis, angle) @ rest
        for bone in rig.pose.bones:
            if bone.name.startswith('finger'):
                bone.rotation_mode = 'XYZ'
                bone.rotation_euler.x = 0.28 if '-1.' in bone.name else 0.18
        rig.location.z = -0.37
        footwear(rig, 'Guest ' + str(variant), material('Guest shoe sole ' + str(variant), (0.008, 0.006, 0.004), 0, 0.5))
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        vertices, faces, materials, indices, loop_uvs = [], [], [], [], []
        created = set(bpy.data.objects) - before
        for obj in created:
            if obj.type != 'MESH':
                continue
            evaluated = obj.evaluated_get(depsgraph)
            data = evaluated.to_mesh()
            offset, material_offset = len(vertices), len(materials)
            vertices.extend(tuple(evaluated.matrix_world @ v.co) for v in data.vertices)
            faces.extend(tuple(i + offset for i in poly.vertices) for poly in data.polygons)
            indices.extend(material_offset + poly.material_index for poly in data.polygons)
            materials.extend(obj.data.materials)
            if data.uv_layers.active:
                loop_uvs.extend(tuple(uv.uv) for uv in data.uv_layers.active.data)
            else:
                loop_uvs.extend((0, 0) for _ in data.loops)
            evaluated.to_mesh_clear()
        template = mesh('Seated guest template ' + str(variant), vertices, faces, None)
        for mat in materials:
            template.data.materials.append(mat)
        for poly, index in zip(template.data.polygons, indices):
            poly.material_index = index
        layer = template.data.uv_layers.new(name='Source asset UV')
        for item, uv in zip(layer.data, loop_uvs):
            item.uv = uv
        template.data.use_fake_user = True
        templates.append(template.data)
        for obj in list(created) + [template]:
            for collection in list(obj.users_collection):
                collection.objects.unlink(obj)
            source_collection.objects.link(obj)
        source_collection.hide_render = True
        source_collection.hide_viewport = True
    for side in (-1, 1):
        for i, y in enumerate((-0.4, 0.55, 1.5, 2.45, 3.4, 4.35, 5.3, 6.25)):
            guest = bpy.data.objects.new(f'Guest | {side} | {i:02d}', templates[(i + (side == 1)) % 4])
            bpy.context.collection.objects.link(guest)
            guest.location = (side * 2.15, y, 0.025)
            guest.rotation_euler.z = -side * math.pi / 2 + 0.035 * math.sin(i * 2)
            guest.scale = (1 + 0.035 * math.sin(i),) * 3


def stage(gold):
    black = material('Obsidian runway lacquer', (0.004, 0.006, 0.008), 0.48, 0.22)
    wall = material('Black velvet stage walls', (0.003, 0.005, 0.009), 0, 0.9)
    audience = material('Unlit audience velvet', (0.00008, 0.0001, 0.00014), 0, 0.95)
    led = material('Champagne LED', (0.7, 0.4, 0.16), 0.2, 0.25)
    shader = led.node_tree.nodes['Principled BSDF']
    shader.inputs['Emission Color'].default_value = (1, 0.55, 0.18, 1)
    shader.inputs['Emission Strength'].default_value = 3
    floor = box('Theatre floor', (0, 4, -0.07), (16, 24, 0.1), black)
    floor.modifiers.new('Floor cloth collision', 'COLLISION')
    box('Polished catwalk', (0, 2, -0.012), (2.15, 15, 0.024), black)
    box('Velvet backdrop', (0, 11, 2.5), (16, 0.1, 5), wall)
    for side in (-1, 1):
        box('Continuous runway edge light', (side * 1.09, 2, 0.009), (0.014, 15, 0.012), led, 0.004)
        for y in (-0.4, 0.55, 1.5, 2.45, 3.4, 4.35, 5.3, 6.25):
            box('Audience seat', (side * 2.15, y, 0.39), (0.48, 0.52, 0.08), wall)
            box('Audience seat back', (side * 2.4, y, 0.7), (0.055, 0.52, 0.65), wall)
    seated_audience()
    for y in (4.5, 6.8, 9.1):
        for side in (-1, 1):
            box('Brass portal upright', (side * 1.45, y, 1.7), (0.045, 0.045, 3.4), gold)
            box('Portal inner light', (side * 1.40, y - 0.015, 1.7), (0.013, 0.02, 3.35), led, 0.003)
        box('Brass portal lintel', (0, y, 3.4), (2.94, 0.045, 0.045), gold)
    lettering('Collection title', 'R E M I R D Y', (0, 10.8, 2.4), 0.23, gold)
    lettering('Collection subtitle', 'C O U T U R E   /   0 1', (0, 10.8, 2.11), 0.075, gold)
    area('Front beauty softbox', (-2.5, -4.2, 3.5), (0, 0, 1.15), 330, (1, 0.84, 0.7), 2.3, 3)
    area('Blue silk edge', (2.5, 1.0, 2.6), (0, 0, 1.1), 400, (0.35, 0.65, 1), 0.7, 3)
    area('Amber rim', (-2, 2.2, 3), (0, 0, 1.1), 550, (1, 0.5, 0.18), 0.8, 3)
    for y in (-1, 1.5, 4, 6.5, 9):
        area('Overhead runway strip', (0, y, 4), (0, y, 0), 170, (1, 0.88, 0.73), 1.7, 0.35)
    for side in (-1, 1):
        data = bpy.data.lights.new('Tracking followspot', 'SPOT')
        data.energy = 600
        data.color = (1, 0.8, 0.58)
        data.spot_size = 0.52
        data.spot_blend = 0.6
        obj = bpy.data.objects.new('Tracking followspot', data)
        bpy.context.collection.objects.link(obj)
        obj.location = (side * 2.5, -2.4, 4)
        for frame in range(1, FRAMES + 1):
            aim(obj, (0, 0.8 - (frame - 1) * 0.0196, 1.05))
            obj.keyframe_insert(data_path='rotation_euler', frame=frame)
    haze = bpy.data.materials.new('Subtle stage atmosphere')
    haze.use_nodes = True
    haze.node_tree.nodes.clear()
    volume = haze.node_tree.nodes.new('ShaderNodeVolumePrincipled')
    volume.inputs['Density'].default_value = 0.003
    volume.inputs['Anisotropy'].default_value = 0.25
    output = haze.node_tree.nodes.new('ShaderNodeOutputMaterial')
    haze.node_tree.links.new(volume.outputs['Volume'], output.inputs['Volume'])
    box('Atmospheric stage volume', (0, 3, 2.5), (10, 19, 5), haze, 0)
    world = bpy.data.worlds.new('Night theatre')
    world.use_nodes = True
    background = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
    background.inputs[0].default_value = (0.04, 0.06, 0.1, 1)
    background.inputs[1].default_value = 0.13
    bpy.context.scene.world = world


def camera(name, location, target, lens, fstop):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    aim(obj, target)
    data.lens = lens
    data.dof.use_dof = True
    data.dof.focus_distance = (Vector(location) - Vector(target)).length
    data.dof.aperture_fstop = fstop
    return obj


def build(args):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.context.collection.name = 'REMIRDY | couture gallery'
    gold = material('18k brushed champagne gold', (0.62, 0.38, 0.13), 0.86, 0.25)
    pearl = material('Warm freshwater nacre', (0.82, 0.72, 0.53), 0.28, 0.21)
    pearl.node_tree.nodes['Principled BSDF'].inputs['Coat Weight'].default_value = 0.4
    finish = material('Burnished bronze shoe hardware', (0.09, 0.072, 0.051), 0.73, 0.37)
    stage(gold)
    gown('01 | Verdigris', (0, 0.8, 0.025), 0, (0.008, 0.085, 0.06), gold, pearl, finish, 0)
    gown('02 | Champagne', (-0.55, 3.15, 0.025), 0, (0.5, 0.34, 0.16), gold, pearl, finish, 1)
    gown('03 | Garnet', (0.55, 5.4, 0.025), 0, (0.1, 0.007, 0.022), gold, pearl, finish, 2)
    gallery = camera('Gallery | 55mm dolly', (3.3, -7.3, 2.8), (0, 0.55, 1.08), 55, 7.1)
    detail = camera('Detail | 85mm textile study', (0.65, -1.47, 1.36), (0, -0.06, 1.13), 85, 6.3)
    for frame in range(1, FRAMES + 1):
        progress = (frame - 1) / (FRAMES - 1)
        gallery.location = (1.1 - 0.6 * progress, -5.8 - progress * 1.0, 1.65 - 0.12 * progress)
        aim(gallery, (0, 0.75 - progress * 2.8, 0.96))
        gallery.data.lens = 60 - 12 * progress
        gallery.data.dof.focus_distance = (gallery.location - Vector((0, 0.75 - progress * 2.8, 1.02))).length
        gallery.data.keyframe_insert(data_path='lens', frame=frame)
        gallery.data.keyframe_insert(data_path='dof.focus_distance', frame=frame)
        gallery.keyframe_insert(data_path='location', frame=frame)
        gallery.keyframe_insert(data_path='rotation_euler', frame=frame)
        detail.location = (0.52, -1.6 - progress * 2.8, 1.38)
        aim(detail, (0, 0.7 - progress * 2.8, 1.18))
        detail.data.lens = 85
        detail.data.dof.focus_distance = (detail.location - Vector((0, 0.7 - progress * 2.8, 1.18))).length
        detail.data.keyframe_insert(data_path='dof.focus_distance', frame=frame)
        detail.keyframe_insert(data_path='location', frame=frame)
        detail.keyframe_insert(data_path='rotation_euler', frame=frame)
    for collection in list(bpy.data.collections):
        if collection.name.startswith('Audience | source rigs'):
            for obj in list(collection.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.collections.remove(collection)
    scene = bpy.context.scene
    scene.name = 'REMIRDY | silk and goldwork'
    scene.camera = gallery if args.shot == 'gallery' else detail
    scene.render.engine = args.engine
    if args.engine == 'BLENDER_EEVEE':
        scene.eevee.taa_render_samples = args.samples
        scene.eevee.use_raytracing = True
    if args.device == 'METAL':
        preferences = bpy.context.preferences.addons['cycles'].preferences
        preferences.compute_device_type = 'METAL'
        preferences.get_devices()
        devices = [device for device in preferences.devices if device.type == 'METAL']
        if not devices:
            raise RuntimeError('No Metal render device is available')
        for device in preferences.devices:
            device.use = device.type == 'METAL'
        scene.cycles.device = 'GPU'
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 2
    scene.render.resolution_x = args.width
    scene.render.resolution_y = round(args.width * 0.625)
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.frame_start = 1
    scene.frame_end = FRAMES
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.exposure = -0.6
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.film_transparent = False
    scene.frame_set(1)
    scene['showcase_frames'] = FRAMES
    scene['garment_motion'] = 'Skinned bodices, physical Cloth skirts, collision and self collision, baked to portable shape keys.'
    return scene


def main():
    global ASSETS
    args = arguments()
    ASSETS = args.assets.expanduser().resolve()
    args.output = args.output.expanduser().resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    if not 21 <= args.cloth_frames <= FRAMES:
        raise ValueError(f'Cloth frame count must be between 21 and {FRAMES}')
    if args.mode == 'animation' and not 1 <= args.start <= args.end <= args.cloth_frames:
        raise ValueError('Render range must be inside the simulated frame range')
    scene = build(args)
    scene.frame_end = args.cloth_frames
    bake_fabric(args.cloth_frames)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output / 'remirdy_couture.blend'))
    if args.mode == 'still':
        scene.frame_set(21)
        scene.render.filepath = str(args.output / f'{args.shot}.png')
        bpy.ops.render.render(write_still=True)
    elif args.mode == 'animation':
        frames = args.output / (args.shot + '_frames')
        frames.mkdir(exist_ok=True)
        scene.frame_start = args.start
        scene.frame_end = args.end
        scene.render.filepath = str(frames / 'frame_')
        bpy.ops.render.render(animation=True)
    report = {'blender': bpy.app.version_string, 'shot': args.shot, 'objects': len(scene.objects), 'fps': scene.render.fps, 'frames': args.cloth_frames, 'resolution': [scene.render.resolution_x, scene.render.resolution_y], 'samples': args.samples, 'mode': args.mode}
    (args.output / f'{args.shot}_manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
