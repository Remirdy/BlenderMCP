from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import struct
import sys
import time

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]


def valid_frame(path, width, height):
    if not path.exists():
        alternative = path.with_suffix('.webp')
        if not alternative.exists():
            return False
        with alternative.open('rb') as source:
            header = source.read(25)
        if len(header) != 25 or header[:4] != b'RIFF' or header[8:16] != b'WEBPVP8L' or header[20] != 0x2f:
            return False
        size = struct.unpack('<I', header[4:8])[0] + 8
        dimensions = struct.unpack('<I', header[21:25])[0]
        return alternative.stat().st_size == size and (dimensions & 0x3fff) + 1 == width and ((dimensions >> 14) & 0x3fff) + 1 == height
    with path.open('rb') as source:
        header = source.read(24)
        try:
            source.seek(-12, 2)
        except OSError:
            return False
        if source.read(12) != b'\x00\x00\x00\x00IEND\xaeB\x60\x82':
            return False
    return len(header) == 24 and header[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', header[16:24]) == (width, height)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/couture_film/film_frames_20s')
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--samples', type=int, default=16)
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--end', type=int)
    parser.add_argument('--duration', type=int, choices=(20, 60), default=20)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--engine', choices=('BLENDER_EEVEE', 'CYCLES'), default='BLENDER_EEVEE')
    parser.add_argument('--device', choices=('CPU', 'METAL'), default='CPU')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    total_frames = args.duration * 24
    frames_per_look = total_frames // 6
    if args.end is None:
        args.end = total_frames
    if not 1 <= args.start <= args.end <= total_frames:
        raise ValueError(f'Film output range must be inside frames 1–{total_frames}')
    scene = bpy.context.scene
    looks = json.loads(scene['film_looks'])
    scene.render.engine = args.engine
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.render.resolution_x = args.width
    scene.render.resolution_y = round(args.width * 0.625)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.media_type = 'IMAGE'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.fps = 24
    if args.engine == 'BLENDER_EEVEE':
        scene.eevee.taa_render_samples = args.samples
        scene.eevee.use_raytracing = False
        scene.eevee.shadow_pool_size = '1024'
        bpy.data.objects['Atmospheric stage volume'].hide_render = True
    else:
        scene.cycles.samples = args.samples
        scene.cycles.use_denoising = True
        if args.device == 'METAL':
            preferences = bpy.context.preferences.addons['cycles'].preferences
            preferences.compute_device_type = 'METAL'
            preferences.get_devices()
            for device in preferences.devices:
                device.use = device.type == 'METAL'
            scene.cycles.device = 'GPU'
    data = bpy.data.cameras.new('Remirdy | film camera')
    camera = bpy.data.objects.new('Remirdy | film camera', data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    data.dof.use_dof = True
    data.dof.aperture_fstop = 6.3
    args.output.mkdir(parents=True, exist_ok=True)
    lights = [obj for obj in scene.objects if obj.type == 'LIGHT']
    shadow_defaults = {obj: obj.data.use_shadow for obj in lights}
    active_lighting_look = None
    for output_frame in range(args.start, args.end + 1):
        path = args.output / f'frame_{output_frame:06d}.png'
        if args.resume and valid_frame(path, scene.render.resolution_x, scene.render.resolution_y):
            continue
        look_index = (output_frame - 1) // frames_per_look
        local = round(((output_frame - 1) % frames_per_look) * 239 / (frames_per_look - 1))
        source_frame = local + 25
        look = looks[look_index]
        if active_lighting_look != look_index:
            root = bpy.data.objects[look['root']]
            overhead = min((obj for obj in lights if obj.name.startswith('Overhead runway strip')), key=lambda obj: abs(obj.location.y - (root.location.y - 1.4)))
            for light in lights:
                key = light.name.startswith('Tracking followspot') or light.name == 'Front beauty softbox' or light == overhead
                light.data.use_shadow = shadow_defaults[light] if args.engine == 'CYCLES' else key
            active_lighting_look = look_index
        for index, item in enumerate(looks):
            collection = bpy.data.collections[item['collection']]
            visible = index == look_index or (look_index == 0 and local < 96 and index < 3)
            collection.hide_render = not visible
            collection.hide_viewport = not visible
        scene.frame_set(source_frame)
        rig = bpy.data.objects[look['rig']]
        pelvis = rig.matrix_world @ rig.pose.bones['root'].head
        target = pelvis + Vector((0, -0.015, 0.14))
        if local < 96:
            offset = Vector(((0.8 if look_index % 2 == 0 else -0.9) + 0.15 * math.sin(local / 95 * math.pi), -4.7, 0.40))
            data.lens = 52
            target.z = 0.96
        elif local < 168:
            offset = Vector((0.62 if look_index % 2 == 0 else -0.58, -2.8, 0.15))
            target.z = 1.20
            data.lens = 60
        else:
            offset = Vector(((0.8 if look_index in (1, 5) else 0.4 if look_index == 4 else -0.8), -4.7, 0.34))
            target.z = 0.98
            data.lens = 50
        camera.location = target + offset
        camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
        data.dof.focus_distance = offset.length
        scene.render.filepath = str(path.resolve())
        started = time.monotonic()
        bpy.ops.render.render(write_still=True)
        print(f'FILM_FRAME {output_frame}/{total_frames} LOOK {look_index + 1} SOURCE {source_frame} SECONDS {time.monotonic() - started:.2f}', flush=True)
    print('FILM_RENDER_COMPLETE', flush=True)


if __name__ == '__main__':
    main()
