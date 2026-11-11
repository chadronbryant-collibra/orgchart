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

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('command', choices=['outline']); parser.add_argument('input'); parser.add_argument('--mode', choices=geometry.MODES); args=parser.parse_args()
    try: print(outline(json.loads(Path(args.input).read_text()), args.mode)); return 0
    except (ValueError, OSError, KeyError, TypeError) as exc: print(f'Preview: {exc}', file=sys.stderr); return 2
if __name__ == '__main__': sys.exit(main())
