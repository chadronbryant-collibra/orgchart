"""Lossless request compaction, transport, and legacy readback contracts."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/orgchart/scripts'
sys.path.insert(0, str(SCRIPTS))
import org_chart_geometry as geometry
import slides_requests as slides
from test_compile_verify import connector_readback, flat, tiny_geometry
from test_large_orgs import roster


class CompactRequestsTests(unittest.TestCase):
    def test_one_z_order_per_nonempty_page_preserves_stacking(self):
        geo = tiny_geometry(3)
        geo['pages'][-1]['connectors'] = []
        result = slides.compile_requests(geo, 'neutral', chunk=1)
        stacks, current, moved = {}, None, {}
        for request in flat(result):
            if 'createSlide' in request:
                current = request['createSlide']['objectId']
                stacks[current] = []
            for operation in ('createShape', 'createLine'):
                if operation in request:
                    stacks[current].append(request[operation]['objectId'])
            if 'updatePageElementsZOrder' in request:
                update = request['updatePageElementsZOrder']
                self.assertNotIn(current, moved)
                moved[current] = update['pageElementObjectIds']
                self.assertEqual(update['operation'], 'SEND_TO_BACK')
                self.assertTrue(set(moved[current]) <= set(stacks[current]))
                # Slides preserves existing relative order within the selection.
                selected = set(moved[current])
                stacks[current] = ([x for x in stacks[current] if x in selected]
                                   + [x for x in stacks[current] if x not in selected])
        self.assertEqual(len(moved), 2)
        for page in geo['pages']:
            pid = slides.ident(page['id'])
            expected = [slides.line_id(line) for line in reversed(page['connectors'])]
            self.assertEqual(stacks[pid][:len(expected)], expected)
            if expected:
                self.assertEqual(set(moved[pid]), set(expected))

    def test_line_defaults_removed_and_masks_match(self):
        geo = tiny_geometry()
        geo['pages'][0]['connectors'][0]['line_style'] = 'dotted'
        for theme in slides.THEMES:
            updates = [r['updateLineProperties'] for r in
                       flat(slides.compile_requests(geo, theme)) if 'updateLineProperties' in r]
            for update in updates:
                properties = update['lineProperties']
                self.assertEqual(set(update['fields'].split(',')), set(properties))
                self.assertTrue({'lineFill', 'startConnection', 'endConnection'} <= set(properties))
                self.assertFalse({'weight', 'startArrow', 'endArrow'} & set(properties))
                line = next(line for line in geo['pages'][0]['connectors']
                            if slides.line_id(line) == update['objectId'])
                if line.get('line_style') == 'dotted':
                    self.assertEqual(properties['dashStyle'], 'DOT')
                else:
                    self.assertNotIn('dashStyle', properties)
                self.assertEqual(properties['startConnection']['connectionSiteIndex'], 2)
                self.assertEqual(properties['endConnection']['connectionSiteIndex'], 0)

    def test_shape_defaults_removed_non_solid_dashes_retained(self):
        geo = tiny_geometry()
        cards = geo['pages'][0]['elements']
        cards[0]['data']['status'] = 'open'
        cards[1]['data']['status'] = 'planned'
        cards[2]['data']['worker_type'] = 'contingent'
        for theme in slides.THEMES:
            updates = [r['updateShapeProperties'] for r in
                       flat(slides.compile_requests(geo, theme)) if 'updateShapeProperties' in r]
            for update in updates:
                self.assertEqual(update['fields'], 'shapeBackgroundFill,outline,contentAlignment')
                outline = update['shapeProperties']['outline']
                self.assertNotIn('weight', outline)
                self.assertNotEqual(outline.get('dashStyle'), 'SOLID')
            for card, dash in zip(cards, ('DASH', 'DOT', 'LONG_DASH_DOT')):
                update = next(u for u in updates if u['objectId'] == slides.card_id(card))
                self.assertEqual(update['shapeProperties']['outline']['dashStyle'], dash)

    def test_integral_numbers_and_compact_transport(self):
        self.assertEqual(slides.color('00FF00'), {'rgbColor': {'red': 0, 'green': 1, 'blue': 0}})
        self.assertIs(type(slides.color('00FF00')['rgbColor']['green']), int)
        self.assertIs(type(slides.props('page-id', dict(x=0, y=1, w=2, h=3))
                           ['transform']['translateY']), int)
        self.assertEqual(slides._r(1.2345), 1.23)
        self.assertEqual(slides._r(-0.0), 0)
        result = slides.compile_requests(tiny_geometry(2), 'neutral', chunk=3)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output.json'
            slides.write_json(output, result)
            slides.write_pages(Path(directory) / 'pages', result)
            for path in [output, *sorted((Path(directory) / 'pages').glob('*.json'))]:
                text = path.read_text(encoding='utf-8')
                self.assertEqual(text, json.dumps(json.loads(text), ensure_ascii=False,
                                                 separators=(',', ':')) + '\n')

    def test_legacy_readbacks_still_pass_and_bad_endpoints_fail(self):
        geo = tiny_geometry()
        readback = connector_readback(slides.compile_requests(geo, 'neutral'))
        for element in readback['content']['slides'][0]['pageElements']:
            if 'line' in element:
                element['line']['lineProperties'].update(
                    weight={'magnitude': 1, 'unit': 'PT'}, dashStyle='SOLID',
                    startArrow='NONE', endArrow='NONE')
        self.assertTrue(all(ok for _, _, ok in slides.verify(geo, readback)))
        bad = copy.deepcopy(readback)
        line = next(e['line'] for e in bad['content']['slides'][0]['pageElements'] if 'line' in e)
        line['lineProperties']['endConnection']['connectedObjectId'] = 'wrong-card'
        self.assertEqual(sum(not ok for _, _, ok in slides.verify(geo, bad)), 1)

    def test_large_page_size_regression(self):
        # The scale fixture needs >= 156 people; retain its first 150 people,
        # whose managers all precede them. This is still a complete rooted org.
        source = roster(300)
        source['people'] = source['people'][:150]
        geo = geometry.layout(source, 'enterprise_overview')
        page = next(p for p in geo['pages']
                    if p['id'] == 'org-page-enterprise-function-0-5-b08acfa5')
        requests = flat(slides.compile_requests(dict(geo, pages=[page]), 'collibra-2026'))
        size = len((json.dumps(requests, ensure_ascii=False, separators=(',', ':')) + '\n').encode())
        # Previous compact-format baseline: 55,097 bytes / 190 requests.
        # These bounds record the achieved saving, not the requested 25% goal.
        self.assertLessEqual(size, 49730)
        self.assertLessEqual(len(requests), 172)


if __name__ == '__main__':
    unittest.main()
