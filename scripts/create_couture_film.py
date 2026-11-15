from __future__ import annotations

import argparse
from array import array
import importlib.util
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree


ROOT = Path(__file__).resolve().parents[1]
FIRST = 25
LAST = 264
FPS = 24


def load_builder():
    spec = importlib.util.spec_from_file_location('couture_builder', Path(__file__).with_name('create_couture_showcase.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def actor_members(root):
    result = {root}
    while True:
        additions = {obj for obj in bpy.context.scene.objects if obj.parent in result or any(getattr(c, 'target', None) in result for c in obj.constraints)}
        if additions <= result:
            return result
        result |= additions


def actor_collection(root, name):
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    for obj in actor_members(root):
        for old in list(obj.users_collection):
            old.objects.unlink(obj)
        collection.objects.link(obj)
    return collection


def ease(value):
    value = min(1, max(0, value))
    return value * value * (3 - 2 * value)


def extend_performance(rig, hand_side):
    scene = bpy.context.scene
    scene.frame_set(144)
    controls = {}
    for name in ('left_hand_ik', 'right_hand_ik', 'left_elbow_ik', 'right_elbow_ik'):
        controls[name] = rig.pose.bones[name].matrix.copy()
    pelvis = rig.pose.bones['root'].head.copy()
    base_head = Vector(rig.pose.bones['head'].rotation_euler)
    base_chest = Vector(rig.pose.bones['spine02'].rotation_euler)
    foot_data = {}
    for side, short in (('left', 'L'), ('right', 'R')):
        control = rig.pose.bones[side + '_foot_ik']
        ankle = rig.pose.bones['foot.' + short].head.copy()
        correction = control.bone.matrix_local.to_3x3().inverted() @ Vector((0, 0, 0.073 - ankle.z))
        foot_data[side] = (control.location.copy(), control.rotation_euler.copy(), correction)
    rig.keyframe_insert(data_path='location', frame=144)
    rig.keyframe_insert(data_path='rotation_euler', frame=144)
    for frame in range(145, LAST + 1):
        scene.frame_set(frame)
        pose = ease((frame - 144) / 40)
        turn = ease((frame - 192) / 48)
        angle = (0.67 if hand_side == 'right' else -0.57) * turn
        rotation = Matrix.Rotation(angle, 4, 'Z')
        rig.rotation_euler.z = angle
        rig.location = pelvis - rotation @ pelvis
        rig.keyframe_insert(data_path='rotation_euler', frame=frame)
        rig.keyframe_insert(data_path='location', frame=frame)
        for side, sign in (('left', 1), ('right', -1)):
            hand = rig.pose.bones[side + '_hand_ik']
            elbow = rig.pose.bones[side + '_elbow_ik']
            hip_pose = side == hand_side
            hand_target = pelvis + Vector((sign * (0.175 if hip_pose else 0.215), -0.035 if hip_pose else -0.075, 0.15 if hip_pose else -0.02))
            elbow_target = pelvis + Vector((sign * (0.34 if hip_pose else 0.24), 0.035, 0.27 if hip_pose else 0.26))
            for bone, target in ((hand, hand_target), (elbow, elbow_target)):
                matrix = controls[bone.name].copy()
                matrix.translation = controls[bone.name].translation.lerp(target, pose)
                bone.matrix = matrix
                bone.keyframe_insert(data_path='location', frame=frame)
                bone.keyframe_insert(data_path='rotation_euler', frame=frame)
            foot = rig.pose.bones[side + '_foot_ik']
            start_location, start_rotation, correction = foot_data[side]
            foot.location = start_location + correction * pose
            foot.rotation_euler = Vector(start_rotation) * (1 - pose)
            if 192 < frame < 240:
                local = (frame - 192) / 48
                lift = max(0, math.sin(local * math.tau + (0 if side == 'left' else math.pi))) * 0.026
                foot.location += foot.bone.matrix_local.to_3x3().inverted() @ Vector((0, 0, lift))
            foot.keyframe_insert(data_path='location', frame=frame)
            foot.keyframe_insert(data_path='rotation_euler', frame=frame)
        head = rig.pose.bones['head']
        chest = rig.pose.bones['spine02']
        head.rotation_euler = base_head + Vector((0.015 * pose, 0.03 * pose, -0.085 * pose))
        chest.rotation_euler = base_chest + Vector((0, -0.022 * pose, 0.018 * pose))
        head.keyframe_insert(data_path='rotation_euler', frame=frame)
        chest.keyframe_insert(data_path='rotation_euler', frame=frame)
    scene.frame_set(1)


def simulator(obj, start, end, pin, quality=6):
    modifier = obj.modifiers.new('Physical runway fabric', 'CLOTH')
    settings = modifier.settings
    settings.quality = quality
    settings.mass = 0.14
    settings.tension_stiffness = 22
    settings.compression_stiffness = 22
    settings.shear_stiffness = 12
    settings.bending_stiffness = 0.16
    settings.tension_damping = 8
    settings.compression_damping = 8
    settings.shear_damping = 8
    settings.bending_damping = 0.6
    settings.air_damping = 2
    settings.vertex_group_mass = pin
    modifier.collision_settings.use_collision = True
    modifier.collision_settings.distance_min = 0.009
    modifier.collision_settings.collision_quality = 3
    modifier.collision_settings.use_self_collision = True
    modifier.collision_settings.self_distance_min = 0.005
    modifier.point_cache.frame_start = start
    modifier.point_cache.frame_end = end
    return modifier


def capture_simulation(objects, start, end):
    samples = {obj: [] for obj in objects}
    hidden_states = {obj: obj.hide_viewport for obj in bpy.context.scene.objects if obj.type == 'MESH'}
    for obj in hidden_states:
        if obj not in objects and not any(modifier.type == 'COLLISION' for modifier in obj.modifiers):
            obj.hide_viewport = True
    for frame in range(start, end + 1):
        bpy.context.scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for obj in objects:
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            if len(mesh.vertices) != len(obj.data.vertices):
                raise RuntimeError('Cloth topology changed')
            coordinates = array('f', [0]) * (len(mesh.vertices) * 3)
            mesh.vertices.foreach_get('co', coordinates)
            if any(not math.isfinite(value) or abs(value) > 20 for value in coordinates):
                raise RuntimeError('Unstable fabric: ' + obj.name)
            samples[obj].append(coordinates)
            evaluated.to_mesh_clear()
        if frame % 8 == 0 or frame == start:
            print(f'FILM_CLOTH {frame}/{end}', flush=True)
    for obj, hidden in hidden_states.items():
        obj.hide_viewport = hidden
    for obj in objects:
        for modifier in list(obj.modifiers):
            if modifier.type == 'CLOTH':
                obj.modifiers.remove(modifier)
        if not obj.data.shape_keys:
            obj.shape_key_add(name='Tailored rest')
        else:
            last_key = obj.data.shape_keys.key_blocks[-1]
            for frame in (start, end):
                last_key.value = 0
                last_key.keyframe_insert(data_path='value', frame=frame)
        for frame, coordinates in enumerate(samples[obj], start):
            key = obj.shape_key_add(name=f'Physical silk {frame:04d}')
            key.data.foreach_set('co', coordinates)
            for at in sorted({1, max(1, frame - 1), frame, min(end, frame + 1), end}):
                key.value = 1 if at == frame else 0
                key.keyframe_insert(data_path='value', frame=at)
        sub = obj.modifiers.new('Smooth fabric folds', 'SUBSURF')
        sub.levels = 1
        sub.render_levels = 1
        shell = obj.modifiers.new('Fabric thickness', 'SOLIDIFY')
        shell.thickness = 0.0012
        shell.offset = 0
    bpy.context.scene.frame_set(1)


def clone_actor(root, title):
    members = actor_members(root)
    copies = {}
    collection = bpy.data.collections.new(title)
    bpy.context.scene.collection.children.link(collection)
    for original in members:
        obj = original.copy()
        if original.data:
            obj.data = original.data.copy()
        obj.name = title + ' | ' + original.name
        obj['film_source_name'] = original.name
        if obj.animation_data and obj.animation_data.action:
            obj.animation_data.action = obj.animation_data.action.copy()
        collection.objects.link(obj)
        copies[original] = obj
    for original, obj in copies.items():
        obj.parent = copies.get(original.parent, original.parent)
        for constraint in obj.constraints:
            if hasattr(constraint, 'target') and constraint.target in copies:
                constraint.target = copies[constraint.target]
        for modifier in list(obj.modifiers):
            if modifier.type == 'ARMATURE':
                modifier.object = copies.get(modifier.object, modifier.object)
            if modifier.type == 'COLLISION':
                obj.modifiers.remove(modifier)
    return copies[root], collection


def recolor(collection, color):
    changed = {}
    for obj in collection.objects:
        if obj.type != 'MESH':
            continue
        for slot in obj.material_slots:
            mat = slot.material
            if not mat or not any(word in mat.name for word in ('warp and weft silk', 'metallic organza')):
                continue
            if mat not in changed:
                copy = mat.copy()
                copy.name = collection.name + ' | silk'
                for node in copy.node_tree.nodes:
                    if node.type == 'BSDF_PRINCIPLED':
                        node.inputs['Base Color'].default_value = (*color, 1)
                    if node.type == 'VALTORGB':
                        node.color_ramp.elements[0].color = (*(c * 0.65 for c in color), 1)
                        node.color_ramp.elements[-1].color = (*(min(1, c * 1.15) for c in color), 1)
                changed[mat] = copy
            slot.material = changed[mat]


def rest_context(rig):
    action = rig.animation_data.action
    rig.animation_data.action = None
    rig.location = (0, 0, 0)
    rig.rotation_euler = (0, 0, 0)
    for bone in rig.pose.bones:
        bone.location = (0, 0, 0)
        bone.rotation_mode = 'XYZ'
        bone.rotation_euler = (0, 0, 0)
        bone.scale = (1, 1, 1)
    bpy.context.view_layer.update()
    return action


def make_trouser_look(root, collection, builder, assets):
    rig = next(obj for obj in collection.objects if obj.type == 'ARMATURE')
    body = next(obj for obj in collection.objects if obj.name.endswith(' | model'))
    action = rest_context(rig)
    keep = {root, rig, body}
    keep |= {obj for obj in collection.objects if any(word in obj.name for word in ('high-poly', 'eyebrow', 'eyelashes', 'ponytail', 'pointed pump', ' | heel '))}
    for obj in list(collection.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    import importlib
    service = importlib.import_module('bl_ext.blender_org.mpfb.services.humanservice').HumanService
    before = set(bpy.data.objects)
    service.add_mhclo_asset(str(assets / 'clothes/male_elegantsuit01/male_elegantsuit01.mhclo'), body, asset_type='Clothes', subdiv_levels=1)
    for obj in set(bpy.data.objects) - before:
        for old in list(obj.users_collection):
            old.objects.unlink(obj)
        collection.objects.link(obj)
        if obj.type == 'MESH':
            obj.data.materials.clear()
            mat = builder.audience_outfit_material('Midnight silk wool tailoring', 'male_elegantsuit01', 1) if hasattr(builder, 'audience_outfit_material') else builder.fabric('Midnight silk wool tailoring', (0.006, 0.012, 0.035))
            obj.data.materials.append(mat)
    rig.animation_data.action = action
    bpy.context.scene.frame_set(1)


def binding_points(builder, body, rig):
    action = rest_context(rig)
    evaluated = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data = evaluated.to_mesh()
    builder.BIND_KD = KDTree(len(data.vertices))
    builder.BIND_WEIGHTS = []
    names = {group.index: group.name for group in body.vertex_groups if group.name in rig.data.bones}
    for vertex in data.vertices:
        builder.BIND_KD.insert(vertex.co, vertex.index)
        builder.BIND_WEIGHTS.append([(names[group.group], group.weight) for group in vertex.groups if group.group in names and group.weight > 0.001])
    builder.BIND_KD.balance()
    evaluated.to_mesh_clear()
    return action


def make_ivory_look(root, collection, builder):
    for obj in list(collection.objects):
        if 'overlapping orchid petal' in obj.name or 'orchid shoulder' in obj.name:
            bpy.data.objects.remove(obj, do_unlink=True)
    recolor(collection, (0.72, 0.65, 0.5))
    rig = next(obj for obj in collection.objects if obj.type == 'ARMATURE')
    body = next(obj for obj in collection.objects if obj.name.endswith(' | model'))
    wardrobe = next(obj for obj in collection.objects if obj.type == 'EMPTY' and 'fitted wardrobe' in obj.name)
    action = binding_points(builder, body, rig)
    silk = builder.fabric('Ivory duchess satin', (0.72, 0.65, 0.5))
    for side in (-1, 1):
        def point(t, a, side=side):
            radius = 0.043 + 0.075 * math.sin(math.pi * t) ** 0.7
            return (side * (0.19 + 0.19 * t) + radius * math.sin(a) * 0.6, -0.015 + radius * math.cos(a), 1.275 - 0.34 * t + radius * math.sin(a) * 0.4)
        obj = builder.surface('Ivory | sculptural bishop sleeve', point, 32, 48, silk, wardrobe)
        builder.bind_tailoring(obj, rig)
        for old in list(obj.users_collection):
            old.objects.unlink(obj)
        collection.objects.link(obj)
    rig.animation_data.action = action
    bpy.context.scene.frame_set(1)


def make_cape(root, collection, builder):
    for obj in list(collection.objects):
        if 'cascading bias ruffle' in obj.name or 'fine gold piping' in obj.name:
            bpy.data.objects.remove(obj, do_unlink=True)
    recolor(collection, (0.012, 0.045, 0.25))
    wardrobe = next(obj for obj in collection.objects if obj.type == 'EMPTY' and 'fitted wardrobe' in obj.name)
    material = builder.fabric('Sapphire | fluid organza cape', (0.014, 0.05, 0.22))
    material.node_tree.nodes['Principled BSDF'].inputs['Transmission Weight'].default_value = 0.12
    def point(t, a):
        u = a / math.tau
        width = 0.20 + 0.43 * t
        x = (u * 2 - 1) * width
        y = 0.12 + t * 0.48 + 0.025 * math.sin(u * math.tau * 12) * t
        return (x, y, 1.29 - 1.22 * t + 0.016 * math.cos(u * math.tau * 12) * t)
    cape = builder.surface('Sapphire | simulated shoulder cape', point, 32, 64, material, wardrobe)
    cape.modifiers.clear()
    for old in list(cape.users_collection):
        old.objects.unlink(cape)
    collection.objects.link(cape)
    pin = cape.vertex_groups.new(name='Sewn shoulder line')
    for vertex in cape.data.vertices:
        if vertex.co.z > 1.23:
            pin.add([vertex.index], 1, 'REPLACE')
    simulator(cape, 1, LAST, pin.name, quality=5)
    return cape



def finish_waist_seams(looks):
    pairs = []
    for look in looks:
        collection = bpy.data.collections[look['collection']]
        skirt = next((obj for obj in collection.objects if 'fitted bias skirt' in obj.name), None)
        corset = next((obj for obj in collection.objects if 'sweetheart corset' in obj.name), None)
        if skirt and corset:
            pairs.append((skirt, corset))
    states = {obj: obj.hide_viewport for obj in bpy.context.scene.objects}
    collection_states = {collection: collection.hide_viewport for collection in bpy.data.collections}
    for collection in bpy.data.collections:
        collection.hide_viewport = False
    corsets = {corset for skirt, corset in pairs}
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            obj.hide_viewport = obj not in corsets
    bands, bottoms = {}, {}
    for skirt, corset in pairs:
        uv_t = {}
        uv = skirt.data.uv_layers.active
        for loop in skirt.data.loops:
            uv_t[loop.vertex_index] = round(uv.data[loop.index].uv.y, 6)
        rings = {}
        for index, t in uv_t.items():
            rings.setdefault(t, []).append(index)
        bottom_t = min(t for t, indices in rings.items() if max(skirt.data.vertices[index].co.z for index in indices) <= 0.86)
        bottoms[skirt] = sorted((math.atan2(skirt.data.vertices[index].co.y + 0.055, skirt.data.vertices[index].co.x) % math.tau, index) for index in rings[bottom_t])
        bands[skirt] = [(index, skirt.data.vertices[index].co.copy(), 1 - t / bottom_t) for index, t in uv_t.items() if t < bottom_t]
    anchor_map = {}
    for skirt, items in bands.items():
        anchor_map[skirt] = {}
        for index, rest, factor in items:
            angle = math.atan2(rest.y + 0.055, rest.x) % math.tau
            anchor_map[skirt][index] = min(bottoms[skirt], key=lambda item: min(abs(item[0] - angle), math.tau - abs(item[0] - angle)))[1]
    for frame in range(1, LAST + 1):
        bpy.context.scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for skirt, corset in pairs:
            key = next((key for key in skirt.data.shape_keys.key_blocks if key.name.endswith(f'{frame:04d}')), None)
            if key is None:
                continue
            parent = skirt.parent.evaluated_get(depsgraph)
            skirt_world = parent.matrix_world @ skirt.matrix_parent_inverse @ skirt.matrix_basis
            evaluated = corset.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            transform = skirt_world.inverted() @ evaluated.matrix_world
            waist = [transform @ mesh.vertices[index].co for index in range(193)]
            center = sum(waist[:-1], Vector()) / 192
            if abs(center.x) > 0.5 or abs(center.y) > 0.5 or not 0.7 < center.z < 1.25:
                raise RuntimeError('Waist coordinate mismatch: ' + skirt.name)
            for index, rest, factor in bands[skirt]:
                factor = min(1, max(0, factor))
                angle = math.atan2(rest.y + 0.055, rest.x) % math.tau
                u = angle / math.tau * 192
                left = int(u) % 192
                top = waist[left].lerp(waist[left + 1], u - int(u))
                outward = Vector((top.x - center.x, top.y - center.y, 0)).normalized()
                top += outward * 0.003
                lower_index = anchor_map[skirt][index]
                lower = key.data[lower_index].co.copy()
                target = lower.lerp(top, factor)
                target += outward * (0.003 * math.sin(angle * 28) * math.sin(math.pi * factor))
                key.data[index].co = target
            evaluated.to_mesh_clear()
        if frame % 48 == 0:
            print(f'WAIST_FINISH {frame}/{LAST}', flush=True)
    for obj, hidden in states.items():
        obj.hide_viewport = hidden
    for collection, hidden in collection_states.items():
        collection.hide_viewport = hidden
    bpy.context.scene.frame_set(48)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scene', type=Path, default=ROOT / 'outputs/couture/remirdy_couture.blend')
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/couture_film')
    parser.add_argument('--assets', type=Path, default=ROOT / 'outputs/couture/source_assets')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    module = 'bl_ext.blender_org.mpfb'
    if module not in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_enable(module=module)
    builder = load_builder()
    builder.ASSETS = args.assets.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    roots = [bpy.data.objects[name] for name in ('01 | Verdigris', '02 | Champagne', '03 | Garnet')]
    looks = []
    titles = ('01 | Verdigris', '02 | Champagne orchid', '03 | Garnet cascade')
    for index, root in enumerate(roots):
        collection = actor_collection(root, titles[index])
        rig = next(obj for obj in collection.objects if obj.type == 'ARMATURE')
        extend_performance(rig, 'left' if index == 1 else 'right')
        looks.append({'name':titles[index], 'collection':collection.name, 'root':root.name, 'rig':rig.name})
    skirts = [next(obj for obj in bpy.data.collections[item['collection']].objects if 'fitted bias skirt' in obj.name) for item in looks]
    for skirt in skirts:
        skirt.modifiers.clear()
        simulator(skirt, 145, LAST, 'Sewn waistband')
    capture_simulation(skirts, 145, LAST)
    bpy.context.scene.frame_set(1)
    for source, title in ((roots[0], '04 | Midnight tailoring'), (roots[2], '05 | Sapphire cape'), (roots[1], '06 | Ivory sculpture')):
        root, collection = clone_actor(source, title)
        rig = next(obj for obj in collection.objects if obj.type == 'ARMATURE')
        looks.append({'name':title, 'collection':collection.name, 'root':root.name, 'rig':rig.name})
        if title.startswith('04'):
            make_trouser_look(root, collection, builder, args.assets.resolve())
        elif title.startswith('06'):
            make_ivory_look(root, collection, builder)
    cape_collection = bpy.data.collections[looks[4]['collection']]
    cape = make_cape(bpy.data.objects[looks[4]['root']], cape_collection, builder)
    capture_simulation([cape], 1, LAST)
    finish_waist_seams(looks)
    scene = bpy.context.scene
    scene.frame_end = LAST
    scene.render.fps = FPS
    scene['film_looks'] = json.dumps(looks)
    scene['film_source_frames_per_look'] = LAST - FIRST + 1
    scene['film_frames_per_look'] = 80
    scene['film_source_start'] = FIRST
    scene['film_duration_seconds'] = 20
    scene['film_playback_speed'] = 3
    scene.name = 'REMIRDY | six look couture film'
    for index, look in enumerate(looks):
        bpy.data.collections[look['collection']].hide_render = index >= 3
        bpy.data.collections[look['collection']].hide_viewport = index >= 3
    scene.frame_set(48)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    path = args.output / 'remirdy_couture_film.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(path.resolve()))
    (args.output / 'film_manifest.json').write_text(json.dumps({'fps':FPS, 'duration_seconds':20, 'render_frames':480, 'playback_speed':3, 'source_frames':[FIRST,LAST], 'looks':looks}, indent=2)+'\n')
    print('FILM_SCENE_COMPLETE',path,flush=True)


if __name__ == '__main__':
    main()
