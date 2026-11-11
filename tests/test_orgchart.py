import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/orgchart'
sys.path.insert(0, str(SKILL/'scripts'))
import normalize_org_chart as normalizer
import org_chart_geometry as geometry
import preview_org_chart as preview
import templates

def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/f'{name}.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

class OrgchartTests(unittest.TestCase):
    def rows(self, name='simple-team'):
        return json.loads((SKILL/'examples/starters'/f'{name}.json').read_text())
    def render(self, rows=None):
        return normalizer.normalize_source(rows or self.rows(), source_kind='flat_json')[0]
    def test_normalize_statuses(self):
        rows=self.rows()
        for row, status in zip(rows, ['filled','open','planned','resigned','other','filled']): row['status']=status
        rows[4]['statusLabel']='Temporary'
        people=self.render(rows)['people']; by_id={p['id']:p for p in people}
        self.assertEqual(by_id[rows[3]['node_id']]['headcount_impact'], -1)
        self.assertEqual(by_id[rows[4]['node_id']]['headcount_impact'], 0)
        self.assertEqual(by_id[rows[4]['node_id']]['statusLabel'], 'Temporary')
    def test_other_label_required(self):
        rows=self.rows(); rows[0]['status']='other'
        with self.assertRaisesRegex(normalizer.NormalizationError,'statusLabel'): self.render(rows)
    def test_bad_status(self):
        rows=self.rows(); rows[0]['status']='mystery'
        with self.assertRaisesRegex(normalizer.NormalizationError,'Unsupported status'): self.render(rows)
    def test_canonical_other(self):
        data={'people':[], 'positions':[{'positionId':'p','title':'Role','status':'other','statusLabel':'Leave'}], 'relationships':[]}
        result,_=normalizer.normalize_source(data,source_kind='canonical_json')
        self.assertEqual(result['people'][0]['statusLabel'],'Leave')
    def test_people_limit(self):
        rows=[{'node_id':str(i),'display_name':'Person Alpha','title':'Role','manager_node_id':'0' if i else ''} for i in range(201)]
        with self.assertRaisesRegex(normalizer.NormalizationError,'200'): self.render(rows)
    def test_matrix_limit(self):
        rows=self.rows(); rows[0]['dotted_to_node_ids']=';'.join([rows[1]['node_id']]*9)
        with self.assertRaisesRegex(normalizer.NormalizationError,'8 matrix'): self.render(rows)
    def test_geometry_all_starters_and_layouts(self):
        for starter in ('simple-team','functional-org','future-state-plan'):
            data=self.render(self.rows(starter))
            self.assertIn(geometry.recommend(data)['recommended_mode'], geometry.MODES)
            for mode in geometry.MODES:
                with self.subTest(starter=starter,mode=mode):
                    result=geometry.layout(data,mode)
                    self.assertTrue(geometry.validate_layout(result)['valid'])
    def test_compact_subtree_groups_and_overlap(self):
        deep = [{'node_id': str(i), 'display_name': 'Person Alpha', 'title': 'Role',
                 'manager_node_id': str(i-1) if i else ''} for i in range(8)]
        for label, rows in [(name, self.rows(name)) for name in ('simple-team', 'functional-org', 'future-state-plan')] + [('eight-row', deep)]:
            data = self.render(rows)
            parents = {p['id']: p['manager_id'] for p in data['people']}
            result = geometry.layout(data, 'compact_hierarchy')
            for page in result['pages']:
                cards = [e for e in page['elements'] if e.get('node_id')]
                by_id = {e['node_id']: e for e in cards}
                for i, card in enumerate(cards):
                    for other in cards[i+1:]:
                        self.assertFalse(geometry._intersects(card['box'], other['box']), (label, page['id']))
                groups = {}
                for card in cards:
                    parent = parents[card['node_id']]
                    if parent in by_id: groups.setdefault(parent, []).append(card)
                for parent, children in groups.items():
                    center = lambda e: e['box']['x'] + e['box']['w']/2
                    child_center = (min(map(center, children)) + max(map(center, children))) / 2
                    self.assertLessEqual(abs(child_center-center(by_id[parent])), by_id[parent]['box']['w']/2 + 0.001, (label, page['id'], parent))
                    for child in children:
                        for other in groups:
                            if other != parent and abs(by_id[other]['box']['y']-by_id[parent]['box']['y']) < 0.001:
                                self.assertLessEqual(abs(center(child)-center(by_id[parent])), abs(center(child)-center(by_id[other])) + 0.001, (label, child['node_id']))
    def test_geometry_limits(self):
        data=self.render(); data['people'] *= 34
        with self.assertRaisesRegex(geometry.GeometryError,'200'): geometry.recommend(data)
        data=self.render(); data['relationships']=[{}]*9
        with self.assertRaisesRegex(geometry.GeometryError,'8 matrix'): geometry.layout(data)
        self.assertFalse(geometry.validate_layout({'pages':[{'id':str(i),'elements':[]} for i in range(31)]})['valid'])
    def test_preview(self):
        output=preview.outline(self.render())
        self.assertIn('Person Alpha', output); self.assertIn('Totals:',output); self.assertIn('Recommended:',output); self.assertIn('Page plan:',output)
    def test_preview_bounded(self):
        rows=[{'node_id':str(i),'display_name':'Person Alpha','title':'Role','manager_node_id':str(i-1) if i else ''} for i in range(200)]
        self.assertLess(len(preview.outline(self.render(rows), 'enterprise_overview').splitlines()), 60)
    def test_manifest(self):
        data=json.loads((SKILL/'templates/manifest.json').read_text()); self.assertEqual(templates.validate(data),[])
        data['templates'].append(copy.deepcopy(data['templates'][0])); self.assertTrue(templates.validate(data))
    def test_zip(self):
        builder=load_script('build_desktop_zip')
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            import shutil
            root=Path(directory); shutil.copytree(SKILL,root/'skills/orgchart')
            with ZipFile(builder.build(root)) as archive:
                entries=archive.namelist(); self.assertIn('orgchart/SKILL.md',entries); self.assertTrue(all(x.startswith('orgchart/') for x in entries)); self.assertFalse(any('__pycache__' in x for x in entries))
    def test_public_check(self):
        checker=load_script('check_public'); self.assertEqual(checker.check(),[])
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root=Path(directory); (root/'bad.txt').write_text('contact ' + 'sample' + '@' + 'example.org')
            self.assertTrue(checker.check(root))
    def test_cli_manifest(self):
        result=subprocess.run([sys.executable,str(SKILL/'scripts/templates.py'),'validate'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__': unittest.main()
