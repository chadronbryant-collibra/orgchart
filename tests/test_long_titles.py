"""Long job titles on a wide leadership page must never make layout fail (synthetic data only)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/orgchart/scripts'
sys.path.insert(0, str(SCRIPTS))
import normalize_org_chart as normalizer
import org_chart_geometry as geometry


def rows():
    out = [{'node_id': 'head', 'display_name': 'Person Alpha', 'title': 'Chief Example Officer', 'manager_node_id': '', 'function': 'Example Org'}]
    titles = ['Senior Manager, Example Infrastructure', 'Vice President, Communications & Experience',
              'Senior Director, Example Operations', 'Director, Total Example Rewards', 'Head of Equity and Impact']
    for i in range(11):
        out.append({'node_id': f'lead{i}', 'display_name': f'Person Beta {i}', 'title': titles[i % len(titles)],
                    'manager_node_id': 'head', 'function': 'Example Org', 'location': 'Office - XX Example City'})
        for j in range(3 if i % 2 else 2):
            out.append({'node_id': f'm{i}-{j}', 'display_name': f'Person Gamma {i}{j}', 'title': 'Specialist',
                        'manager_node_id': f'lead{i}', 'function': f'Team {i}'})
    return out


class LongTitleTests(unittest.TestCase):
    def test_layout_succeeds_and_every_card_fits(self):
        payload, _ = normalizer.normalize_source(rows(), source_kind='flat_json')
        result = geometry.layout(payload)
        self.assertTrue(result['validation']['valid'])
        self.assertGreaterEqual(result['page_count'], 2)


if __name__ == '__main__':
    unittest.main()
