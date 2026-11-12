"""Synthetic compiler transport and connector readback regressions."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/orgchart/scripts'
sys.path.insert(0, str(SCRIPTS))
import slides_requests as slides


def tiny_geometry(page_count=1):
    pages = []
    for page_number in range(page_count):
        pid = f'synthetic-page-{page_number}'
        cards = []
        for i in range(3):
            cards.append({
                'stable_name': f'{pid}-card-{i}', 'collision_class': 'card',
                'box': {'x': 0.421234 + i * 3.123456, 'y': 1.234567 + i,
                        'w': 2.123456, 'h': 0.723456},
                'data': {'name': f'Person {page_number * 3 + i} Ω', 'title': 'Synthetic role'},
            })
        connectors = []
        for i in (1, 2):
            connectors.append({
                'stable_name': f'{pid}-line-{i}',
                'from': cards[0]['stable_name'], 'to': cards[i]['stable_name'],
                'segments': [{'x1': 1.482962, 'y1': 1.958023,
                              'x2': 1.482962 + i * 3.123456, 'y2': 1.234567 + i}],
                'google_slides_from_site_index': 2, 'google_slides_to_site_index': 0,
            })
        pages.append({'id': pid, 'elements': cards, 'connectors': connectors})
    return {'title': 'Synthetic organization', 'pages': pages}


def flat(result):
    return [r for chunk in result['presentation_requests'] for r in chunk]


def connector_readback(result):
    """Build only the read_presentation fields used by verify from requests."""
    pages, elements = {}, {}
    for request in flat(result):
        if 'createSlide' in request:
            obj = request['createSlide']['objectId']
            pages[obj] = {'objectId': obj, 'pageElements': []}
        for operation, kind in (('createShape', 'shape'), ('createLine', 'line')):
            if operation in request:
                data = request[operation]
                element = {'objectId': data['objectId'], kind: {}}
                if kind == 'shape':
                    element[kind] = {'shapeType': data['shapeType'], 'text': {'textElements': []}}
                elements[data['objectId']] = element
                pages[data['elementProperties']['pageObjectId']]['pageElements'].append(element)
        if 'insertText' in request:
            data = request['insertText']
            elements[data['objectId']]['shape']['text']['textElements'].append(
                {'textRun': {'content': data['text']}})
        if 'updateLineProperties' in request:
            data = request['updateLineProperties']
            elements[data['objectId']]['line']['lineProperties'] = copy.deepcopy(data['lineProperties'])
    return {'content': {'slides': list(pages.values())}}


# Measured before compiler changes: indent=2, ensure_ascii=False, trailing newline.
OLD_12_PERSON_4_PAGE_BYTES = 81703


class CompileVerifyTests(unittest.TestCase):
    def setUp(self):
        self.geo = tiny_geometry()
        self.result = slides.compile_requests(self.geo, 'collibra-2026')
        self.raw = connector_readback(self.result)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / 'slides_requests.py'), *map(str, args)],
                              capture_output=True, text=True)

    def test_raw_connector_fixture_and_envelopes(self):
        bare = self.raw['content']
        for payload in (bare, self.raw, json.dumps(bare), json.dumps(self.raw),
                        [{'type': 'text', 'text': json.dumps(bare)}],
                        [{'type': 'text', 'text': json.dumps(self.raw)}],
                        {'content': [{'type': 'text', 'text': json.dumps(self.raw)}]}):
            with self.subTest(payload=payload):
                self.assertEqual(slides.unwrap_readback(payload), bare)
                checks = slides.verify(self.geo, payload)
                self.assertEqual(len(checks), 6)  # One slide, three cards, two lines.
                self.assertTrue(all(ok for _, _, ok in checks))

    def test_bad_envelope_error_lists_shapes(self):
        for payload in ({}, {'content': {}}, {'slides': None}, [], 'not JSON',
                        [{'type': 'text', 'text': 'not JSON'}]):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, 'Expected readback') as error:
                    slides.unwrap_readback(payload)
                for shape in ('slides', 'content', 'JSON string', 'MCP text blocks'):
                    self.assertIn(shape, str(error.exception))

    def test_missing_connections_fail_and_omitted_zero_passes(self):
        line = next(e['line']['lineProperties'] for e in self.raw['content']['slides'][0]['pageElements']
                    if 'line' in e)
        del line['endConnection']['connectionSiteIndex']
        self.assertTrue(all(ok for _, _, ok in slides.verify(self.geo, self.raw)))
        for field in ('startConnection', 'endConnection'):
            for value in ('missing', None, {}):
                payload = copy.deepcopy(self.raw)
                properties = next(e['line']['lineProperties'] for e in payload['content']['slides'][0]['pageElements']
                                  if 'line' in e)
                if value == 'missing':
                    del properties[field]
                else:
                    properties[field] = value
                checks = slides.verify(self.geo, payload)
                self.assertEqual(sum(not ok for _, _, ok in checks), 1)

    def test_compact_size_pretty_and_rounding(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            geo, output, pretty = (folder / name for name in ('geometry.json', 'out.json', 'pretty.json'))
            geo.write_text(json.dumps(tiny_geometry(4)), encoding='utf-8')
            args = ('compile', geo, '--theme', 'collibra-2026')
            result = self.cli(*args, '--output', output)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary['cards'], 12)
            self.assertEqual(summary['pages'], 4)
            self.assertEqual(summary['pages_files'], 0)
            self.assertEqual(result.stdout.strip(), json.dumps(summary, sort_keys=True))
            self.assertLessEqual(output.stat().st_size, OLD_12_PERSON_4_PAGE_BYTES * .65)
            self.assertIn('Ω', output.read_text(encoding='utf-8'))
            self.assertEqual(len(output.read_text().splitlines()), 1)
            result = self.cli(*args, '--output', pretty, '--pretty')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text()), json.loads(pretty.read_text()))
            self.assertEqual(pretty.read_text(), json.dumps(json.loads(output.read_text()),
                                                          indent=2, ensure_ascii=False) + '\n')

        def check(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in ('magnitude', 'translateX', 'translateY'):
                        self.assertEqual(item, round(item, 2))
                    if key in ('red', 'green', 'blue'):
                        self.assertEqual(item, round(item, 4))
                    check(item)
            elif isinstance(value, list):
                for item in value:
                    check(item)
        check(self.result)
        self.assertEqual(slides.props('synthetic', {'x': 1/3, 'y': 1/7, 'w': 1/11, 'h': 1/13})
                         ['size']['width']['magnitude'], 6.55)
        self.assertEqual(slides.color('002B40')['rgbColor']['green'], .1686)

    def test_per_page_files_equal_flat_output_and_are_self_contained(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            geo, existing, output = (folder / name for name in ('geometry.json', 'existing.json', 'out.json'))
            geo.write_text(json.dumps(tiny_geometry(4)))
            existing.write_text(json.dumps({'content': {'slides': [{'objectId': 'template-slide'}]}}))
            split = folder / 'pages'
            args = ('compile', geo, '--theme', 'collibra-2026', '--existing-slides', existing,
                    '--chunk', '7', '--split-dir', split)
            result = self.cli(*args, '--output', output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['pages_files'], 4)
            manifest = json.loads((split / 'manifest.json').read_text())
            self.assertEqual([f['file'] for f in manifest['files']],
                             [f'page-{i:03}.json' for i in range(1, 5)])
            combined = []
            for i, entry in enumerate(manifest['files']):
                requests = json.loads((split / entry['file']).read_text())
                self.assertEqual(entry['request_count'], len(requests))
                self.assertIn('createSlide', requests[0])
                self.assertEqual(sum('createSlide' in r for r in requests), 1)
                self.assertFalse(any('deleteObject' in r for r in requests))
                # Simulate submitting this page alone; endpoints must already exist.
                created = set()
                for request in requests:
                    for operation in ('createSlide', 'createShape', 'createLine'):
                        if operation in request:
                            created.add(request[operation]['objectId'])
                    if 'updateLineProperties' in request:
                        properties = request['updateLineProperties']['lineProperties']
                        for field in ('startConnection', 'endConnection'):
                            self.assertIn(properties[field]['connectedObjectId'], created)
                readback = connector_readback({'presentation_requests': [requests]})
                checks = slides.verify({'pages': [tiny_geometry(4)['pages'][i]]}, readback)
                self.assertTrue(all(ok for _, _, ok in checks))
                combined.extend(requests)
            cleanup = json.loads((split / 'cleanup.json').read_text())
            self.assertEqual(cleanup, [{'deleteObject': {'objectId': 'template-slide'}}])
            self.assertEqual(manifest['cleanup'], {'file': 'cleanup.json', 'request_count': 1})
            self.assertEqual(combined + cleanup, flat(json.loads(output.read_text())))
            # A split directory can also be the only output.
            result = self.cli(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = self.cli('compile', geo, '--theme', 'neutral')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('--output or --split-dir', result.stderr)

    def test_summary_and_multiple_readback_files(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            geo = tiny_geometry(2)
            geometry_file = folder / 'geometry.json'
            geometry_file.write_text(json.dumps(geo))
            payload = connector_readback(slides.compile_requests(geo, 'neutral'))
            files = []
            for i, page in enumerate(payload['content']['slides']):
                path = folder / f'readback-{i}.json'
                path.write_text(json.dumps({'content': {'slides': [page]}}))
                files.append(path)
            result = self.cli('verify', geometry_file, *files, '--summary')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, 'PASS 12 FAIL 0\n')
            page = payload['content']['slides'][0]
            line = next(e for e in page['pageElements'] if 'line' in e)
            del line['line']['lineProperties']['startConnection']
            files[0].write_text(json.dumps({'content': {'slides': [page]}}))
            result = self.cli('verify', geometry_file, *files, '--summary')
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(result.stdout.splitlines(),
                             ['PASS 11 FAIL 1', f"FAIL    connector  {line['objectId']}"])
            full = self.cli('verify', geometry_file, *files)
            self.assertEqual(full.returncode, 1)
            self.assertTrue(full.stdout.startswith('RESULT  TYPE       OBJECT ID\n'))
            self.assertEqual(len(full.stdout.splitlines()), 13)


if __name__ == '__main__':
    unittest.main()
