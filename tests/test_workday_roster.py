"""Synthetic-fixture tests for the Workday roster assembler. No People data."""
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "orgchart" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import workday_roster as mod  # noqa: E402
import org_chart_geometry as geometry  # noqa: E402


def row(nid, mgr="", **kw):
    base = {"node_id": nid, "display_name": f"Person {nid}", "title": "T", "manager_node_id": mgr,
            "function": "F", "status": "filled", "worker_type": "employee",
            "node_type": "person", "location": "Demo"}
    base.update(kw)
    return base


def unit_page(unit, rows, last=False, status="active", codes="more_pages"):
    return {"result": {"outcome": "ok", "unit": str(unit), "unit_status": status, "completeness": "partial",
            "reason_codes": codes, "returned_count": str(len(rows)),
            "has_more": "false" if last else "true",
            "next_unit": "" if last else str(unit + 1), "next_offset": "" if last else "0", "rows": rows}}


class WorkdayRosterBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, obj):
        p = self.dir / name
        p.write_text(json.dumps(obj), encoding="utf-8")
        return str(p)

    def run_asm(self, pages, *extra):
        out, rep = self.dir / "roster.json", self.dir / "report.json"
        if rep.exists():
            rep.unlink()
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = mod.main(["assemble", *pages, "--output", str(out), "--report", str(rep), *extra])
        return code, out, json.loads(rep.read_text()) if rep.exists() else None

    def live_like(self, skip=None):
        pages = [unit_page(0, [row("m1", "head", function="Org A (Head)"), row("m2", "head", function="Org A (Head)")]),
                 unit_page(1, [row("a1", "m1", function="Team One (Mgr One)")]),
                 unit_page(2, [], status="inactive"),
                 unit_page(3, [row("b1", "m2", display_name="Person b1 [C]", function="Team Three (Mgr Two)")],
                           last=True, codes="depth_limit")]
        return [self.write(f"page-{i:03d}.json", pg) for i, pg in enumerate(pages) if i != skip]


class AssemblerTests(WorkdayRosterBase):
    def test_complete_roster_fields_and_dedupe(self):
        p1 = self.write("page-001.json", {"outcome": "ok", "completeness": "partial", "reason_codes": ["more_pages"],
                                          "has_more": "true", "rows": [row("a"), row("b", "a")]})
        p2 = self.write("page-002.json", {"outcome": "ok", "completeness": "complete", "has_more": "false",
                                          "rows": [row("c", "a"), row("b", "a")]})
        code, out, rep = self.run_asm([p1, p2])
        self.assertEqual(code, 0)
        self.assertEqual(rep["verdict"], "complete")
        self.assertEqual((rep["rows_out"], rep["duplicates_removed"], rep["roots"]), (3, 1, 1))
        rows = json.loads(out.read_text())
        self.assertEqual(list(rows[0]), mod.FIELDS)
        self.assertEqual([r["sort_order"] for r in rows], ["1", "2", "3"])

    def test_fields_are_known_to_the_normalizer(self):
        import normalize_org_chart as norm
        self.assertTrue(set(mod.FIELDS) <= norm.FLAT_KNOWN)

    def test_unfinished_pull_is_partial(self):
        p = self.write("page-001.json", {"outcome": "ok", "has_more": "true", "rows": [row("a")]})
        _, _, rep = self.run_asm([p])
        self.assertEqual(rep["verdict"], "partial")
        self.assertIn("pull_not_finished", rep["partial_reasons"])

    def test_reason_codes_and_outcomes_make_partial(self):
        p1 = self.write("page-001.json", {"outcome": "ok", "completeness": {"status": "partial",
                        "reason_codes": ["depth_limit"]}, "has_more": "false", "rows": [row("a")]})
        p2 = self.write("page-002.json", {"outcome": "row_cap_reached", "has_more": "false", "rows": []})
        _, _, rep = self.run_asm([p1, p2])
        self.assertEqual(rep["verdict"], "partial")
        self.assertIn("depth_limit", rep["partial_reasons"])
        self.assertIn("outcome:row_cap_reached", rep["partial_reasons"])

    def test_dangling_manager_stops_until_roots_chosen(self):
        p = self.write("page-001.json", {"has_more": "false", "rows": [row("a", "hidden"), row("b", "a")]})
        code, out, rep = self.run_asm([p])
        self.assertEqual(code, 3)
        self.assertFalse(out.exists())
        self.assertEqual(rep["dangling_manager_links"], 1)
        code, out, rep = self.run_asm([p], "--dangling", "roots")
        self.assertEqual((code, rep["roots"], rep["dangling_made_roots"]), (0, 1, 1))

    def test_cycle_is_refused_and_report_has_counts_only(self):
        p = self.write("page-001.json", {"has_more": "false", "rows": [row("a", "b"), row("b", "a")]})
        code, out, rep = self.run_asm([p])
        self.assertEqual((code, rep["cycles"]), (3, 2))
        self.assertFalse(out.exists())
        self.assertNotIn("Person", json.dumps(rep))

    def test_never_overwrites(self):
        p = self.write("page-001.json", {"has_more": "false", "rows": [row("a")]})
        self.assertEqual(self.run_asm([p])[0], 0)
        self.assertEqual(mod.main(["assemble", p, "--output", str(self.dir / "roster.json"),
                                   "--report", str(self.dir / "r2.json")]), 2)

    def test_plan_thresholds(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            mod.main(["plan", "--sub-orgs", "13", "--depth", "2"])
        out = json.loads(buf.getvalue())
        self.assertEqual((out["min_pages"], out["advice"], out["workday_calls"]), (14, "heads_up", 3 + 13 * 5))

    def test_envelope_unwrapped_and_string_codes_split(self):
        page = {"result": {"outcome": "ok", "completeness": "partial", "reason_codes": "more_pages,depth_limit",
                           "has_more": "false", "unit_status": "active", "rows": [row("a", "head"), row("b", "head")]}}
        p = self.write("page-001.json", page)
        code, _, rep = self.run_asm([p])
        self.assertEqual((code, rep["rows_out"], rep["distinct_missing_managers"]), (3, 2, 1))
        self.assertEqual(rep["reason_codes"], {"more_pages": 1, "depth_limit": 1})
        self.assertEqual(rep["partial_reasons"], ["depth_limit"])

    def test_head_added_and_cleanups(self):
        files = self.live_like()
        code, _, rep = self.run_asm(files)
        self.assertEqual((code, rep["distinct_missing_managers"], rep["inactive_units_flagged"]), (3, 1, 1))
        code, out, rep = self.run_asm(files, "--add-head", "Head Person", "--head-title", "Head", "--clean-function")
        self.assertEqual(code, 0)
        self.assertTrue(rep["head_row_added"])
        self.assertEqual((rep["roots"], rep["rows_out"]), (1, 5))
        self.assertEqual(rep["partial_reasons"], ["depth_limit"])
        self.assertEqual((rep["contingent_marker_fixed"], rep["page_gaps"]), (1, 0))
        data = json.loads(out.read_text())
        rows = {r["node_id"]: r for r in data}
        self.assertEqual(rows["b1"]["worker_type"], "contingent")
        self.assertEqual(rows["b1"]["display_name"], "Person b1")
        self.assertEqual(rows["a1"]["function"], "Team One")
        self.assertEqual(data[0]["node_id"], "head")

    def test_skipped_page_is_a_gap(self):
        _, _, rep = self.run_asm(self.live_like(skip=1), "--dangling", "roots")
        self.assertGreaterEqual(rep["page_gaps"], 1)
        self.assertIn("page_gap", rep["partial_reasons"])

    def test_in_unit_offset_must_follow_rows(self):
        first = unit_page(0, [row("a")])
        first["result"].update(next_unit="0", next_offset="5")
        second = unit_page(0, [row("b")], last=True, codes="")
        _, _, rep = self.run_asm([self.write("page-001.json", first), self.write("page-002.json", second)])
        self.assertGreaterEqual(rep["page_gaps"], 1)

    def test_clean_function_helper(self):
        self.assertEqual(mod.strip_trailing_parens("Total Rewards (Name (Inherited))"), "Total Rewards")
        self.assertEqual(mod.strip_trailing_parens("Plain label"), "Plain label")
        self.assertEqual(mod.strip_trailing_parens("(Only)"), "(Only)")

    def test_add_head_refuses_unless_exactly_one_missing(self):
        p = self.write("page-001.json", {"has_more": "false", "rows": [row("a", "h1"), row("b", "h2")]})
        code, out, _ = self.run_asm([p], "--add-head", "X")
        self.assertEqual(code, 3)
        self.assertFalse(out.exists())

    def test_size_advice_tiers(self):
        self.assertEqual((mod.size_advice(200), mod.size_advice(201)), ("single_chart", "staged"))
        self.assertEqual((mod.size_advice(1000), mod.size_advice(1001)), ("staged", "split_decks"))


class EndToEndTests(WorkdayRosterBase):
    def test_assembled_roster_normalizes_and_lays_out(self):
        code, out, rep = self.run_asm(self.live_like(), "--add-head", "Head Person", "--head-title", "Head",
                                      "--clean-function")
        self.assertEqual(code, 0, rep)
        render, receipt = self.dir / "render.json", self.dir / "receipt.json"
        result = subprocess.run([sys.executable, str(SCRIPTS / "normalize_org_chart.py"), "normalize", str(out),
                                 "--output", str(render), "--receipt", str(receipt)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(render.read_text())
        layout = geometry.layout(data)
        self.assertTrue(geometry.validate_layout(layout)["valid"])


if __name__ == "__main__":
    unittest.main()
