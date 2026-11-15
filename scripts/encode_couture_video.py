from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
import sys

import bpy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('frames', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=800)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    marker = args.frames / '.compression_active'
    deadline = time.monotonic() + 300
    while marker.exists():
        try:
            os.kill(int(marker.read_text()), 0)
        except (OSError, ValueError):
            break
        if time.monotonic() > deadline:
            raise RuntimeError('Frame compression did not finish')
        time.sleep(0.2)
    indexed = {}
    for path in args.frames.glob('frame_*'):
        if path.suffix.lower() not in ('.png', '.webp'):
            continue
        index = int(path.stem.rsplit('_', 1)[1])
        if index not in indexed or path.suffix.lower() == '.png':
            indexed[index] = path
    frames = [indexed[index] for index in sorted(indexed)]
    if not frames:
        raise ValueError('No rendered image frames found')
    indices = [int(frame.stem.rsplit('_', 1)[1]) for frame in frames]
    if indices != list(range(indices[0], indices[0] + len(indices))):
        raise ValueError('The frame sequence has missing frames')
    scene = bpy.context.scene
    editor = scene.sequence_editor_create()
    for strip in list(editor.strips):
        editor.strips.remove(strip)
    strip = editor.strips.new_image('Couture render sequence', str(frames[0]), channel=1, frame_start=1)
    for frame in frames[1:]:
        strip.elements.append(frame.name)
    strip.frame_final_duration = len(frames)
    strip.colorspace_settings.name = 'sRGB'
    scene.frame_start = 1
    scene.frame_end = len(frames)
    scene.render.fps = 24
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 2
    scene.render.use_sequencer = True
    scene.view_settings.view_transform = 'Standard'
    scene.render.image_settings.media_type = 'VIDEO'
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'HIGH'
    scene.render.filepath = str(args.output.expanduser().resolve())
    bpy.ops.render.render(animation=True)


if __name__ == '__main__':
    main()
