"""Text must stay inside cards on team pages (synthetic data only)."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/orgchart/scripts'))
import org_chart_geometry as geometry


def person(pid, manager, name, title, function='Product'):
    return {'id': pid, 'name': name, 'title': title, 'manager_id': manager, 'function': function}


def nine_report_team():
    people = [person('root', None, 'Person Alpha', 'Chief Product Officer', 'Executive'),
              person('head', 'root', 'Person Beta Product Head', 'Head of Product Management')]
    for i in range(9):
        people.append(person(f'r{i}', 'head', f'Person Gamma Report With A Long Name {i}', 'Senior Product Manager'))
    for i in range(30):  # enough depth under one report to force a continuation page
        people.append(person(f'k{i}', 'r0', f'Person Delta {i}', 'Product Analyst'))
    return {'title': 'Synthetic overflow team', 'people': people}


def team_pages(result):
    return [p for p in result['pages'] if p['section'].startswith('enterprise-') and not p['section'].endswith('overview')]


class OverflowTests(unittest.TestCase):
    def setUp(self):
        self.result = geometry.layout(nine_report_team(), 'enterprise_overview')

    def test_layout_is_valid_and_text_fits(self):
        self.assertTrue(self.result['validation']['valid'], self.result['validation']['errors'])
        for page in team_pages(self.result):
            for card in page['elements']:
                if card.get('node_id'):
                    self.assertIsNone(geometry._text_fit_problem(card), card['data']['name'])

    def test_lone_head_cards_get_full_width(self):
        found = False
        for page in team_pages(self.result):
            rows = {}
            for card in page['elements']:
                if card.get('node_id'):
                    rows.setdefault(round(card['box']['y'], 3), []).append(card)
            widest = max(len(r) for r in rows.values())
            for row in rows.values():
                if len(row) == 1 and widest > 1:
                    found = True
                    self.assertAlmostEqual(row[0]['box']['w'], 2.0, places=3)
        self.assertTrue(found, 'expected a team page with a lone head above a wide row')

    def test_continuation_hint_present_and_fits(self):
        hints = [c['data']['continuation_hint'] for p in team_pages(self.result) for c in p['elements']
                 if c.get('data', {}).get('continuation_hint')]
        self.assertTrue(hints)

    def test_checker_flags_overflowing_card(self):
        bad = copy.deepcopy(self.result)
        card = next(c for p in team_pages(bad) for c in p['elements'] if c.get('node_id'))
        card['box']['w'] = 0.6
        report = geometry.validate_layout(bad)
        self.assertFalse(report['valid'])
        self.assertTrue(any('does not fit' in e for e in report['errors']))

    def test_layout_raises_clear_error_when_text_cannot_fit(self):
        data = nine_report_team()
        data['people'][2]['name'] = 'X' * 400
        with self.assertRaises(geometry.GeometryError) as ctx:
            geometry.layout(data, 'enterprise_overview')
        self.assertIn('does not fit', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
