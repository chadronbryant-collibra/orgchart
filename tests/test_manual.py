"""The manual ships everywhere, the README stands alone, and the Workday scope is stated."""
import re
import sys
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/orgchart'
sys.path.insert(0, str(ROOT / 'scripts'))
import build_desktop_zip  # noqa: E402
import build_plugin_zip  # noqa: E402

SECTIONS = ('Quick start', 'Giving Claude your people', 'Choosing a layout', 'Statuses and the legend',
            'at-a-glance page', 'Adding, changing and removing', 'Proposed roles', 'Dotted lines',
            'Current vs planned', 'Themes and branding', 'Updating a deck', 'Large organizations',
            'Privacy', 'Troubleshooting', 'will check with you')


class ManualTest(unittest.TestCase):
    def test_manual_covers_every_topic(self):
        text = (SKILL / 'references/manual.md').read_text()
        for section in SECTIONS:
            self.assertIn(section, text)
        self.assertNotIn('—', text)

    def test_manual_ships_in_both_zips(self):
        self.assertIn('skills/orgchart/references/manual.md', ZipFile(build_plugin_zip.build()).namelist())
        self.assertIn('orgchart/references/manual.md', ZipFile(build_desktop_zip.build()).namelist())

    def test_docs_manual_points_to_shipped_copy(self):
        self.assertIn('skills/orgchart/references/manual.md', (ROOT / 'docs/MANUAL.md').read_text())

    def test_readme_links_resolve_inside_the_plugin_zip(self):
        names = set(ZipFile(build_plugin_zip.build()).namelist())
        text = (ROOT / 'README.md').read_text()
        for target in re.findall(r'\]\(([^)#]+)\)', text):
            if target.startswith('http'):
                continue
            self.assertIn(target, names, f'README links to {target}, which the plugin zip lacks')

    def test_workday_scope_is_in_the_first_lines_users_see(self):
        for path in (SKILL / 'SKILL.md', SKILL / 'references/overview.md', ROOT / 'README.md'):
            first = '\n'.join(path.read_text().splitlines()[:25]).lower()
            self.assertIn('workday', first, path)
            self.assertIn('own ', first, path)
        readme = (ROOT / 'README.md').read_text()
        self.assertLess(readme.index('your own reporting line'), readme.index('## What you need'))

    def test_bare_command_opens_a_menu(self):
        text = (SKILL / 'SKILL.md').read_text()
        self.assertIn('What would you like to do?', text)
        for word in ('dotted', 'current vs planned', 'Change the look', 'Update a deck'):
            self.assertIn(word, text)

    def test_features_are_linked_from_skill(self):
        text = (SKILL / 'SKILL.md').read_text()
        for ref in ('references/editing.md', 'references/themes.md', 'references/manual.md', '--at-a-glance'):
            self.assertIn(ref, text)


if __name__ == '__main__':
    unittest.main()
