"""Regressions found by the synthetic drilldown canary."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/orgchart/scripts'))
import org_chart_geometry as geometry


def canary():
    people = []

    def add(manager, function, title='Role'):
        i = len(people)
        people.append({'id': f'p{i}', 'name': f'Person Delta {i}', 'title': title,
                       'manager_id': manager, 'function': function, 'kind': 'person'})
        return f'p{i}'
    root = add(None, 'Leadership', 'Chief')
    for function, size in (('Engineering', 70), ('Finance', 25)):
        head = add(root, function, 'Director')
        remaining = size - 1
        while remaining:
            manager = add(head, function, 'Manager')
            remaining -= 1
            for _ in range(3):
                if not remaining:
                    break
                lead = add(manager, function, 'Team lead')
                remaining -= 1
                for _ in range(2):
                    if not remaining:
                        break
                    add(lead, function)
                    remaining -= 1
    return {'title': 'Synthetic', 'people': people}


class DrilldownPolishTest(unittest.TestCase):
    def setUp(self):
        self.result = geometry.layout(canary(), 'enterprise_overview')

    def test_no_stray_single_card_overview_pages(self):
        for page in self.result['pages']:
            if page['section'] == 'function-overview':
                cards = [e for e in page['elements'] if e.get('collision_class') == 'card']
                self.assertGreater(len(cards), 2, page['title'])

    def test_hints_skip_context_and_overview_cards(self):
        for page in self.result['pages']:
            for card in page['elements']:
                hint = card.get('data', {}).get('continuation_hint')
                if hint:
                    self.assertFalse(card['data'].get('context'))
                    self.assertFalse(page['section'].endswith('overview'))

    def test_sub_leader_cards_do_not_repeat_their_own_name_as_lead(self):
        for page in self.result['pages']:
            if page['section'] == 'function-overview':
                for card in page['elements']:
                    self.assertFalse(card['data'].get('lead'))

    def test_every_sub_leader_has_a_reporting_line(self):
        for page in self.result['pages']:
            if page['section'] == 'function-overview':
                cards = [e for e in page['elements'] if e.get('collision_class') == 'card']
                self.assertEqual(len(page['connectors']), len(cards) - 1, page['title'])


if __name__ == '__main__':
    unittest.main()
