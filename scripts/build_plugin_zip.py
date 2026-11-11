#!/usr/bin/env python3
"""Build the organization upload archive (Claude "Upload a plugin" layout).

The zip holds the plugin root itself: .claude-plugin/plugin.json,
skills/orgchart/**, README.md and CHANGELOG.md. No tests, docs or tooling.
"""
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def _keep(path):
    return path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc' and path.name != '.DS_Store'


def build(root=ROOT):
    manifest = json.loads((root / '.claude-plugin/plugin.json').read_text())
    destination = root / 'dist' / f"orgchart-plugin-v{manifest['version']}.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, 'w', ZIP_DEFLATED) as archive:
        archive.write(root / '.claude-plugin/plugin.json', '.claude-plugin/plugin.json')
        for name in ('README.md', 'CHANGELOG.md'):
            archive.write(root / name, name)
        for path in sorted((root / 'skills').rglob('*')):
            if _keep(path):
                archive.write(path, path.relative_to(root).as_posix())
    return destination


if __name__ == '__main__':
    print(f'Built {build()}')
