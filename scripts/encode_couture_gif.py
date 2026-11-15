from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('frames', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--width', type=int, default=720)
    parser.add_argument('--film-teaser', action='store_true')
    args = parser.parse_args()
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
    if args.film_teaser:
        if len(frames) not in (480, 1440):
            raise ValueError('A complete 20- or 60-second film is required for the six-look teaser')
        per_look = len(frames) // 6
        starts = (60, 140, 175, 60, 140, 175)
        starts = [min(round(start * per_look / 240), per_look - 24) for start in starts]
        frames = [frame for look, start in enumerate(starts) for frame in frames[look * per_look + start:look * per_look + start + 24]]
    images = []
    with Image.open(frames[0]) as first:
        size = (args.width, round(first.height * args.width / first.width))
    palette_samples = []
    for index in sorted({round(i * (len(frames) - 1) / 7) for i in range(8)}):
        with Image.open(frames[index]) as source:
            palette_samples.append(source.convert('RGB').resize((160, 100), Image.Resampling.LANCZOS))
    sheet = Image.new('RGB', (160, len(palette_samples) * 100))
    for index, sample in enumerate(palette_samples):
        sheet.paste(sample, (0, index * 100))
    palette = sheet.quantize(colors=192, method=Image.Quantize.MEDIANCUT)
    for path in frames:
        with Image.open(path) as source:
            images.append(source.convert('RGB').resize(size, Image.Resampling.LANCZOS).quantize(palette=palette, dither=Image.Dither.NONE))
    duration = [round((i + 1) * 100 / 24) * 10 - round(i * 100 / 24) * 10 for i in range(len(images))]
    images[0].save(args.output, save_all=True, append_images=images[1:], duration=duration, loop=0, optimize=True, disposal=1)
    print(f'Encoded {len(images)} frames, {sum(duration)} ms, {args.output.stat().st_size} bytes')


if __name__ == '__main__':
    main()
