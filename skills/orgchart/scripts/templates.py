#!/usr/bin/env python3
"""List and validate the bundled template catalog without dependencies."""
import argparse
import copy
import datetime
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME_DIR = ROOT / 'templates/themes'
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
    allowed = {'id','name','kind','layouts','file_id','home','upstream_file_id','upstream_description','audience','last_checked','path','theme','layout_id'}
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
            for field in ('file_id','home','audience','last_checked','theme','layout_id'):
                if not isinstance(entry.get(field), str) or not entry.get(field): errors.append(f'{ident}: missing {field}.')
            try: datetime.date.fromisoformat(entry.get('last_checked', ''))
            except (ValueError, TypeError): errors.append(f'{ident}: invalid last_checked date.')
        if kind in {'google-slides', 'built-in'} and entry.get('theme') not in theme_ids():
            errors.append(f'{ident}: invalid theme.')
        if kind == 'roster-starter':
            path = entry.get('path')
            if not isinstance(path, str) or not path.startswith('examples/starters/') or '..' in Path(path).parts or not (root / path).is_file():
                errors.append(f'{ident}: starter file is missing or outside examples/starters.')
    return errors

# ---------------------------------------------------------------------------
# Themes: data-driven look for the compiled Slides requests.
# ---------------------------------------------------------------------------
DASHES = ('SOLID', 'DOT', 'DASH', 'DASH_DOT', 'LONG_DASH', 'LONG_DASH_DOT', 'SYS_DASH', 'SYS_DOT')
STATUSES = ('filled', 'open', 'planned', 'resigned', 'other', 'context', 'contingent')
PATTERN_STATUSES = ('filled', 'open', 'planned', 'resigned', 'contingent')
COLOR_KEYS = ('ink', 'muted', 'line', 'matrix_line', 'surface')
TOP_FIELDS = ('id', 'description', 'extends', 'accent', 'colors', 'background', 'statuses', 'font',
              'title', 'card_corners', 'table', 'footer', 'color_by_function')
NESTED = {
    'colors': COLOR_KEYS,
    'statuses': STATUSES,
    'title': ('size', 'color', 'align', 'bold'),
    'table': ('header_fill', 'body_fill'),
    'footer': ('text', 'size', 'color'),
    'color_by_function': ('enabled', 'palette'),
}
STATUS_FIELDS = ('fill', 'outline', 'dash')
DEFAULT_FUNCTION_PALETTE = [{'fill': f, 'outline': o} for f, o in [
    ('FFD6A5', '9C4A00'), ('CFF5C0', '2E7D32'), ('A8EEF5', '00707A'), ('B7D0FF', '1F4E9C'),
    ('D3CBFF', '5B3FB5'), ('FFC9F2', '9C2F9C'), ('F6F2A3', '7A7000'), ('FFB8B8', 'B3261E')]]
HEX = re.compile(r'^#?([0-9A-Fa-f]{6})$')

class ThemeError(ValueError):
    """A theme problem written for a non-technical reader."""

def _near(name, options):
    close = difflib.get_close_matches(str(name), options, n=1)
    return f" Did you mean '{close[0]}'?" if close else ''

def theme_files(directory=None):
    return sorted(p for p in (directory or THEME_DIR).glob('*.json') if not p.name.endswith('.schema.json'))

def builtin_themes(directory=None):
    """Raw built-in theme definitions keyed by id, in a stable order."""
    result = {}
    for path in theme_files(directory):
        data = json.loads(path.read_text(encoding='utf-8'))
        result[data['id']] = data
    order = ['collibra-2026', 'neutral']
    return {k: result[k] for k in order + sorted(set(result) - set(order)) if k in result}

def dark_background(theme):
    """True when a resolved theme paints a dark page background."""
    bg = theme.get('background') if isinstance(theme, dict) else None
    return bool(bg) and _luminance(bg) < 0.25

def branded_layout_ids(manifest_path=None):
    """Layout IDs of organization templates whose layouts carry a logo or artwork."""
    path = Path(manifest_path) if manifest_path else ROOT / 'templates/manifest.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    return {e['layout_id'] for e in data['templates'] if e.get('kind') == 'google-slides' and e.get('layout_id')}

def theme_ids():
    return set(builtin_themes())

def _merge(base, over):
    out = copy.deepcopy(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out

def _hex(value, where, accent=None):
    if isinstance(value, str) and value in ('@accent', '@ink', '@muted'):
        return value
    match = HEX.match(value) if isinstance(value, str) else None
    if not match:
        raise ThemeError(f"The colour {value!r} in '{where}' is not a hex colour. "
                         "Write six hex digits such as #1A2B3C (a leading # is optional).")
    return match.group(1).upper()

def _check_keys(obj, allowed, where):
    if not isinstance(obj, dict):
        raise ThemeError(f"'{where}' should be an object with named settings, not {type(obj).__name__}.")
    for key in obj:
        if key not in allowed:
            raise ThemeError(f"Unknown setting '{where + '.' if where else ''}{key}'.{_near(key, allowed)} "
                             f"Allowed here: {', '.join(allowed)}.")

def _positive_number(value, where, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise ThemeError(f"'{where}' must be a number from {low} to {high}.")
    return value

def resolve_theme(base='neutral', overlay=None, accent=None, color_by_function=None, footer=None):
    """Merge an optional user overlay over a built-in base and validate the result.

    Returns a fully resolved theme: every colour is six uppercase hex digits and
    every "@accent" style reference is replaced. Raises ThemeError otherwise.
    """
    themes = builtin_themes()
    if base not in themes:
        raise ThemeError(f"Unknown theme '{base}'.{_near(base, list(themes))} Available themes: {', '.join(themes)}.")
    overlay = overlay or {}
    if not isinstance(overlay, dict):
        raise ThemeError('A theme file must hold one JSON object at the top level.')
    _check_keys(overlay, TOP_FIELDS, '')
    raw = _merge(themes[base], {k: v for k, v in overlay.items() if k not in ('id', 'extends')})
    raw['id'] = str(overlay.get('id') or base)
    raw.pop('extends', None)
    for key, allowed in NESTED.items():
        if isinstance(raw.get(key), dict):
            _check_keys(raw[key], allowed, key)
    for name, entry in raw['statuses'].items():
        _check_keys(entry, STATUS_FIELDS, f'statuses.{name}')
    if accent is not None:
        raw['accent'] = accent
    accent_hex = _hex(raw['accent'], 'accent')
    if accent_hex.startswith('@'):
        raise ThemeError("'accent' must be a hex colour, not a reference.")
    out = {'id': raw['id'], 'description': str(raw.get('description', '')), 'accent': accent_hex}
    colors = {}
    for key in COLOR_KEYS:
        colors[key] = _hex(raw['colors'].get(key), f'colors.{key}')
    for key in ('ink', 'muted'):
        if colors[key].startswith('@'):
            raise ThemeError(f"'colors.{key}' must be a hex colour, not a reference.")
    def ref(value):
        return {'@accent': accent_hex, '@ink': colors['ink'], '@muted': colors['muted']}.get(value, value)
    out['colors'] = {k: ref(v) for k, v in colors.items()}
    bg = raw.get('background')
    out['background'] = None if bg in (None, '') else ref(_hex(bg, 'background'))
    out['statuses'] = {}
    for name in STATUSES:
        entry = raw['statuses'].get(name)
        if entry is None:
            raise ThemeError(f"The theme has no look for the '{name}' status. Add statuses.{name} with fill, outline and dash.")
        dash = entry.get('dash')
        if dash not in DASHES:
            raise ThemeError(f"The line pattern {dash!r} in 'statuses.{name}.dash' is not available. Choose one of: {', '.join(DASHES)}.")
        out['statuses'][name] = {'fill': ref(_hex(entry.get('fill'), f'statuses.{name}.fill')),
                                 'outline': ref(_hex(entry.get('outline'), f'statuses.{name}.outline')), 'dash': dash}
    font = raw.get('font')
    if not isinstance(font, str) or not re.fullmatch(r"[A-Za-z0-9 '\-]{2,60}", font):
        raise ThemeError("'font' must be the name of a Google Slides font, such as Arial or Roboto.")
    out['font'] = font
    title = raw['title']
    align = title.get('align')
    if align not in ('START', 'CENTER', 'END'):
        raise ThemeError("'title.align' must be START (left), CENTER or END (right).")
    if not isinstance(title.get('bold'), bool):
        raise ThemeError("'title.bold' must be true or false.")
    out['title'] = {'size': _positive_number(title.get('size'), 'title.size', 12, 40),
                    'color': ref(_hex(title.get('color'), 'title.color')), 'align': align, 'bold': title['bold']}
    if raw.get('card_corners') not in ('round', 'square'):
        raise ThemeError("'card_corners' must be 'round' or 'square'.")
    out['card_corners'] = raw['card_corners']
    table = raw['table']
    out['table'] = {'header_fill': ref(_hex(table.get('header_fill'), 'table.header_fill')),
                    'body_fill': None if table.get('body_fill') in (None, '') else ref(_hex(table['body_fill'], 'table.body_fill'))}
    if footer is not None:
        raw['footer'] = {'text': footer}
    foot = raw.get('footer')
    if foot in (None, {}) or (isinstance(foot, dict) and not foot.get('text')):
        out['footer'] = None
    else:
        if isinstance(foot, str):
            foot = {'text': foot}
        _check_keys(foot, NESTED['footer'], 'footer')
        text = foot.get('text')
        if not isinstance(text, str) or len(text) > 120 or '\n' in text:
            raise ThemeError("'footer.text' must be a single line of up to 120 characters.")
        out['footer'] = {'text': text, 'size': _positive_number(foot.get('size', 8), 'footer.size', 6, 14),
                         'color': ref(_hex(foot.get('color', '@muted'), 'footer.color'))}
    cbf = raw.get('color_by_function') or {}
    enabled = bool(cbf.get('enabled'))
    if color_by_function is not None:
        enabled = color_by_function
    palette = cbf.get('palette')
    if palette is not None:
        if not isinstance(palette, list) or not 2 <= len(palette) <= 12:
            raise ThemeError("'color_by_function.palette' needs between 2 and 12 colour pairs, each with a fill and an outline.")
        palette = [_check_pair(item, i) for i, item in enumerate(palette)]
    elif enabled:
        if _luminance(out['background'] or out['colors']['surface']) < 0.25:
            raise ThemeError("Colour-by-function on a dark theme needs its own palette. Add color_by_function.palette "
                             "with dark fills and light outlines, or pick a light theme.")
        palette = copy.deepcopy(DEFAULT_FUNCTION_PALETTE)
    out['color_by_function'] = {'enabled': enabled, 'palette': palette}
    return out

def _check_pair(item, index):
    where = f'color_by_function.palette[{index}]'
    _check_keys(item, ('fill', 'outline'), where)
    return {'fill': _hex(item.get('fill'), where + '.fill'), 'outline': _hex(item.get('outline'), where + '.outline')}

def load_theme_file(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except OSError as exc:
        raise ThemeError(f"Could not read the theme file '{path}': {exc.strerror or exc}.") from exc
    except ValueError as exc:
        raise ThemeError(f"The theme file '{path}' is not valid JSON ({exc}). Check commas, quotes and brackets.") from exc
    return data

def _channel(v):
    v /= 255
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

def _luminance(value):
    r, g, b = (_channel(int(value[i:i + 2], 16)) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast(a, b):
    """WCAG contrast ratio between two hex colours."""
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)

def theme_warnings(theme):
    """Plain-language accessibility warnings for a resolved theme (never errors)."""
    notes = []
    c = theme['colors']; ground = theme['background'] or 'FFFFFF'
    def text(label, fg, bg, need=4.5):
        ratio = contrast(fg, bg)
        if ratio < need:
            notes.append(f"{label} is hard to read: contrast {ratio:.1f}:1 (aim for {need}:1 or more). Pick a darker or lighter colour.")
    fills = {f'the {n} card fill': s['fill'] for n, s in theme['statuses'].items()}
    cbf = theme['color_by_function']
    if cbf['palette'] and cbf['enabled']:
        fills.update({f'colour-by-function colour {i + 1}': p['fill'] for i, p in enumerate(cbf['palette'])})
    for label, fill in fills.items():
        text(f'Text on {label}', c['ink'], fill); text(f'Secondary text on {label}', c['muted'], fill)
    text('The title', theme['title']['color'], ground)
    text('Table text', c['ink'], theme['table']['body_fill'] or ground)
    text('Table heading text', c['ink'], theme['table']['header_fill'])
    text('Function heading text', c['ink'], c['surface'])
    text('The relationship legend text', c['matrix_line'], ground)
    if theme['footer']:
        text('The footer', theme['footer']['color'], ground)
    for name in ('open', 'planned', 'resigned', 'contingent'):
        ratio = contrast(theme['statuses'][name]['outline'], ground)
        if ratio < 3:
            notes.append(f"The {name} outline is faint against the page: contrast {ratio:.1f}:1 (aim for 3:1 or more).")
    if contrast(c['line'], ground) < 3:
        notes.append(f"Reporting lines are faint against the page: contrast {contrast(c['line'], ground):.1f}:1 (aim for 3:1 or more).")
    if cbf['palette'] and cbf['enabled']:
        for i, p in enumerate(cbf['palette']):
            if contrast(p['outline'], p['fill']) < 3:
                notes.append(f"Colour-by-function colour {i + 1}: the outline is faint against its fill.")
    seen = {}
    for name in PATTERN_STATUSES:
        seen.setdefault(theme['statuses'][name]['dash'], []).append(name)
    for dash, names in seen.items():
        if len(names) > 1:
            notes.append(f"{' and '.join(names)} cards share the {dash} line pattern, so they would differ by colour alone. "
                         "Give each a different pattern so the meaning survives black-and-white printing and colour blindness.")
    return notes

def preview_text(theme):
    """Palette summary of a resolved theme as plain text."""
    c = theme['colors']
    lines = [f"{theme['id']}: {theme['description']}",
             f"  page background  #{theme['background'] or 'FFFFFF'}" + ('' if theme['background'] else ' (from the template layout)'),
             f"  text             main #{c['ink']}   secondary #{c['muted']}   title #{theme['title']['color']}",
             f"  lines            reporting #{c['line']}   dotted relationship #{c['matrix_line']}   accent #{theme['accent']}",
             f"  font             {theme['font']}, title {theme['title']['size']} pt, corners {theme['card_corners']}"]
    for name in STATUSES:
        s = theme['statuses'][name]
        lines.append(f"  {name:<16} fill #{s['fill']}   outline #{s['outline']}   {s['dash'].lower().replace('_', ' ')}")
    cbf = theme['color_by_function']
    if cbf['palette']:
        lines.append(f"  by function      {'ON' if cbf['enabled'] else 'off (use --color-by-function)'}: " +
                     ', '.join(f"#{p['fill']}/#{p['outline']}" for p in cbf['palette']))
    if theme['footer']:
        lines.append(f"  footer           {theme['footer']['text']}")
    return '\n'.join(lines)

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
