import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/orgchart/scripts'))
import org_chart_geometry as geometry


def roster(kind):
    rng = random.Random(14)
    people = []
    greek = ('Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta', 'Eta')
    def add(parent, function):
        i = len(people)
        people.append({'id': f'p{i:03}', 'name': f'Person {greek[i % len(greek)]} {i}',
                       'title': 'Role', 'manager_id': parent, 'function': function,
                       'status': ('filled', 'open', 'planned', 'resigned')[i % 4]})
        return people[-1]['id']
    root = add(None, 'F0')
    if kind == 'wide':
        for i in range(12):
            manager = add(root, f'F{i % 4}')
            for _ in range(rng.randrange(5)):
                add(manager, f'F{i % 4}')
    else:
        target = 60 if kind == 'deep60' else 200
        level = [root]
        depth = 1
        while len(people) < target:
            following = []
            for manager in level:
                count = min(rng.randint(3, 4), target - len(people))
                for _ in range(count):
                    following.append(add(manager, f'F{depth % 4}'))
            level = following
            depth += 1
    return {'title': 'Synthetic chart', 'people': people}


class ScaleTests(unittest.TestCase):
    def test_scale_layouts(self):
        for kind in ('wide', 'deep60', 'limit200'):
            data = roster(kind)
            for mode in geometry.MODES:
                with self.subTest(roster=kind, mode=mode):
                    result = geometry.layout(data, mode)
                    self.assertTrue(geometry.validate_layout(result)['valid'])
                    self.assertLessEqual(result['page_count'], 30)
                    if kind == 'wide' and mode == 'compact_hierarchy':
                        self.assertLessEqual(result['page_count'], 5)
                    if kind == 'deep60' and mode == 'compact_hierarchy':
                        self.assertLessEqual(result['page_count'], 4)
                    names = [item['stable_name'] for page in result['pages'] for key in ('elements', 'connectors', 'alignment_groups') for item in page[key]]
                    self.assertEqual(len(names), len(set(names)))

    def test_wide_compact_reporting_pairs(self):
        data = roster("wide")
        result = geometry.layout(data, "compact_hierarchy")
        page_nodes = [{element["node_id"] for element in page["elements"] if "node_id" in element} for page in result["pages"]]
        for person in data["people"]:
            if person["manager_id"]:
                self.assertTrue(any({person["id"], person["manager_id"]} <= nodes for nodes in page_nodes), person["id"])

    def test_wide_recommendation(self):
        self.assertIn(geometry.recommend(roster('wide'))['recommended_mode'], ('compact_hierarchy',))

if __name__ == '__main__':
    unittest.main()
