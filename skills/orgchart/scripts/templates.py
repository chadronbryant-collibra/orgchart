#!/usr/bin/env python3
"""List and validate the bundled template catalog without dependencies."""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODES = {'compact_hierarchy', 'leadership_bands', 'functional_columns', 'matrix_relationships', 'enterprise_overview'}

def validate(data, root=ROOT):
    errors = []
    if not isinstance(data, dict) or set(data) != {'version', 'folder_url', 'templates'} or data.get('version') != 1:
        return ['Manifest must contain version 1, folder_url and templates.']
    if not isinstance(data['folder_url'], str) or not data['folder_url'].startswith('https://'):
        errors.append('folder_url must be an https URL.')
    entries = data['templates']
    if not isinstance(entries, list) or not entries:
        return errors + ['templates must be a nonempty list.']
    ids = set()
    allowed = {'id','name','kind','layouts','file_id','home','upstream_file_id','upstream_description','audience','last_checked','path'}
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append('Each template must be an object.'); continue
        ident = entry.get('id')
        if not isinstance(ident, str) or not re.fullmatch(r'[a-z0-9-]+', ident) or ident in ids:
            errors.append(f'Invalid or duplicate template id: {ident!r}')
        ids.add(ident)
        if set(entry) - allowed or not isinstance(entry.get('name'), str) or not entry.get('name'):
            errors.append(f'{ident}: invalid fields or name.')
        modes = entry.get('layouts')
        if not isinstance(modes, list) or not modes or any(x not in MODES for x in modes) or len(set(modes)) != len(modes):
            errors.append(f'{ident}: invalid layouts.')
        kind = entry.get('kind')
        if kind not in {'google-slides','built-in','roster-starter'}:
            errors.append(f'{ident}: invalid kind.')
        if kind == 'google-slides':
            for field in ('file_id','home','audience','last_checked'):
                if not isinstance(entry.get(field), str) or not entry.get(field): errors.append(f'{ident}: missing {field}.')
            try: datetime.date.fromisoformat(entry.get('last_checked', ''))
            except (ValueError, TypeError): errors.append(f'{ident}: invalid last_checked date.')
        if kind == 'roster-starter':
            path = entry.get('path')
            if not isinstance(path, str) or not path.startswith('examples/starters/') or '..' in Path(path).parts or not (root / path).is_file():
                errors.append(f'{ident}: starter file is missing or outside examples/starters.')
    return errors

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['list','validate'])
    parser.add_argument('--manifest', type=Path, default=ROOT/'templates/manifest.json')
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text())
        errors = validate(data)
        if errors:
            print('\n'.join(errors), file=sys.stderr); return 1
        if args.command == 'validate': print('Manifest valid.')
        else:
            print('ID                   KIND             NAME')
            for e in data['templates']: print(f"{e['id']:20} {e['kind']:16} {e['name']}")
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f'Manifest error: {exc}', file=sys.stderr); return 1
if __name__ == '__main__': sys.exit(main())
