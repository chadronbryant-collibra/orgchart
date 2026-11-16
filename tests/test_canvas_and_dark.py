"""Blank-canvas themes copy a 16:9 file, and dark themes stay off branded templates."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / 'skills/orgchart'
sys.path.insert(0, str(SKILL / 'scripts'))
import normalize_org_chart as normalizer
import org_chart_geometry as geometry
import templates

SCRIPT = SKILL / 'scripts/slides_requests.py'
MANIFEST = json.loads((SKILL / 'templates/manifest.json').read_text())


def geo_file(tmp):
    rows = json.loads((SKILL / 'examples/starters/simple-team.json').read_text())
    path = Path(tmp) / 'geo.json'
    path.write_text(json.dumps(geometry.layout(normalizer.normalize_source(rows, source_kind='flat_json')[0], 'compact_hierarchy')))
    return path


class BlankCanvasTests(unittest.TestCase):
    def test_every_blank_canvas_theme_has_a_file_and_layout(self):
        built_in = [e for e in MANIFEST['templates'] if e['kind'] == 'built-in']
        self.assertTrue(built_in)
        for entry in built_in:
            self.assertTrue(entry.get('file_id'), entry['id'])
            self.assertTrue(entry.get('layout_id'), entry['id'])
        self.assertEqual(len({e['file_id'] for e in built_in}), 1)
        self.assertEqual(templates.validate(MANIFEST), [])

    def test_writer_never_creates_a_blank_deck(self):
        text = (SKILL / 'references/slides-writer.md').read_text()
        self.assertIn('Never create a new blank deck', text)
        self.assertNotIn('Page setup', text)


class DarkThemeGuardTests(unittest.TestCase):
    def run_compile(self, *extra):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out.json'
            return subprocess.run([sys.executable, str(SCRIPT), 'compile', str(geo_file(tmp)), '--output', str(out), *extra],
                                  capture_output=True, text=True)

    def branded(self):
        return next(e['layout_id'] for e in MANIFEST['templates'] if e['kind'] == 'google-slides')

    def blank(self):
        return next(e['layout_id'] for e in MANIFEST['templates'] if e['kind'] == 'built-in')

    def test_dark_theme_on_branded_template_is_refused(self):
        result = self.run_compile('--theme', 'dark-mode', '--layout-id', self.branded())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('hide the logo', result.stderr + result.stdout)

    def test_dark_theme_on_blank_canvas_compiles(self):
        self.assertEqual(self.run_compile('--theme', 'dark-mode', '--layout-id', self.blank()).returncode, 0)

    def test_light_theme_on_branded_template_compiles(self):
        self.assertEqual(self.run_compile('--theme', 'collibra-2026', '--layout-id', self.branded()).returncode, 0)

    def test_dark_background_detection(self):
        self.assertTrue(templates.dark_background(templates.resolve_theme('dark-mode')))
        self.assertFalse(templates.dark_background(templates.resolve_theme('neutral')))


if __name__ == '__main__':
    unittest.main()
