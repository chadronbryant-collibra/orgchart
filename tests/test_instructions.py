import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/orgchart'


class InstructionConsistencyTest(unittest.TestCase):
    def test_size_limits_agree_with_code(self):
        geometry = (SKILL / 'scripts/org_chart_geometry.py').read_text()
        limit = int(re.search(r'^MAX_PEOPLE = (\d+)', geometry, re.M).group(1))
        pages = int(re.search(r'^MAX_PAGES = (\d+)', geometry, re.M).group(1))
        text = '\n'.join(p.read_text() for p in [
            SKILL / 'SKILL.md', SKILL / 'references/statuses.md',
            SKILL / 'references/layouts.md', SKILL / 'references/overview.md',
            ROOT / 'docs/FAQ.md'])
        self.assertNotIn('200 people', text)
        self.assertNotIn('30 pages', text)
        self.assertIn(f'{limit:,}', text)
        self.assertIn(f'{pages} pages', text)

    def test_no_repo_relative_script_paths_in_skill(self):
        for path in SKILL.rglob('*.md'):
            self.assertNotIn('skills/orgchart/scripts', path.read_text(), path)

    def test_description_covers_planned_roles_and_excludes_lookups(self):
        text = (SKILL / 'SKILL.md').read_text()
        description = re.search(r'^description: "(.*)"$', text, re.M).group(1)
        for phrase in ('org chart', 'planned roles', 'current vs planned'):
            self.assertIn(phrase, description)
        self.assertIn('Not for', description)

    def test_help_points_to_overview_and_privacy_is_in_skill(self):
        text = (SKILL / 'SKILL.md').read_text()
        self.assertIn('references/overview.md', text)
        self.assertIn('pay, performance', text)
        overview = (SKILL / 'references/overview.md').read_text()
        for word in ('Simple tree', 'Matrix', 'Scenarios', 'Statuses', 'Left out on purpose'):
            self.assertIn(word, overview)
        self.assertIn('parentId', text)

    def test_example_scenario_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, receipt = Path(tmp, 'o.json'), Path(tmp, 'r.json')
            result = subprocess.run(
                [sys.executable, str(SKILL / 'scripts/apply_org_chart_scenario.py'),
                 str(SKILL / 'examples/synthetic-scenario.json'),
                 '--output', str(out), '--receipt', str(receipt)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(out.read_text()))


if __name__ == '__main__':
    unittest.main()
