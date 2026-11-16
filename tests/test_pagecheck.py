"""Page-completeness check run before the template cleanup call."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_compile_verify import SCRIPTS, connector_readback, flat, tiny_geometry  # noqa: E402
import slides_requests as slides  # noqa: E402


class PageCheckTest(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / 'slides_requests.py'), *map(str, args)],
                              capture_output=True, text=True)

    def build(self, folder):
        geo = folder / 'geometry.json'
        geo.write_text(json.dumps(tiny_geometry(3)))
        split = folder / 'pages'
        self.assertEqual(self.cli('compile', geo, '--theme', 'neutral', '--split-dir', split).returncode, 0)
        result = slides.compile_requests(tiny_geometry(3), slides.templates.resolve_theme('neutral'))
        return split, connector_readback(result)

    def test_manifest_has_expected_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            split, _ = self.build(Path(tmp))
            manifest = json.loads((split / 'manifest.json').read_text())
            for entry in manifest['files']:
                self.assertEqual(entry['expected_elements'], 7)  # title, cards, lines, legend
                self.assertTrue(entry['slide_object_id'])
                self.assertGreater(entry['bytes'], 0)
            self.assertIn('pagecheck', manifest['cleanup_instruction'])

    def test_complete_deck_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            split, readback = self.build(Path(tmp))
            path = Path(tmp, 'rb.json'); path.write_text(json.dumps(readback))
            result = self.cli('pagecheck', split, path)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn('Safe to send cleanup.json', result.stdout)
            self.assertEqual(result.stdout.count('OK '), 3)

    def test_truncated_and_missing_pages_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            split, readback = self.build(Path(tmp))
            broken = copy.deepcopy(readback)
            slides_list = broken['content']['slides'] if 'content' in broken else broken['slides']
            slides_list[1]['pageElements'] = slides_list[1]['pageElements'][:3]
            del slides_list[2]
            path = Path(tmp, 'rb.json'); path.write_text(json.dumps(broken))
            result = self.cli('pagecheck', split, path)
            self.assertEqual(result.returncode, 1)
            self.assertIn('MISSING  page-002.json: 3 of 7', result.stdout)
            self.assertIn('MISSING  page-003.json: 0 of 7 elements; slide not found', result.stdout)
            self.assertIn('Do not send cleanup.json', result.stdout)
            only = self.cli('pagecheck', split, path, '--page', 'page-001.json')
            self.assertEqual(only.returncode, 0, only.stdout)


if __name__ == '__main__':
    unittest.main()
