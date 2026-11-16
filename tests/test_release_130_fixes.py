"""Regression tests for 1.3.0 layout fixes. Synthetic data only."""
import random
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/orgchart/scripts"))
import org_chart_geometry as geometry  # noqa: E402


def person(pid, manager, name=None, title="Engineer", function="Ops", **extra):
    p = {"id": pid, "name": name or f"Person {pid}", "title": title, "manager_id": manager, "function": function}
    p.update(extra)
    return p


def random_roster(seed):
    rng = random.Random(seed)
    people = [person("p0", None, title="Head")]
    for i in range(1, 80):
        window = people[max(0, len(people) - rng.choice([3, 10, 40])):]
        people.append(person(f"p{i}", rng.choice(window)["id"]))
    return {"title": "Synthetic", "people": people}


class ContinuationLabelTests(unittest.TestCase):
    def test_repeated_head_points_forward_to_a_page_with_its_reports(self):
        checked = 0
        for seed in range(40):
            data = random_roster(seed)
            result = geometry.layout(data, "compact_hierarchy")
            reports = {}
            for p in data["people"]:
                reports.setdefault(p["manager_id"], set()).add(p["id"])
            pages_of, copies = {}, {}
            for page in result["pages"]:
                for e in page["elements"]:
                    if e.get("node_id") and not e["data"].get("context"):
                        pages_of.setdefault(e["node_id"], set()).add(page["index"])
                        copies[e["node_id"]] = copies.get(e["node_id"], 0) + 1
            for page in result["pages"]:
                for e in page["elements"]:
                    hint = e.get("data", {}).get("continuation_hint")
                    if not hint or copies.get(e["node_id"], 0) < 2:
                        continue
                    checked += 1
                    target = int(re.findall(r"\d+", hint)[0])
                    self.assertGreater(target, page["index"], (seed, hint))
                    self.assertTrue(any(target in pages_of.get(r, ()) for r in reports[e["node_id"]]), (seed, hint))
        self.assertGreater(checked, 0, "fixture no longer repeats a head across pages")


class FourLineCardTests(unittest.TestCase):
    def test_wrapped_name_plus_contingent_marker_fits_in_simple_tree(self):
        people = [person("h", None, title="VP Engineering")]
        people += [person(f"k{i}", "h", name="Alexandria Montgomery-Fitzgerald III",
                          title="Senior Staff Software Engineer", worker_type="contingent") for i in range(6)]
        result = geometry.layout({"title": "T", "people": people}, "compact_hierarchy")
        for page in result["pages"]:
            for e in page["elements"]:
                if e.get("node_id") and e.get("box"):
                    needed = geometry._text_height_needed(e, e["box"]["w"])
                    self.assertLessEqual(needed, e["box"]["h"] * 72 + 0.01, e["node_id"])


class LeadershipRootsTests(unittest.TestCase):
    def roots(self, n):
        return {"title": "T", "people": [person(f"r{i}", None, title="Director") for i in range(n)]
                + [person("x", "r0")]}

    def test_many_roots_warn_and_recommend_simple_tree(self):
        data = self.roots(11)
        rec = geometry.recommend(data)
        self.assertEqual(rec["recommended_mode"], "compact_hierarchy")
        self.assertTrue(any("Simple tree" in w for w in rec["warnings"]))
        warnings = geometry.layout(data, "leadership_bands")["validation"]["warnings"]
        self.assertTrue(any("Simple tree" in w and "11" in w for w in warnings))

    def test_six_roots_do_not_warn(self):
        data = self.roots(6)
        self.assertEqual(geometry.recommend(data)["recommended_mode"], "leadership_bands")
        self.assertFalse(any("Simple tree" in w for w in geometry.layout(data, "leadership_bands")["validation"]["warnings"]))


if __name__ == "__main__":
    unittest.main()
