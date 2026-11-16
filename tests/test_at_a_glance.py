"""Optional at-a-glance summary page (synthetic data only)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/orgchart/scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / 'tests'))
import normalize_org_chart as normalizer
import org_chart_geometry as geometry
import slides_requests as slides
from test_compile_verify import connector_readback


def rows():
    out = [{'node_id': 'ceo', 'display_name': 'Person Alpha', 'title': 'Chief Executive', 'manager_node_id': '', 'function': 'Leadership', 'source_as_of': '2099-06-01'}]
    spec = [('Engineering', 'filled', 4), ('Engineering', 'open', 2), ('Sales', 'filled', 3),
            ('Sales', 'planned', 1), ('Support', 'resigned', 1), ('Support', 'filled', 1)]
    n = 0
    for function, status, count in spec:
        for _ in range(count):
            n += 1
            out.append({'node_id': f'p{n}', 'display_name': f'Person Beta {n}', 'title': 'Role', 'manager_node_id': 'ceo',
                        'function': function, 'status': status})
    out[2]['worker_type'] = 'contingent'
    out.append({'node_id': 'o1', 'display_name': 'Person Gamma', 'title': 'Role', 'manager_node_id': 'ceo', 'function': 'Support',
                'status': 'other', 'statusLabel': 'Leave'})
    out[1]['dotted_to_node_ids'] = 'p7'
    return out


def build():
    payload, receipt = normalizer.normalize_source(rows(), source_kind='flat_json')
    return payload, receipt


class AtAGlanceTests(unittest.TestCase):
    def setUp(self):
        self.payload, self.receipt = build()

    def test_off_by_default_is_unchanged(self):
        plain = geometry.layout(self.payload)
        again = geometry.layout(self.payload, at_a_glance=False)
        self.assertEqual(plain, again)
        self.assertFalse(any(p['section'] == 'at-a-glance' for p in plain['pages']))

    def test_prepends_one_page_and_validates(self):
        plain = geometry.layout(self.payload)
        glance = geometry.layout(self.payload, at_a_glance=True)
        self.assertEqual(glance['page_count'], plain['page_count'] + 1)
        self.assertEqual(glance['pages'][0]['section'], 'at-a-glance')
        self.assertEqual([p['index'] for p in glance['pages']], list(range(1, glance['page_count'] + 1)))
        self.assertTrue(geometry.validate_layout(glance)['valid'])
        # Original pages keep their object IDs.
        self.assertEqual([p['id'] for p in plain['pages']], [p['id'] for p in glance['pages'][1:]])

    def test_counts_match_normalizer(self):
        page = geometry.layout(self.payload, at_a_glance=True)['pages'][0]
        recon = self.receipt['reconciliation']
        totals = page['glance']
        self.assertEqual(totals['positions'], recon['chart_nodes'])
        self.assertEqual(sum(totals['by_status'].values()), recon['chart_nodes'])
        self.assertEqual(totals['dotted_links'], recon['non_direct_relationships'])
        self.assertEqual(totals['by_status'], {'filled': 9, 'open': 2, 'planned': 1, 'resigned': 1, 'other': 1})
        self.assertEqual(totals['contingent'], 1)
        by_name = {e['data']['title']: e['data']['name'] for e in page['elements']}
        self.assertEqual(by_name['Open roles'], '2')
        self.assertEqual(by_name['Contingent workers'], '1')
        self.assertEqual(by_name['Dotted-line links'], '1')
        function_cards = {e['data']['name']: e['data']['title'] for e in page['elements']
                          if e['stable_name'].startswith('org-summary-glance-function')}
        self.assertEqual(sum(int(t.split()[0]) for t in function_cards.values()), recon['chart_nodes'])

    def test_context_cards_excluded(self):
        data = json.loads(json.dumps(self.payload))
        data['people'].append({**data['people'][0], 'id': 'ctx', 'context': True})
        totals = geometry.glance_totals(data)
        self.assertEqual(totals['positions'], self.receipt['reconciliation']['chart_nodes'])

    def test_cards_follow_conventions(self):
        page = geometry.layout(self.payload, at_a_glance=True)['pages'][0]
        names = [e['stable_name'] for e in page['elements']]
        self.assertEqual(len(names), len(set(names)))
        for e in page['elements']:
            self.assertEqual(e['collision_class'], 'card')
            self.assertTrue(geometry.GOOGLE_OBJECT_ID.fullmatch(e['google_slides_object_id']))
        self.assertEqual(page['connectors'], [])
        self.assertIn('Dotted line', page['elements'][-1]['data']['name'])

    def test_many_functions_collapse(self):
        data = json.loads(json.dumps(self.payload))
        for i in range(20):
            data['people'].append({**data['people'][1], 'id': f'f{i}', 'function': f'Function {i:02}', 'manager_id': data['people'][0]['id']})
        page = geometry.layout(data, at_a_glance=True)['pages'][0]
        self.assertTrue(any('other functions' in e['data']['name'] for e in page['elements']))
        self.assertEqual(geometry.glance_totals(data)['positions'], len(data['people']))

    def test_option_in_input_enables_it(self):
        data = json.loads(json.dumps(self.payload))
        data['options'] = {'at_a_glance': True}
        self.assertEqual(geometry.layout(data)['pages'][0]['section'], 'at-a-glance')

    def test_text_uses_8pt_floor_and_compiles_and_verifies(self):
        result = geometry.layout(self.payload, at_a_glance=True)
        compiled = slides.compile_requests(result, 'collibra-2026')
        sizes = [r['updateTextStyle']['style']['fontSize']['magnitude'] for chunk in compiled['presentation_requests']
                 for r in chunk if 'updateTextStyle' in r and 'fontSize' in r['updateTextStyle']['style']]
        self.assertTrue(sizes and min(sizes) >= 8)
        checks = slides.verify(result, connector_readback(compiled))
        self.assertTrue(all(ok for _, _, ok in checks))

    def test_cli_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp) / 'in.json', Path(tmp) / 'out.json'
            src.write_text(json.dumps(self.payload))
            for flag, expected in (([], False), (['--at-a-glance'], True)):
                run = subprocess.run([sys.executable, str(SCRIPTS / 'org_chart_geometry.py'), 'layout', str(src),
                                      '--output', str(out), *flag], capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(json.loads(out.read_text())['pages'][0]['section'] == 'at-a-glance', expected)
            check = subprocess.run([sys.executable, str(SCRIPTS / 'org_chart_geometry.py'), 'validate', str(out)],
                                   capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stderr)


if __name__ == '__main__':
    unittest.main()
