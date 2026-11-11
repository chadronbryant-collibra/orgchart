#!/usr/bin/env python3
"""Build the uploadable Desktop skill archive."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
def build(root=ROOT):
    skill = root / 'skills/orgchart'
    destination = root / 'dist/orgchart.zip'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, 'w', ZIP_DEFLATED) as archive:
        for path in sorted(skill.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                archive.write(path, 'orgchart/' + path.relative_to(skill).as_posix())
    return destination
if __name__ == '__main__': print(f'Built {build()}')
