import json
import subprocess
import sys
import tempfile
import unittest
import hashlib
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / 'skills/orgchart'
sys.path.insert(0, str(SKILL / 'scripts'))
import normalize_org_chart as normalizer
import org_chart_geometry as geometry
import slides_requests as slides
import templates

NEW_THEMES = ['dark-mode', 'high-contrast', 'soft-pastel', 'function-colors', 'print-mono', 'corporate-blue']
STARTERS = ('simple-team', 'functional-org', 'future-state-plan')
SCRIPT = SKILL / 'scripts/slides_requests.py'


def geo_for(starter, mode):
    rows = json.loads((SKILL / 'examples/starters' / f'{starter}.json').read_text())
    return geometry.layout(normalizer.normalize_source(rows, source_kind='flat_json')[0], mode)


def flat(result):
    return [r for chunk in result['presentation_requests'] for r in chunk]


class RegressionTests(unittest.TestCase):
    def test_legacy_themes_are_byte_identical(self):
        baseline = json.loads((Path(__file__).parent / 'fixtures/theme_baseline.json').read_text())
        self.assertEqual(len(baseline), 30)
        for key, digest in baseline.items():
            starter, mode, theme = key.split('|')
            with self.subTest(key=key):
                result = slides.compile_requests(geo_for(starter, mode), theme, layout_id='layout_x_12345')
                self.assertEqual(hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest(), digest)


class BuiltInThemeTests(unittest.TestCase):
    def test_theme_set(self):
        self.assertEqual(list(slides.THEMES)[:2], ['collibra-2026', 'neutral'])
        self.assertTrue(set(NEW_THEMES) <= set(slides.THEMES))

    def test_manifest_lists_every_theme(self):
        data = json.loads((SKILL / 'templates/manifest.json').read_text())
        self.assertEqual(templates.validate(data), [])
        used = {e['theme'] for e in data['templates'] if 'theme' in e}
        self.assertEqual(used, set(slides.THEMES))

    def test_new_themes_pass_contrast_checks(self):
        for name in NEW_THEMES:
            with self.subTest(theme=name):
                self.assertEqual(templates.theme_warnings(templates.resolve_theme(name)), [])

    def test_wcag_aa_text_contrast(self):
        for name in NEW_THEMES:
            theme = templates.resolve_theme(name, color_by_function=True)
            ground = theme['background'] or 'FFFFFF'
            fills = [s['fill'] for s in theme['statuses'].values()] + [p['fill'] for p in theme['color_by_function']['palette']]
            for fill in fills:
                for key in ('ink', 'muted'):
                    with self.subTest(theme=name, fill=fill, text=key):
                        self.assertGreaterEqual(templates.contrast(theme['colors'][key], fill), 4.5)
            self.assertGreaterEqual(templates.contrast(theme['title']['color'], ground), 4.5)
            self.assertGreaterEqual(templates.contrast(theme['colors']['ink'], theme['colors']['surface']), 4.5)

    def test_high_contrast_meets_aaa(self):
        theme = templates.resolve_theme('high-contrast')
        for s in theme['statuses'].values():
            self.assertGreaterEqual(templates.contrast(theme['colors']['ink'], s['fill']), 7)
            self.assertGreaterEqual(templates.contrast(theme['colors']['muted'], s['fill']), 7)

    def test_status_meaning_not_by_colour_alone(self):
        for name in NEW_THEMES:
            theme = templates.resolve_theme(name)
            dashes = [theme['statuses'][s]['dash'] for s in templates.PATTERN_STATUSES]
            with self.subTest(theme=name):
                self.assertEqual(len(set(dashes)), len(dashes))

    def test_status_text_still_on_cards(self):
        geo = geo_for('future-state-plan', 'compact_hierarchy')
        for name in NEW_THEMES:
            text = json.dumps(slides.compile_requests(geo, name))
            self.assertIn('Open role', text); self.assertIn('Planned', text)

    def test_every_theme_compiles_and_verifies_with_native_shapes(self):
        for name in slides.THEMES:
            for starter in STARTERS:
                geo = geo_for(starter, 'functional_columns')
                with self.subTest(theme=name, starter=starter):
                    requests = flat(slides.compile_requests(geo, name))
                    self.assertFalse([r for r in requests if 'createImage' in r])
                    shapes = {r['createShape']['shapeType'] for r in requests if 'createShape' in r}
                    self.assertTrue(shapes <= {'ROUND_RECTANGLE', 'RECTANGLE', 'TEXT_BOX'})

    def test_dark_mode_sets_background_and_square_corners(self):
        geo = geo_for('simple-team', 'compact_hierarchy')
        dark = flat(slides.compile_requests(geo, 'dark-mode'))
        self.assertTrue(any('updatePageProperties' in r for r in dark))
        self.assertFalse(any('updatePageProperties' in r for r in flat(slides.compile_requests(geo, 'neutral'))))
        shapes = {r['createShape']['shapeType'] for r in flat(slides.compile_requests(geo, 'print-mono')) if 'createShape' in r}
        self.assertIn('RECTANGLE', shapes); self.assertNotIn('ROUND_RECTANGLE', shapes)

    def test_schema_matches_theme_files(self):
        schema = json.loads((SKILL / 'templates/themes/theme.schema.json').read_text())
        self.assertEqual(set(schema['properties']), set(templates.TOP_FIELDS))
        for name, raw in slides.THEMES.items():
            self.assertEqual(set(raw) - set(templates.TOP_FIELDS), set(), name)
            self.assertEqual(set(raw['statuses']), set(templates.STATUSES), name)


class UserThemeTests(unittest.TestCase):
    def test_overlay_merges_over_base(self):
        theme = templates.resolve_theme('neutral', {'colors': {'ink': '#112233'}, 'statuses': {'open': {'dash': 'LONG_DASH'}}})
        self.assertEqual(theme['colors']['ink'], '112233')
        self.assertEqual(theme['statuses']['open']['dash'], 'LONG_DASH')
        self.assertEqual(theme['statuses']['open']['outline'], '757575')
        self.assertEqual(theme['colors']['muted'], '757575')

    def test_accent_override_reaches_cards_and_lines(self):
        geo = geo_for('functional-org', 'matrix_relationships')
        theme = templates.resolve_theme('collibra-2026', accent='#AA00CC')
        text = json.dumps(slides.compile_requests(geo, theme))
        self.assertIn(json.dumps(slides.color('AA00CC')['rgbColor'])[:10], text)
        self.assertNotEqual(text, json.dumps(slides.compile_requests(geo, 'collibra-2026')))
        self.assertEqual(theme['statuses']['open']['outline'], 'AA00CC')
        self.assertEqual(theme['colors']['matrix_line'], 'AA00CC')

    def test_color_by_function_cycles_palette(self):
        geo = geo_for('functional-org', 'functional_columns')
        theme = templates.resolve_theme('neutral', {'color_by_function': {'enabled': True, 'palette': [
            {'fill': 'FFD6A5', 'outline': '9C4A00'}, {'fill': 'CFF5C0', 'outline': '2E7D32'}]}})
        requests = flat(slides.compile_requests(geo, theme))
        fills = {json.dumps(r['updateShapeProperties']['shapeProperties']['shapeBackgroundFill'], sort_keys=True)
                 for r in requests if 'updateShapeProperties' in r and 'solidFill' in r['updateShapeProperties']['shapeProperties'].get('shapeBackgroundFill', {})}
        for colour in ('FFD6A5', 'CFF5C0'):
            self.assertIn(json.dumps({'solidFill': {'color': slides.color(colour)}}, sort_keys=True), fills)
        functions = {e['data']['function'] for p in geo['pages'] for e in slides.cards(p)}
        self.assertGreater(len(functions), 2)

    def test_color_by_function_is_deterministic_and_filled_only(self):
        geo = geo_for('future-state-plan', 'functional_columns')
        theme = templates.resolve_theme('soft-pastel', color_by_function=True)
        self.assertEqual(slides.compile_requests(geo, theme), slides.compile_requests(geo, theme))

    def test_dark_theme_without_palette_is_refused(self):
        with self.assertRaises(templates.ThemeError) as ctx:
            templates.resolve_theme('dark-mode', {'colors': {'surface': '000000'}, 'color_by_function': {'palette': None, 'enabled': False}}, color_by_function=True)
        self.assertIn('palette', str(ctx.exception))

    def test_footer(self):
        geo = geo_for('simple-team', 'compact_hierarchy')
        theme = templates.resolve_theme('neutral', footer='Acme Corp | Confidential')
        self.assertIn('Acme Corp | Confidential', json.dumps(slides.compile_requests(geo, theme)))
        self.assertNotIn('Acme', json.dumps(slides.compile_requests(geo, 'neutral')))

    def assertPlainError(self, overlay, *fragments, **kw):
        with self.assertRaises(templates.ThemeError) as ctx:
            templates.resolve_theme('neutral', overlay, **kw)
        message = str(ctx.exception)
        for fragment in fragments:
            self.assertIn(fragment, message)
        self.assertNotIn('Traceback', message); self.assertNotIn('KeyError', message)

    def test_plain_language_errors(self):
        self.assertPlainError({'colors': {'ink': 'blue'}}, "'blue'", 'colors.ink', 'six hex digits')
        self.assertPlainError({'colours': {}}, "Unknown setting 'colours'", "Did you mean 'colors'")
        self.assertPlainError({'colors': {'inks': '#000000'}}, "colors.inks", "Did you mean 'ink'")
        self.assertPlainError({'statuses': {'open': {'dash': 'WAVY'}}}, 'WAVY', 'Choose one of')
        self.assertPlainError({'statuses': {'open': {'fil': 'FFFFFF'}}}, 'statuses.open.fil', "'fill'")
        self.assertPlainError({'title': {'align': 'MIDDLE'}}, 'title.align')
        self.assertPlainError({'card_corners': 'pointy'}, 'card_corners')
        self.assertPlainError({'font': '<b>'}, 'font')
        self.assertPlainError({'footer': {'text': 'x' * 200}}, 'footer.text')
        self.assertPlainError({}, "'#12'", accent='#12')
        self.assertPlainError({'color_by_function': {'palette': [{'fill': 'FFFFFF'}]}}, 'palette')
        with self.assertRaises(templates.ThemeError) as ctx:
            templates.resolve_theme('nope')
        self.assertIn('Available themes', str(ctx.exception))

    def test_low_contrast_is_warned_not_refused(self):
        theme = templates.resolve_theme('neutral', {'colors': {'ink': 'EEEEEE'}})
        self.assertTrue(any('hard to read' in n for n in templates.theme_warnings(theme)))

    def test_shared_patterns_are_warned(self):
        theme = templates.resolve_theme('neutral', {'statuses': {'planned': {'dash': 'DASH'}}})
        self.assertTrue(any('line pattern' in n for n in templates.theme_warnings(theme)))


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def test_themes_listing_and_preview(self):
        out = self.run_cli('themes')
        self.assertEqual(out.returncode, 0)
        for name in slides.THEMES:
            self.assertIn(name, out.stdout)
        preview = self.run_cli('themes', '--preview')
        self.assertEqual(preview.returncode, 0)
        self.assertEqual(preview.stdout.count('outline #'), 7 * len(slides.THEMES))
        one = self.run_cli('themes', '--preview', 'dark-mode')
        self.assertIn('page background  #0F1B26', one.stdout); self.assertNotIn('neutral', one.stdout)
        self.assertEqual(self.run_cli('themes', '--preview', 'nope').returncode, 1)

    def test_compile_with_theme_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            geo = tmp / 'geo.json'; geo.write_text(json.dumps(geo_for('simple-team', 'compact_hierarchy')))
            theme = tmp / 'my-theme.json'
            theme.write_text(json.dumps({'extends': 'dark-mode', 'accent': '#FFB000', 'footer': {'text': 'Synthetic Co'}}))
            out = tmp / 'out.json'
            result = self.run_cli('compile', str(geo), '--theme-file', str(theme), '--output', str(out))
            self.assertEqual(result.returncode, 0, result.stderr)
            text = out.read_text()
            self.assertIn('Synthetic Co', text); self.assertIn('pageBackgroundFill', text)
            result = self.run_cli('compile', str(geo), '--theme', 'neutral', '--accent', '#FFB000', '--color-by-function', '--output', str(out))
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_compile_errors_are_plain(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            geo = tmp / 'geo.json'; geo.write_text(json.dumps(geo_for('simple-team', 'compact_hierarchy')))
            bad = tmp / 'bad.json'; bad.write_text(json.dumps({'colors': {'ink': 'navy'}}))
            result = self.run_cli('compile', str(geo), '--theme-file', str(bad), '--output', str(tmp / 'o.json'))
            self.assertEqual(result.returncode, 1)
            self.assertIn("'navy'", result.stderr); self.assertNotIn('Traceback', result.stderr)
            broken = tmp / 'broken.json'; broken.write_text('{')
            self.assertIn('not valid JSON', self.run_cli('compile', str(geo), '--theme-file', str(broken), '--output', str(tmp / 'o.json')).stderr)
            self.assertIn('Choose a look', self.run_cli('compile', str(geo), '--output', str(tmp / 'o.json')).stderr)
            self.assertIn('Unknown theme', self.run_cli('compile', str(geo), '--theme', 'nope', '--output', str(tmp / 'o.json')).stderr)
            low = tmp / 'low.json'; low.write_text(json.dumps({'colors': {'ink': 'EEEEEE'}}))
            result = self.run_cli('compile', str(geo), '--theme-file', str(low), '--output', str(tmp / 'o.json'))
            self.assertEqual(result.returncode, 0); self.assertIn('Warning:', result.stderr)


if __name__ == '__main__':
    unittest.main()
