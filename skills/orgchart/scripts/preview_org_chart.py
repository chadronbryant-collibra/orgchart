#!/usr/bin/env python3
"""Print a bounded, human-readable outline and page plan."""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
import org_chart_geometry as geometry

NAMES = {'compact_hierarchy':'Simple tree','leadership_bands':'Leadership team','functional_columns':'Departments and teams','matrix_relationships':'Matrix','enterprise_overview':'Overview + team pages'}

def outline(data, mode=None):
    recommendation = geometry.recommend(data)
    plan = geometry.layout(data, mode)
    children = defaultdict(list)
    for person in data['people']: children[person.get('manager_id')].append(person)
    def size(node): return 1 + sum(size(p['id']) for p in children[node])
    lines = ['Outline:']
    def visit(person, depth):
        if len(lines) >= 48: return
        descendants = size(person['id']) - 1
        label = f"{person['name']} | {person['title']} [{person.get('status', 'filled')}]"
        if depth >= 3 and descendants:
            lines.append('  ' * depth + label + f' (+{descendants} below)'); return
        lines.append('  ' * depth + label)
        for child in children[person['id']]: visit(child, depth + 1)
    for root in children[None]: visit(root, 0)
    shown = sum(1 for line in lines[1:] if line.strip())
    if len(lines) >= 48: lines.append(f'  ... additional branches omitted ({len(data["people"])} positions total)')
    counts = Counter(p.get('status','filled') for p in data['people'])
    lines.append('Totals: ' + ', '.join(f'{s} {counts[s]}' for s in ('filled','open','planned','resigned','other')))
    lines.append(f"Recommended: {NAMES[recommendation['recommended_mode']]} | {recommendation['rationale']}")
    lines.append(f"Page plan: {len(plan['pages'])} page(s), {NAMES[plan['mode']]}")
    for page in plan['pages'][:5]: lines.append(f"  {page['id']}: {page.get('title', 'Chart')}")
    if len(plan['pages']) > 5: lines.append(f"  ... {len(plan['pages']) - 5} more page(s)")
    return '\n'.join(lines)

def _headcount(people):
    return sum(int(p.get('headcount_impact', {'filled': 1, 'resigned': -1}.get(p.get('status', 'filled'), 0))) for p in people)

def _lines(data):
    children = defaultdict(list)
    for p in data['people']: children[p.get('manager_id')].append(p)
    out = []
    def visit(p, depth):
        mark = ''
        if p.get('status', 'filled') != 'filled': mark = f" [{p.get('status')}]"
        out.append((p['id'], '  ' * depth + f"{p['name']} | {p['title']}{mark}"))
        for c in children[p['id']]: visit(c, depth + 1)
    ids = {p['id'] for p in data['people']}
    for p in data['people']:
        if not p.get('manager_id') or p['manager_id'] not in ids: visit(p, 0)
    return out

def diff(current, planned):
    """Side-by-side outlines of current vs planned, with plain-words changes and headcount."""
    cur = {p['id']: p for p in current['people']}
    pln = {p['id']: p for p in planned['people']}
    cl, pl = _lines(current), _lines(planned)
    width = min(max([len(t) for _, t in cl] + [7]), 52)
    rows = max(len(cl), len(pl))
    out = [f"{'CURRENT':<{width}}   PLANNED", f"{'-' * width}   {'-' * width}"]
    for i in range(rows):
        left = cl[i] if i < len(cl) else ('', '')
        right = pl[i] if i < len(pl) else ('', '')
        flag = ''
        if right[0] and right[0] not in cur: flag = '  + new'
        elif left[0] and left[0] not in pln: flag = ''
        elif right[0] and (cur[right[0]].get('manager_id') != pln[right[0]].get('manager_id')): flag = '  > moved'
        elif right[0] and any(cur[right[0]].get(k) != pln[right[0]].get(k) for k in ('name', 'title', 'status', 'function')): flag = '  ~ changed'
        out.append(f"{left[1][:width]:<{width}}   {right[1]}{flag}")
    added = [pln[i] for i in pln if i not in cur]
    removed = [cur[i] for i in cur if i not in pln]
    moved = [pln[i] for i in pln if i in cur and cur[i].get('manager_id') != pln[i].get('manager_id')]
    changed = [pln[i] for i in pln if i in cur and i not in {m['id'] for m in moved}
               and any(cur[i].get(k) != pln[i].get(k) for k in ('name', 'title', 'status', 'function'))]
    h0, h1 = _headcount(current['people']), _headcount(planned['people'])
    summary = []
    if added: summary.append(f"{len(added)} added")
    if changed: summary.append(f"{len(changed)} changed")
    if moved: summary.append(f"{len(moved)} moved")
    if removed: summary.append(f"{len(removed)} removed")
    out.append('')
    out.append(', '.join(summary) or 'No differences')
    out[-1] += f"; headcount {h0} -> {h1} ({h1 - h0:+d})"
    for label, group in (('Added', added), ('Removed', removed), ('Moved', moved), ('Changed', changed)):
        for p in group: out.append(f"  {label}: {p['name']} | {p['title']} [{p.get('status', 'filled')}, impact {int(p.get('headcount_impact', 0)):+d}]")
    rel = lambda d: len(d.get('relationships') or []) + len(d.get('companion_links') or [])
    if rel(current) != rel(planned): out.append(f"Dotted lines: {rel(current)} -> {rel(planned)}")
    return '\n'.join(out)

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('command', choices=['outline', 'diff']); parser.add_argument('input', help='Roster JSON (for diff: the current roster)'); parser.add_argument('planned', nargs='?', help='Planned JSON (diff only)'); parser.add_argument('--mode', choices=geometry.MODES); args=parser.parse_args()
    try:
        if args.command == 'diff':
            if not args.planned: print('Preview: diff needs two files: the current roster and the planned view.', file=sys.stderr); return 2
            print(diff(json.loads(Path(args.input).read_text()), json.loads(Path(args.planned).read_text()))); return 0
        print(outline(json.loads(Path(args.input).read_text()), args.mode)); return 0
    except FileNotFoundError as exc: print(f'Preview: I could not find the file {exc.filename}.', file=sys.stderr); return 2
    except (ValueError, OSError, KeyError, TypeError) as exc: print(f'Preview: {exc}', file=sys.stderr); return 2
if __name__ == '__main__': sys.exit(main())
