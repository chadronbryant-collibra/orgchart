import json
import sys
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_desktop_zip  # noqa: E402
import build_plugin_zip  # noqa: E402


class PackagingTest(unittest.TestCase):
    def test_versions_agree(self):
        plugin = json.loads((ROOT / '.claude-plugin/plugin.json').read_text())
        market = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text())
        skill = (ROOT / 'skills/orgchart/SKILL.md').read_text()
        entry = next(p for p in market['plugins'] if p['name'] == 'orgchart')
        self.assertEqual(plugin['version'], entry['version'])
        self.assertIn(f'version: "{plugin["version"]}"', skill)
        self.assertIn(f'## {plugin["version"]}', (ROOT / 'CHANGELOG.md').read_text())

    def test_plugin_zip_layout(self):
        names = ZipFile(build_plugin_zip.build()).namelist()
        self.assertIn('.claude-plugin/plugin.json', names)
        self.assertIn('skills/orgchart/SKILL.md', names)
        self.assertIn('README.md', names)
        self.assertIn('CHANGELOG.md', names)
        allowed = ('.claude-plugin/', 'skills/orgchart/', 'README.md', 'CHANGELOG.md')
        self.assertTrue(all(n.startswith(allowed) for n in names), names)
        self.assertFalse(any('__pycache__' in n or n.endswith('.pyc') for n in names))

    def test_desktop_zip_layout(self):
        names = ZipFile(build_desktop_zip.build()).namelist()
        self.assertIn('orgchart/SKILL.md', names)
        self.assertTrue(all(n.startswith('orgchart/') for n in names))


if __name__ == '__main__':
    unittest.main()
