"""Synthetic scale, navigation and partition contracts (no source-system data)."""
import ast
import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/orgchart/scripts'
sys.path.insert(0, str(SCRIPTS))
import org_chart_geometry as geometry
import slides_requests


def roster(count):
    people = []

    def add(manager, function, title='Role'):
        i = len(people)
        people.append({'id': f'p{i}', 'name': f'Person Delta {i}', 'title': title,
                       'manager_id': manager, 'function': function,
                       'kind': 'open_role' if i and i % 67 == 0 else 'person',
                       'worker_type': 'contingent' if i and i % 41 == 0 else 'employee'})
        return people[-1]['id']

    root = add(None, 'Leadership')
    sizes = [max(155, (count - 1) // 4)]
    remaining = count - 1 - sizes[0]
    sizes += [remaining // 7 + (i < remaining % 7) for i in range(7)]
    for index, size in enumerate(sizes):
        function = f'Function {index}'
        head = add(root, function, 'Director')
        remaining = size - 1
        while remaining:
            manager = add(head, function, 'Manager')
            remaining -= 1
            # Uneven third/fourth levels, retaining each function's subtree.
            for _ in range(min(2 + len(people) % 2, remaining)):
                if not remaining:
                    break
                lead = add(manager, function, 'Team lead')
                remaining -= 1
                for _ in range(min(2 + len(people) % 2, remaining)):
                    if not remaining:
                        break
                    child = add(lead, function)
                    remaining -= 1
                    if remaining:
                        add(child, function)
                        remaining -= 1
    assert len(people) == count
    return {'title': 'Synthetic large organization', 'people': people}


def owned(result):
    return [(page, card) for page in result['pages'] for card in page['elements']
            if card.get('node_id') and not card['data'].get('context')]


class LargeOrgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = {n: geometry.layout(roster(n)) for n in (300, 800)}

    def test_scale_geometry_and_coverage(self):
        for n, result in self.results.items():
            with self.subTest(people=n):
                self.assertTrue(geometry.validate_layout(result)['valid'])
                self.assertLessEqual(result['page_count'], geometry.MAX_PAGES)
                # Verified deterministic counts: 300 people = 30 pages;
                # 800 people = 82 pages, below the 120-page ceiling.
                if n == 800:
                    self.assertLess(result['page_count'], 120)
                self.assertEqual(Counter(c['node_id'] for _, c in owned(result)),
                                 Counter(p['id'] for p in roster(n)['people']))
                for page in result['pages']:
                    cards = [c for c in page['elements'] if c.get('collision_class') == 'card']
                    self.assertLessEqual(len(cards), 60)
                    for card in cards:
                        lines = slides_requests.card_text(card).splitlines()
                        self.assertLessEqual(len(lines), 5)
                        if card['type'] == 'group_summary_card':
                            self.assertEqual(lines[0], card['data']['name'])
                            # Sub-leader cards name the leader already; function cards add a lead line.
                            self.assertEqual(len(lines), 3 if card['data'].get('lead') else 2)
                            if card['data'].get('lead'):
                                self.assertTrue(lines[2].startswith('Lead: '))
                            self.assertLessEqual(card['box']['h'], 1.06)

    def test_navigation_and_hints(self):
        for n, result in self.results.items():
            people = {p['id']: p for p in roster(n)['people']}
            locations = {c['node_id']: page['index'] for page, c in owned(result)}
            self.assertEqual(len(result['navigation']), result['page_count'])
            run = 0
            previous_section = None
            for page, nav in zip(result['pages'], result['navigation']):
                self.assertIn(nav['level'], (0, 1, 2))
                self.assertEqual(nav['page'], page['index'])
                if nav['parent_page'] is not None:
                    self.assertLess(nav['parent_page'], nav['page'])
                if page['section'].startswith('enterprise-') and page['section'] != 'enterprise-overview':
                    # Every team page must be reachable from an overview page.
                    parent = result['pages'][nav['parent_page'] - 1]
                    self.assertTrue(parent['section'] == 'enterprise-overview' or
                                    parent['section'] == 'function-overview' or
                                    parent['section'].endswith('overview'))
                else:
                    run = 0
                previous_section = page['section']
                for card in page['elements']:
                    hint = card.get('data', {}).get('continuation_hint')
                    if hint:
                        target = int(hint.rsplit(' ', 1)[1])
                        self.assertTrue(any(p['manager_id'] == card['node_id'] and locations[p['id']] == target
                                            for p in people.values()))
                        self.assertNotEqual(target, page['index'])

    def test_caps_match_without_imports(self):
        values = []
        for filename in ('org_chart_geometry.py', 'normalize_org_chart.py'):
            tree = ast.parse((SCRIPTS / filename).read_text())
            values.append(next(ast.literal_eval(node.value) for node in tree.body
                               if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'MAX_PEOPLE'
                                                                       for t in node.targets)))
        self.assertEqual(values, [1000, 1000])
        self.assertEqual(geometry.MAX_PAGES, 120)
        recommendation = geometry.recommend(roster(300))
        self.assertEqual(recommendation['recommended_mode'], 'enterprise_overview')
        self.assertIn('scale', recommendation['facts'])
        self.assertIn('Scale:', recommendation['rationale'])

    def test_plan_and_cli_outputs(self):
        data = roster(1200)
        with self.assertRaisesRegex(geometry.GeometryError, 'plan'):
            geometry.layout(data)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.json'
            source.write_text(json.dumps(data))
            completed = subprocess.run([sys.executable, str(SCRIPTS / 'org_chart_geometry.py'), 'plan', str(source),
                                        '--output-dir', str(Path(directory) / 'parts')],
                                       check=True, text=True, capture_output=True)
            planned = json.loads(completed.stdout)
            self.assertFalse(planned['fits_one_deck'])
            seen = Counter()
            for part in planned['parts']:
                candidate = json.loads(Path(part['file']).read_text())
                result = geometry.layout(candidate)
                self.assertTrue(result['validation']['valid'])
                self.assertEqual(result['page_count'], part['pages'])
                self.assertLessEqual(part['people'], geometry.MAX_PEOPLE)
                self.assertLessEqual(part['pages'], geometry.MAX_PAGES)
                for person in candidate['people']:
                    if person.get('duplicated_root'):
                        self.assertIsNone(person['manager_id'])
                        self.assertFalse(person.get('context'))
                    else:
                        seen[person['id']] += 1
            self.assertEqual(seen, Counter(p['id'] for p in data['people']))
            self.assertTrue(planned['overview_part']['top_nodes'])
        self.assertTrue(geometry.plan(roster(300))['fits_one_deck'])
        self.assertEqual(geometry.estimate_pages(roster(300)), self.results[300]['page_count'])

    def test_lead_variants(self):
        def person(node, manager, function, **extra):
            return {'id': node, 'manager_id': manager, 'function': function,
                    'name': 'Person Delta ' + node, 'title': 'Role', **extra}
        for multiple_roots in (False, True):
            data = {'people': [person('0', None, 'Leadership'), person('1', '0', 'Single'),
                               person('2', '0', 'Multiple'), person('3', '0', 'Multiple'),
                               person('4', '0', 'Open', kind='open_role')]}
            if multiple_roots:
                data['people'].append(person('5', None, 'Other'))
            result = geometry.layout(data, 'enterprise_overview')
            summaries = {c['data']['name']: c for c in result['pages'][0]['elements']
                         if c['type'] == 'group_summary_card'}
            self.assertEqual(summaries['Single']['data']['lead'], 'Person Delta 1')
            self.assertEqual(summaries['Multiple']['data']['lead'], 'Person Delta 2 +1 more')
            self.assertEqual(summaries['Open']['data']['lead'], 'Open role')
            self.assertEqual(slides_requests.card_text(summaries['Single']).splitlines(),
                             ['Single', '1 position · 0 open', 'Lead: Person Delta 1'])

    def test_recursive_oversized_subtree_plan(self):
        data = roster(1200)
        # Put all function heads under one leader, forcing a nested split.
        head = data['people'][1]['id']
        for person in data['people'][2:]:
            if person['manager_id'] == 'p0':
                person['manager_id'] = head
        planned = geometry.plan(data)
        self.assertTrue(planned['notes'])
        self.assertEqual(Counter(n for p in planned['parts'] for n in p['person_ids']),
                         Counter(p['id'] for p in data['people']))

    def test_nested_function_overviews(self):
        data = roster(300)
        head = data['people'][1]['id']
        reports = [p for p in data['people'] if p['manager_id'] == head]
        first = reports[0]['id']
        for report in reports[1:]:
            report['manager_id'] = first
        result = geometry.layout(data)
        nested = [p for p in result['pages'] if p['section'] == 'function-overview'
                  and 'Person Delta' in p['title']]
        self.assertTrue(nested)
        self.assertTrue(result['validation']['valid'])
        self.assertEqual(Counter(c['node_id'] for _, c in owned(result)),
                         Counter(p['id'] for p in data['people']))
        for page in nested:
            self.assertEqual(page['navigation_level'], 2)
            self.assertTrue(any(e['type'] == 'group_summary_card' for e in page['elements']))

    def test_deep60_regression(self):
        from test_team_pages import deep60
        result = geometry.layout(deep60(), 'enterprise_overview')
        self.assertTrue(result['validation']['valid'])
        self.assertEqual(Counter(c['node_id'] for _, c in owned(result)),
                         Counter(p['id'] for p in deep60()['people']))


if __name__ == '__main__':
    unittest.main()
