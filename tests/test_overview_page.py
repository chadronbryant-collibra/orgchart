"""Overview page polish: singular counts and a vertically centered card grid."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/orgchart/scripts'))
import org_chart_geometry as geometry


def person(pid, manager, function, kind='person'):
    return {'id': pid, 'name': f'Person {pid}', 'title': 'Role', 'manager_id': manager, 'function': function, 'kind': kind}


def roster():
    people = [person('lead', None, 'Leadership')]
    people += [person('b1', 'lead', 'Business')]
    people += [person('p1', 'lead', 'Product'), person('p2', 'p1', 'Product'), person('p3', 'p1', 'Product', 'open_role')]
    return {'title': 'Synthetic overview', 'people': people}


class OverviewPageTest(unittest.TestCase):
    def setUp(self):
        self.result = geometry.layout(roster(), 'enterprise_overview')
        self.overview = self.result['pages'][0]
        self.cards = [e for e in self.overview['elements'] if e['type'] == 'group_summary_card']

    def test_counts_use_singular_for_one(self):
        subtitles = {card['data']['name']: card['data']['title'] for card in self.cards}
        self.assertTrue(subtitles['Business'].startswith('1 position ·'), subtitles['Business'])
        self.assertTrue(subtitles['Product'].startswith('3 positions ·'), subtitles['Product'])

    def test_card_grid_is_vertically_centered(self):
        content = self.overview['content_bounds']
        block = [e for e in self.overview['elements'] if e['type'] in ('group_summary_card', 'person_card')]
        top = min(card['box']['y'] for card in block)
        bottom = max(card['box']['y'] + card['box']['h'] for card in block)
        above = top - content['y']
        below = content['y'] + content['h'] - bottom
        self.assertAlmostEqual(above, below, places=2)
        self.assertGreater(above, 0.5)

    def test_layout_stays_valid(self):
        self.assertTrue(geometry.validate_layout(self.result)['valid'])


if __name__ == '__main__':
    unittest.main()
