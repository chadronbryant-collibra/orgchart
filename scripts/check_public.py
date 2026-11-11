#!/usr/bin/env python3
"""Check public source for common private identifiers and non-synthetic roster names.

Name detection covers structured roster fields and Person-style examples. It is
not a general-purpose detector of every possible real name; review prose too.
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git','dist','orgchart-work','__pycache__'}
PATTERNS = {
    'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
    'local home path': re.compile('/' + r'Users/'),
    'internal domain': re.compile(r'(?:atlassian' + r'\.net|slack' + r'\.com)', re.I),
    'secret reference': re.compile('op:' + r'//'),
    'token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[A-Z0-9]{16})\b'),
}
ALLOWED = {'Person Alpha','Person Beta','Person Gamma','Person Delta','Person Epsilon','Person Zeta','Person Eta','Open','Planned','Unknown','Chadron Bryant'}
NAME_FIELDS = {'display_name','displayName','preferredName'}

def names(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in NAME_FIELDS and isinstance(item, str) and item and item not in ALLOWED: yield item
            else: yield from names(item)
    elif isinstance(value, list):
        for item in value: yield from names(item)

def check(root=ROOT):
    findings=[]
    for path in sorted(root.rglob('*')):
        if not path.is_file() or any(x in EXCLUDED for x in path.relative_to(root).parts) or path.suffix in {'.pyc','.zip'}: continue
        try: content=path.read_text(encoding='utf-8')
        except (UnicodeError, OSError): continue
        rel=path.relative_to(root)
        for label, pattern in PATTERNS.items():
            if pattern.search(content): findings.append(f'{rel}: {label}')
        for match in re.findall(r'\bPerson [A-Z][a-z]+\b', content):
            if match not in ALLOWED: findings.append(f'{rel}: name outside synthetic allowlist')
        try:
            data=json.loads(content) if path.suffix == '.json' else list(csv.DictReader(content.splitlines())) if path.suffix == '.csv' else None
            if data is not None and any(names(data)): findings.append(f'{rel}: roster name outside synthetic allowlist')
        except (ValueError, csv.Error): pass
    return findings
if __name__ == '__main__':
    findings=check()
    if findings: print('\n'.join(findings)); sys.exit(1)
    print('Public content checks passed.')
