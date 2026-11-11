"""Team (drilldown) pages for the Overview + team pages layout.

"Children under their parent" is checked as: the parent's center is within
half a card width of the midpoint of its on-page reports, and those reports sit
in the row directly below. When a branch is split, its reports continue on a
later page under a grey context card for the parent, and the same rule applies
there.
"""
import sys
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/orgchart/scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
import org_chart_geometry as geometry
import slides_requests
from test_scale import roster


def person(pid, manager, function, title='Role'):
    return {'id': pid, 'name': f'Person {pid}', 'title': title, 'manager_id': manager, 'function': function}


def wide60():
    """One leader with 60 direct reports in one team."""
    people = [person('lead', None, 'Operations', 'Head of Operations')]
    people += [person(f'r{i:02}', 'lead', 'Operations') for i in range(60)]
    return {'title': 'Synthetic wide team', 'people': people}


def deep60():
    """Sixty people, six levels below the top leader, across two teams."""
    people = [person('d0', None, 'Engineering', 'Head of Engineering')]
    for depth in range(1, 7):
        people.append(person(f'd{depth}', f'd{depth - 1}', 'Engineering', 'Manager'))
    index = 0
    while len(people) < 60:
        manager = f'd{index % 7}'
        people.append(person(f's{index:02}', manager, 'Data' if index % 4 == 0 else 'Engineering'))
        index += 1
    return {'title': 'Synthetic deep org', 'people': people}


def branchy():
    """Three teams with managers inside and outside each team."""
    people = [person('ceo', None, 'Executive', 'Chief Executive')]
    for b in range(3):
        head = f'h{b}'
        people.append(person(head, 'ceo', f'Team {b}', 'Director'))
        for m in range(3):
            manager = f'h{b}m{m}'
            people.append(person(manager, head, f'Team {b}', 'Manager'))
            for r in range(3 + m):
                people.append(person(f'{manager}r{r}', manager, f'Team {b}'))
    return {'title': 'Synthetic branches', 'people': people}


ROSTERS = {
    'wide60': wide60,
    'deep60': deep60,
    'branchy': branchy,
    'scale-wide': lambda: roster('wide'),
    'scale-deep60': lambda: roster('deep60'),
    'scale-limit200': lambda: roster('limit200'),
}


def team_pages(result):
    return [page for page in result['pages'] if page['section'].startswith('enterprise-') and page['section'] != 'enterprise-overview']


def cards(page):
    return [element for element in page['elements'] if element.get('node_id')]


def center(card):
    return card['box']['x'] + card['box']['w'] / 2


class TeamPageTests(unittest.TestCase):
    def layouts(self):
        for name, build in ROSTERS.items():
            data = build()
            yield name, data, geometry.layout(data, 'enterprise_overview')

    def test_valid_and_bounded(self):
        for name, _, result in self.layouts():
            with self.subTest(roster=name):
                self.assertTrue(geometry.validate_layout(result)['valid'])
                self.assertLessEqual(result['page_count'], 30)

    def test_every_same_page_reporting_edge_has_a_connector(self):
        for name, data, result in self.layouts():
            by_id = {p['id']: p for p in data['people']}
            for page in team_pages(result):
                with self.subTest(roster=name, page=page['id']):
                    by_node = {card['node_id']: card for card in cards(page)}
                    drawn = {(c['from'], c['to']) for c in page['connectors'] if c['type'] == 'direct_report'}
                    expected = set()
                    for card in cards(page):
                        if card['data']['context']:
                            continue
                        manager = by_id[card['node_id']]['manager_id']
                        if manager in by_node:
                            expected.add((by_node[manager]['stable_name'], card['stable_name']))
                    self.assertEqual(drawn, expected)

    def test_no_overlaps_and_readable_cards(self):
        for name, _, result in self.layouts():
            for page in team_pages(result):
                with self.subTest(roster=name, page=page['id']):
                    boxes = [card['box'] for card in cards(page)]
                    for i, a in enumerate(boxes):
                        for b in boxes[i + 1:]:
                            self.assertFalse(geometry._intersects(a, b))
                    self.assertGreaterEqual(min(box['w'] for box in boxes), 1.4)
                    self.assertGreaterEqual(min(box['h'] for box in boxes), 0.48)
                    self.assertLessEqual(len({round(box['y'], 3) for box in boxes}), geometry.TEAM_PAGE_ROWS)

    def test_children_sit_under_their_parent(self):
        for name, data, result in self.layouts():
            by_id = {p['id']: p for p in data['people']}
            for page in team_pages(result):
                with self.subTest(roster=name, page=page['id']):
                    by_node = {card['node_id']: card for card in cards(page)}
                    reports = defaultdict(list)
                    for card in cards(page):
                        manager = by_id[card['node_id']]['manager_id']
                        if not card['data']['context'] and manager in by_node:
                            reports[manager].append(card)
                    for manager, children in reports.items():
                        parent = by_node[manager]
                        width = parent['box']['w']
                        midpoint = (min(map(center, children)) + max(map(center, children))) / 2
                        self.assertLessEqual(abs(center(parent) - midpoint), width / 2 + 1e-6)
                        row_below = parent['box']['y'] + parent['box']['h']
                        for child in children:
                            self.assertGreater(child['box']['y'], row_below)
                            self.assertEqual(round(child['box']['y'], 3), round(children[0]['box']['y'], 3))

    def test_off_page_managers_appear_as_context_cards(self):
        for name, data, result in self.layouts():
            by_id = {p['id']: p for p in data['people']}
            placed = defaultdict(list)
            for page in team_pages(result):
                by_node = {card['node_id']: card for card in cards(page)}
                for card in cards(page):
                    if card['data']['context']:
                        continue
                    placed[card['node_id']].append(page['id'])
                    manager = by_id[card['node_id']]['manager_id']
                    if manager:
                        with self.subTest(roster=name, page=page['id'], person=card['node_id']):
                            self.assertIn(manager, by_node)
                for card in cards(page):
                    if card['data']['context']:
                        with self.subTest(roster=name, page=page['id'], context=card['node_id']):
                            self.assertTrue(any(c['from'] == card['stable_name'] for c in page['connectors']))
            with self.subTest(roster=name):
                omitted = {p['id'] for p in data['people'] if p['manager_id'] is None and sum(q['function'] == p['function'] for q in data['people']) == 1} if sum(p['manager_id'] is None for p in data['people']) == 1 else set()
                self.assertEqual(set(placed), set(by_id) - omitted)
                self.assertTrue(all(len(pages) == 1 for pages in placed.values()))

    def test_wide_team_repeats_its_leader(self):
        result = geometry.layout(wide60(), 'enterprise_overview')
        pages = team_pages(result)
        self.assertLessEqual(len(pages), 9)
        first = {card['node_id']: card for card in cards(pages[0])}
        self.assertFalse(first['lead']['data']['context'])
        for page in pages[1:]:
            context = [card['node_id'] for card in cards(page) if card['data']['context']]
            self.assertEqual(context, ['lead'])
            self.assertTrue(page['title'].endswith('continued'))

    def test_deep_branch_continues_under_context(self):
        result = geometry.layout(deep60(), 'enterprise_overview')
        located = {}
        for page in team_pages(result):
            for card in cards(page):
                if not card['data']['context']:
                    located[card['node_id']] = page
        deepest = located['d6']
        self.assertIn('d5', {card['node_id'] for card in cards(deepest)})
        data_page = located['s00']
        context = {card['node_id'] for card in cards(data_page) if card['data']['context']}
        self.assertIn('d0', context)

    def test_overview_root_summaries_and_singular(self):
        data = {'title': 'Synthetic', 'people': [person('ceo', None, 'Leadership'),
                person('head', 'ceo', 'Product'), person('other', 'ceo', 'Sales')]}
        result = geometry.layout(data, 'enterprise_overview')
        overview = result['pages'][0]
        self.assertEqual([c['node_id'] for c in cards(overview)], ['ceo'])
        summaries = [e for e in overview['elements'] if e['type'] == 'group_summary_card']
        self.assertEqual(len(summaries), 2)
        self.assertTrue(all(e['data']['title'].startswith('1 position ·') for e in summaries))
        self.assertEqual(len(overview['connectors']), 2)
        self.assertNotIn('Leadership', [p['title'] for p in team_pages(result)])
        self.assertTrue(geometry.validate_layout(result)['valid'])

    def test_five_function_overview_has_five_safe_connectors(self):
        data = {'title': 'Synthetic', 'people': [person('ceo', None, 'Leadership')]}
        for i in range(5):
            data['people'].append(person(f'h{i}', 'ceo', f'Team {i}'))
        for i in range(38):
            data['people'].append(person(f'r{i}', 'h0', 'Team 0'))
        result = geometry.layout(data, 'enterprise_overview')
        overview = result['pages'][0]
        self.assertEqual(len(data['people']), 44)
        self.assertEqual(len(overview['connectors']), 5)
        self.assertTrue(geometry.validate_layout(result)['valid'])

    def test_wrapped_overview_keeps_safe_first_row_connectors(self):
        data = {'title': 'Synthetic', 'people': [person('ceo', None, 'Leadership')]}
        data['people'] += [person(f'h{i}', 'ceo', f'Team {i}') for i in range(8)]
        result = geometry.layout(data, 'enterprise_overview')
        overview = result['pages'][0]
        first_row = {e['stable_name'] for e in overview['elements']
                     if e['type'] == 'group_summary_card' and e['box']['y'] == min(
                         x['box']['y'] for x in overview['elements'] if x['type'] == 'group_summary_card')}
        self.assertEqual(len(first_row), 6)
        self.assertTrue(first_row <= {c['to'] for c in overview['connectors']})
        for connector in overview['connectors']:
            self.assertFalse(geometry._connector_hits_non_endpoint_card(connector, overview['elements']))
            self.assertFalse(geometry._google_straight_connector_hits_non_endpoint_card(connector, overview['elements']))
        self.assertTrue(geometry.validate_layout(result)['valid'])

    def test_multiple_roots_keep_function_pages(self):
        data = {'title': 'Synthetic', 'people': [person('a', None, 'A'), person('b', None, 'B')]}
        result = geometry.layout(data, 'enterprise_overview')
        self.assertFalse(cards(result['pages'][0]))
        self.assertEqual([page['title'] for page in team_pages(result)], ['A', 'B'])

    def test_continuation_hint_is_rendered(self):
        result = geometry.layout(wide60(), 'enterprise_overview')
        first = team_pages(result)[0]
        lead = next(c for c in cards(first) if c['node_id'] == 'lead')
        self.assertEqual(lead['data']['continuation_hint'], f"Team continues on page {team_pages(result)[1]['index']}")
        self.assertIn(lead['data']['continuation_hint'], slides_requests.card_text(lead))

    def test_slides_requests_render_context_cards_and_lines(self):
        result = geometry.layout(wide60(), 'enterprise_overview')
        compiled = slides_requests.compile_requests(result, 'neutral')
        expected_lines = sum(len(page['connectors']) for page in result['pages'])
        self.assertEqual(compiled['summary']['connectors'], expected_lines)
        texts = [r['insertText']['text'] for chunk in compiled['presentation_requests'] for r in chunk if 'insertText' in r and 'text' in r['insertText']]
        self.assertTrue(any(text.startswith('Person lead (context)') for text in texts))


if __name__ == '__main__':
    unittest.main()
