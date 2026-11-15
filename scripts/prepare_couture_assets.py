from __future__ import annotations

import argparse
from pathlib import Path
import zipfile


PREFIXES = (
    'skins/young_caucasian_female2/',
    'skins/young_african_female/',
    'skins/young_asian_female/',
    'skins/young_caucasian_male2/',
    'eyes/high-poly/',
    'hair/ponytail01/',
    'hair/bob02/',
    'hair/braid01/',
    'hair/short04/',
    'eyebrows/eyebrow001/',
    'eyelashes/eyelashes01/',
    'clothes/male_elegantsuit01/',
    'clothes/female_elegantsuit01/',
)
EXTRA_FILES = {'eyes/materials/brown.mhmat', 'eyes/materials/brown_eye.png'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, default=Path('outputs/couture/source_assets'))
    args = parser.parse_args()
    root = args.output.expanduser().resolve()
    count = 0
    with zipfile.ZipFile(args.archive) as archive:
        for entry in archive.infolist():
            name = entry.filename
            if entry.is_dir() or name.endswith('.thumb'):
                continue
            if not name.startswith(PREFIXES) and name not in EXTRA_FILES:
                continue
            destination = (root / name).resolve()
            if not destination.is_relative_to(root):
                raise ValueError('Archive entry leaves the output directory')
            if entry.file_size > 32 * 1024 * 1024:
                raise ValueError('Unexpectedly large source asset')
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(entry))
            count += 1
    print(f'Prepared {count} source files in {root}')


if __name__ == '__main__':
    main()
