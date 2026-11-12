"""Synthetic regressions for live-test gaps in normalization and rendering."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/orgchart/scripts'
sys.path.insert(0, str(SCRIPTS))
import normalize_org_chart as normalizer
import org_chart_geometry as geometry
import slides_requests as slides


def row(name='Person Delta 12', **fields):
    return dict(node_id='delta-12', display_name=name, title='Team lead', **fields)


def canonical(name, **fields):
    return {
        'organization': {'name': 'Synthetic team'},
        'people': [{'personId': 'person-12', 'displayName': name}],
        'positions': [dict(positionId='position-12', personId='person-12',
                           title='Team lead', **fields)],
        'relationships': [],
    }


def requests(geo):
    return [r for chunk in slides.compile_requests(geo, 'neutral')['presentation_requests']
            for r in chunk]


class DescriptorTests(unittest.TestCase):
    def test_whitelist_in_both_models(self):
        expected = {
            'on leave': ('filled', 'unknown'),
            'leave of absence': ('filled', 'unknown'),
            'contingent worker': ('filled', 'contingent'),
            'contingent': ('filled', 'contingent'),
            'contractor': ('filled', 'contingent'),
            'terminated': ('resigned', 'unknown'),
            'inactive': ('resigned', 'unknown'),
            'pending start': ('filled', 'unknown'),
            'retired': ('resigned', 'unknown'),
        }
        for term, (status, worker_type) in expected.items():
            for kind in ('flat_json', 'canonical_json'):
                with self.subTest(term=term, kind=kind):
                    name = 'Person Delta 12 (' + term.upper() + ')'
                    source = [row(name)] if kind == 'flat_json' else canonical(name)
                    before = copy.deepcopy(source)
                    payload, receipt = normalizer.normalize_source(source, source_kind=kind)
                    person = payload['people'][0]
                    self.assertEqual((person['name'], person['status'], person['worker_type']),
                                     ('Person Delta 12', status, worker_type))
                    self.assertEqual(receipt['mapping']['descriptors_stripped'], 1)
                    self.assertEqual(receipt['mapping']['descriptor_leave_dropped'],
                                     int(term in ('on leave', 'leave of absence')))
                    self.assertNotIn('Person Delta', json.dumps(receipt))
                    self.assertEqual(source, before)

    def test_repeated_suffixes_and_nicknames(self):
        clean, terms = normalizer._split_descriptors(
            'Person Delta 12 (Bob) (Contingent Worker) (On Leave)')
        self.assertEqual(clean, 'Person Delta 12 (Bob)')
        self.assertEqual(terms, ['contingent worker', 'on leave'])
        self.assertEqual(normalizer._split_descriptors('Person Delta 12 (Bob)'),
                         ('Person Delta 12 (Bob)', []))
        self.assertEqual(normalizer._split_descriptors('Person Delta 12 (On Leave) (Bob)'),
                         ('Person Delta 12 (On Leave) (Bob)', []))
        payload, receipt = normalizer.normalize_source(
            [row('Person Delta 12 (Contractor) (On Leave) (Leave of Absence)')],
            source_kind='flat_json')
        self.assertEqual(payload['people'][0]['worker_type'], 'contingent')
        self.assertEqual(receipt['mapping']['descriptors_stripped'], 3)
        self.assertEqual(receipt['mapping']['descriptor_leave_dropped'], 2)

    def test_leave_allowlist_and_explicit_fields(self):
        for kind in ('flat_json', 'canonical_json'):
            for allowed in ([], ['leave']):
                with self.subTest(kind=kind, allowed=allowed):
                    name = 'Person Delta 12 (Retired) (Contractor) (On Leave)'
                    source = ([row(name, status='planned', worker_type='employee',
                                   location='Site Delta', metadata='Unit Delta')]
                              if kind == 'flat_json' else canonical(
                                  name, status='planned', workerType='employee',
                                  location='Site Delta', level='Level Delta'))
                    payload, receipt = normalizer.normalize_source(
                        source, source_kind=kind, allow_sensitive=allowed)
                    person = payload['people'][0]
                    self.assertEqual(person['status'], 'planned')
                    self.assertEqual(person['worker_type'], 'employee')
                    self.assertEqual(person['name'], 'Person Delta 12')
                    self.assertEqual('On leave' in person['details'], bool(allowed))
                    self.assertEqual(person['details'][0], 'Site Delta')
                    self.assertEqual(receipt['mapping']['descriptor_leave_dropped'],
                                     0 if allowed else 1)
                    self.assertNotIn('Person Delta', json.dumps(receipt))

    def test_sensitive_leave_column_still_requires_allowlist(self):
        with self.assertRaises(normalizer.NormalizationError):
            normalizer.normalize_source([row(leave='')], source_kind='flat_json')

    def test_preferred_name_is_cleaned(self):
        source = canonical('Person Delta 12')
        source['people'][0]['preferredName'] = 'Person Delta 13 (Inactive)'
        payload, _ = normalizer.normalize_source(source, source_kind='canonical_json')
        self.assertEqual(payload['people'][0]['name'], 'Person Delta 13')
        self.assertEqual(payload['people'][0]['status'], 'resigned')


class TitleTests(unittest.TestCase):
    def test_derived_possessive_and_multiple_roots(self):
        for kind in ('flat_json', 'csv'):
            for name, title in (("Person Delta 12", "Person Delta 12's organization"),
                                ("Person Delta 12s", "Person Delta 12s' organization")):
                payload, _ = normalizer.normalize_source(
                    [row(name + ' (Pending Start)')], source_kind=kind)
                self.assertEqual(payload['title'], title)
        payload, _ = normalizer.normalize_source(
            [row(), dict(row('Person Delta 13'), node_id='delta-13')],
            source_kind='flat_json', allow_disconnected=True)
        self.assertEqual(payload['title'], 'Organization chart')

    def test_canonical_and_override(self):
        source = canonical('Person Delta 12')
        self.assertEqual(normalizer.normalize_source(source, source_kind='canonical_json')[0]['title'],
                         'Synthetic team')
        for kind, source in (('flat_json', [row()]), ('canonical_json', source)):
            payload, _ = normalizer.normalize_source(source, source_kind=kind, title='Custom team')
            self.assertEqual(payload['title'], 'Custom team')
            for mode in geometry.MODES:
                geo = geometry.layout(payload, mode)
                self.assertEqual(geo['pages'][0]['title'], 'Custom team')

    def test_cli_title_and_leave_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / 'source.csv'
            source.write_text('node_id,display_name,title\ndelta-12,Person Delta 12 (On Leave),Team lead\n')
            for allowed in (False, True):
                output = folder / ('allowed.json' if allowed else 'dropped.json')
                receipt = folder / ('allowed-receipt.json' if allowed else 'dropped-receipt.json')
                command = [sys.executable, str(SCRIPTS / 'normalize_org_chart.py'),
                           'normalize', str(source), '--title', 'Custom team',
                           '--output', str(output), '--receipt', str(receipt)]
                if allowed:
                    command += ['--allow-sensitive', 'leave']
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(output.read_text())
                self.assertEqual(payload['title'], 'Custom team')
                self.assertEqual(payload['people'][0]['details'], ['On leave'] if allowed else [])
                self.assertNotIn('Person Delta', receipt.read_text())


class RenderingTests(unittest.TestCase):
    def test_details_and_validation_passthrough(self):
        payload, _ = normalizer.normalize_source(
            [row(location='Site Delta', metadata=['Unit Delta', 'Level Delta', 'Region Delta'],
                 worker_type='contingent', markers=['Marker Delta'])], source_kind='flat_json')
        by_id = geometry._validate_input(payload)
        for field in ('details', 'markers', 'worker_type', 'kind'):
            self.assertEqual(by_id['delta-12'][field], payload['people'][0][field])
        by_id['delta-12']['details'].append('Extra Delta')
        self.assertNotIn('Extra Delta', payload['people'][0]['details'])
        geo = geometry.layout(payload, 'compact_hierarchy')
        card = slides.cards(geo['pages'][0])[0]
        self.assertEqual(card['data']['worker_type'], 'contingent')
        expected = ('Person Delta 12\nTeam lead\nSite Delta\n'
                    'Unit Delta · Level Delta · Region Delta\nContingent')
        self.assertEqual(slides.card_text(card), expected)
        self.assertTrue(any(r.get('insertText', {}).get('text') == expected for r in requests(geo)))
        self.assertEqual(slides.card_text({'data': {'name': 'Person Delta 12', 'title': 'Role'}}),
                         'Person Delta 12\nRole')

    def test_contingent_open_role_and_kind_marker(self):
        payload, _ = normalizer.normalize_source(
            [row(status='open', worker_type='contingent')], source_kind='flat_json')
        geo = geometry.layout(payload, 'compact_hierarchy')
        card = slides.cards(geo['pages'][0])[0]
        self.assertEqual(slides.card_text(card), 'Open role\nTeam lead\nContingent')
        req = requests(geo)
        for label in ('Open', 'Contingent'):
            self.assertTrue(any(r.get('insertText', {}).get('text') == label for r in req))
        self.assertIn('Contingent', slides.card_text({'data': {'kind': 'contractor'}}))
        legend = slides.ident(geo['pages'][0]['id'] + '-legend-contingent')
        style = next(r['updateShapeProperties']['shapeProperties'] for r in req
                     if r.get('updateShapeProperties', {}).get('objectId') == legend)
        self.assertEqual(style['outline']['dashStyle'], 'LONG_DASH_DOT')
        self.assertEqual(style['shapeBackgroundFill']['solidFill']['color'], slides.color('E0E0E0'))
        card_style = next(r['updateShapeProperties']['shapeProperties'] for r in req
                          if r.get('updateShapeProperties', {}).get('objectId') == slides.card_id(card))
        self.assertEqual(card_style['outline']['dashStyle'], 'DASH')

    def test_full_legend_does_not_overlap_matrix(self):
        people = []
        for i, status in enumerate(('filled', 'open', 'planned', 'resigned', 'other', 'filled')):
            person = dict(row('Person Delta ' + str(i), status=status), node_id='delta-' + str(i))
            if i:
                person['manager_node_id'] = 'delta-0'
            if status == 'other':
                person['statusLabel'] = 'Custom status'
            if not i:
                person['worker_type'] = 'contingent'
                person['dotted_to_node_ids'] = 'delta-5'
            people.append(person)
        payload, _ = normalizer.normalize_source(people, source_kind='flat_json')
        geo = geometry.layout(payload, 'matrix_relationships')
        slides.cards(geo['pages'][0])[-1]['data']['context'] = True
        req = requests(geo)
        legend_ids = {slides.ident(geo['pages'][0]['id'] + '-legend-' + status)
                      for status in ('filled', 'open', 'planned', 'resigned', 'other',
                                     'context', 'contingent')}
        swatches = [r['createShape'] for r in req if 'createShape' in r
                    and r['createShape']['objectId'] in legend_ids]
        self.assertEqual(len(swatches), 7)
        summary = slides.compile_requests(geo, 'neutral')['summary']
        self.assertEqual(summary['legend_items'], 7)  # Six statuses plus matrix.
        self.assertEqual(summary['contingent_legend_items'], 1)
        for swatch in swatches:
            props = swatch['elementProperties']
            self.assertLess(props['transform']['translateX'] + props['size']['width']['magnitude'],
                            9.75 * 72)

    def test_page_fonts_are_fitted_per_card_type(self):
        payload, _ = normalizer.normalize_source(
            [row(), dict(row('Person Delta ' + '12' * 30, manager_node_id='delta-12'),
                         node_id='delta-13', title='Role Delta ' * 20)], source_kind='flat_json')
        geo = geometry.layout(payload, 'compact_hierarchy')
        page = geo['pages'][0]
        summary = geometry._summary_card('summary-delta', 'Summary', 'Summary body',
                                         {'x': 1, 'y': 1, 'w': 2, 'h': 1}, page['id'])
        page['elements'].append(summary)
        ids = {slides.card_id(c) for c in slides.cards(page) if c['type'] != 'group_summary_card'}
        req = requests(geo)
        styles = [r['updateTextStyle'] for r in req if 'updateTextStyle' in r
                  and r['updateTextStyle']['objectId'] in ids]
        for range_type in ('ALL', 'FIXED_RANGE'):
            sizes = [s['style']['fontSize']['magnitude'] for s in styles
                     if s['textRange']['type'] == range_type]
            self.assertEqual(sizes, [8, 8])
        summary_sizes = {r['updateTextStyle']['style']['fontSize']['magnitude'] for r in req
                         if r.get('updateTextStyle', {}).get('objectId') == slides.card_id(summary)}
        self.assertEqual(summary_sizes, {9, 10})
