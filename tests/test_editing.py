import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "orgchart"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))
import apply_org_chart_scenario as scenario  # noqa: E402
import normalize_org_chart as normalizer  # noqa: E402
import preview_org_chart as preview  # noqa: E402
import org_chart_geometry as geometry  # noqa: E402

EDITS = SKILL / "examples" / "edits"
ROSTER = SKILL / "examples" / "synthetic-roster.csv"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / args[0]), *args[1:]], capture_output=True, text=True)


class EditBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.roster = self.dir / "roster.json"
        result = run("normalize_org_chart.py", "normalize", str(ROSTER), "--output", str(self.roster),
                     "--receipt", str(self.dir / "receipt.json"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.render = json.loads(self.roster.read_text())

    def tearDown(self):
        self.tmp.cleanup()

    def apply(self, rows):
        return scenario.apply_edits(copy.deepcopy(self.render), rows)

    def fails(self, rows, *words):
        with self.assertRaises(scenario.ScenarioError) as ctx:
            self.apply(rows)
        message = str(ctx.exception)
        for word in words:
            self.assertIn(word, message)
        self.assertNotIn("Traceback", message)
        return message


class EditOperations(EditBase):
    def test_add_proposed_role_has_status_note_and_zero_impact(self):
        planned, summary = self.apply([{"op": "add", "node_id": "plan-1", "title": "Director of Analytics",
                                        "manager_node_id": "demo-010", "status": "planned", "note": "Budget pending"}])
        person = {p["id"]: p for p in planned["people"]}["plan-1"]
        self.assertEqual(person["status"], "planned")
        self.assertEqual(person["headcount_impact"], 0)
        self.assertEqual(person["kind"], "open_role")
        self.assertIn("Proposed: Budget pending", person["details"][0])
        self.assertEqual(summary["headcount_before"], summary["headcount_after"])

    def test_proposed_without_note_gets_default_assumption(self):
        planned, _ = self.apply([{"op": "add", "node_id": "p", "title": "X", "manager_node_id": "demo-010", "status": "planned"}])
        self.assertIn("assumption", {p["id"]: p for p in planned["people"]}["p"]["annotation"])

    def test_add_named_filled_person_adds_headcount(self):
        _, summary = self.apply([{"op": "add", "node_id": "n", "display_name": "Person Eta 2", "title": "Analyst", "manager_node_id": "demo-030"}])
        self.assertEqual((summary["headcount_before"], summary["headcount_after"]), (7, 8))
        self.assertIn("1 added", summary["text"])
        self.assertIn("headcount 7 -> 8", summary["text"])

    def test_move_and_modify_and_baseline_untouched(self):
        before = copy.deepcopy(self.render)
        planned, summary = self.apply([
            {"op": "move", "node_id": "demo-011", "manager_node_id": "demo-020"},
            {"op": "modify", "node_id": "demo-021", "title": "Senior Director"},
        ])
        by = {p["id"]: p for p in planned["people"]}
        self.assertEqual(by["demo-011"]["manager_id"], "demo-020")
        self.assertEqual(by["demo-011"]["change"], "moved")
        self.assertEqual(by["demo-021"]["title"], "Senior Director")
        self.assertEqual(self.render, before)
        self.assertIn("1 moved", summary["text"])
        self.assertIn("1 changed", summary["text"])

    def test_mark_open_and_propose_existing(self):
        planned, summary = self.apply([{"op": "open", "node_id": "demo-021", "note": "Backfill"},
                                       {"op": "propose", "node_id": "demo-022"}])
        by = {p["id"]: p for p in planned["people"]}
        self.assertEqual(by["demo-021"]["status"], "open")
        self.assertEqual(by["demo-021"]["name"], "Open")
        self.assertEqual(by["demo-022"]["status"], "planned")
        self.assertEqual(summary["headcount_after"], 5)  # two filled -> 0 impact

    def test_remove_leaf(self):
        planned, summary = self.apply([{"op": "remove", "node_id": "demo-012"}])
        self.assertNotIn("demo-012", {p["id"] for p in planned["people"]})
        self.assertEqual(summary["removed"], 1)
        self.assertEqual(summary["removed_positions"][0]["id"], "demo-012")

    def test_remove_manager_requires_choice_and_names_people(self):
        message = self.fails([{"op": "remove", "node_id": "demo-010"}],
                             "Person Gamma", "Product Operations Lead", "reassign", "cascade", "stop")
        self.assertNotIn("manager_id", message)

    def test_remove_stop_is_an_error_too(self):
        self.fails([{"op": "remove", "node_id": "demo-010", "reports": "stop"}], "without a manager")

    def test_remove_reassign(self):
        planned, summary = self.apply([{"op": "remove", "node_id": "demo-020", "reports": "reassign", "reassign_to_node_id": "demo-010"}])
        by = {p["id"]: p for p in planned["people"]}
        self.assertEqual(by["demo-021"]["manager_id"], "demo-010")
        self.assertEqual(by["demo-022"]["manager_id"], "demo-010")
        self.assertEqual(summary["removed"], 1)
        self.assertEqual(summary["moved"], 2)

    def test_remove_reassign_shorthand_and_bad_target(self):
        planned, _ = self.apply([{"op": "remove", "node_id": "demo-020", "reports": "reassign:demo-030"}])
        self.assertEqual({p["id"]: p for p in planned["people"]}["demo-021"]["manager_id"], "demo-030")
        self.fails([{"op": "remove", "node_id": "demo-020", "reports": "reassign", "reassign_to_node_id": "nobody"}], "take over")

    def test_remove_cascade(self):
        planned, summary = self.apply([{"op": "remove", "node_id": "demo-020", "reports": "cascade"}])
        self.assertEqual(summary["removed"], 3)
        self.assertEqual(len(planned["people"]), 5)
        self.assertEqual(summary["headcount_after"], 4)

    def test_cannot_remove_everyone(self):
        self.fails([{"op": "remove", "node_id": "demo-001", "reports": "cascade"}], "everyone")


class NegativeCases(EditBase):
    def test_unknown_ids_and_ops(self):
        self.fails([{"op": "move", "node_id": "ghost", "manager_node_id": "demo-010"}], "ghost")
        self.fails([{"op": "move", "node_id": "demo-011", "manager_node_id": "ghost"}], "ghost")
        self.fails([{"op": "teleport", "node_id": "demo-011"}], "teleport", "add, modify")

    def test_move_cycle_and_self(self):
        self.fails([{"op": "move", "node_id": "demo-010", "manager_node_id": "demo-011"}], "sits below")
        self.fails([{"op": "move", "node_id": "demo-010", "manager_node_id": "demo-010"}], "themselves")

    def test_add_validation(self):
        self.fails([{"op": "add", "node_id": "demo-010", "title": "T", "manager_node_id": "demo-001"}], "already exists")
        self.fails([{"op": "add", "node_id": "x", "manager_node_id": "demo-001"}], "title")
        self.fails([{"op": "add", "node_id": "x", "title": "T"}], "manager")
        self.fails([{"op": "add", "node_id": "x", "title": "T", "manager_node_id": "demo-001", "status": "filled"}], "name")

    def test_bad_status_and_empty_modify(self):
        self.fails([{"op": "modify", "node_id": "demo-011", "status": "maybe"}], "maybe", "filled")
        self.fails([{"op": "modify", "node_id": "demo-011"}], "nothing to change")
        self.fails([{"op": "modify", "node_id": "demo-011", "manager_node_id": "demo-020"}], "move edit")

    def test_dotted_validation(self):
        self.fails([{"op": "dotted_add", "node_id": "demo-011", "dotted_to_node_ids": "demo-011"}], "themselves")
        self.fails([{"op": "dotted_add", "node_id": "demo-011", "dotted_to_node_ids": "ghost"}], "ghost")
        # demo-010 -> demo-020 already exists in the roster; reverse direction is a duplicate too
        self.fails([{"op": "dotted_add", "node_id": "demo-020", "dotted_to_node_ids": "demo-010"}], "already a dotted line")
        self.fails([{"op": "dotted_add", "node_id": "demo-011", "dotted_to_node_ids": "demo-030;demo-030"}], "already a dotted line")
        self.fails([{"op": "dotted_remove", "node_id": "demo-011", "dotted_to_node_ids": "demo-030"}], "no dotted line")

    def test_not_a_normalized_roster(self):
        with self.assertRaises(scenario.ScenarioError) as ctx:
            scenario.apply_edits({"hello": 1}, [{"op": "remove", "node_id": "x"}])
        self.assertIn("normalize", str(ctx.exception))


class DottedLines(EditBase):
    def test_cap_of_eight_with_companion_list(self):
        render = copy.deepcopy(self.render)
        render["relationships"] = []
        ids = [p["id"] for p in render["people"]]
        pairs = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]][:11]
        rows = [{"op": "dotted_add", "node_id": a, "dotted_to_node_ids": b} for a, b in pairs]
        planned, summary = scenario.apply_edits(render, rows)
        self.assertEqual(len(planned["relationships"]), 8)
        self.assertEqual(len(planned["companion_links"]), 3)
        self.assertEqual((summary["dotted_drawn"], summary["dotted_listed"]), (8, 3))
        self.assertIn("8 drawn", summary["text"])
        self.assertIn("3 listed in a companion table", summary["text"])
        geometry.layout(planned)  # still renders: the cap is respected

    def test_companion_links_rejoin_on_second_pass(self):
        render = copy.deepcopy(self.render)
        render["relationships"] = []
        ids = [p["id"] for p in render["people"]]
        pairs = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]][:9]
        planned, _ = scenario.apply_edits(render, [{"op": "dotted_add", "node_id": a, "dotted_to_node_ids": b} for a, b in pairs])
        again, summary = scenario.apply_edits(planned, [{"op": "dotted_remove", "node_id": pairs[0][0], "dotted_to_node_ids": pairs[0][1]}])
        self.assertEqual((summary["dotted_drawn"], summary["dotted_listed"]), (8, 0))
        self.assertNotIn("companion_links", again)

    def test_add_and_remove(self):
        planned, summary = self.apply([{"op": "dotted_add", "node_id": "demo-011", "dotted_to_node_ids": "demo-030;demo-021"},
                                       {"op": "dotted_remove", "node_id": "demo-010", "dotted_to_node_ids": "demo-020"}])
        self.assertEqual(len(planned["relationships"]), 2)
        self.assertEqual(summary["dotted_drawn"], 2)


class Outputs(EditBase):
    def test_planned_view_renders(self):
        planned, _ = self.apply(scenario.load_edit_rows(str(EDITS / "reorg-plan.csv")))
        plan = geometry.layout(planned)
        self.assertTrue(plan["pages"])

    def test_all_examples_apply_and_json_matches_csv(self):
        for name in ("reorg-plan.csv", "reorg-plan.json", "remove-manager-reassign.csv", "dotted-lines.csv", "mark-open.csv"):
            with self.subTest(name):
                self.apply(scenario.load_edit_rows(str(EDITS / name)))

    def test_cli_never_overwrites_and_prints_plain_summary(self):
        out = self.dir / "planned.json"
        result = run("apply_org_chart_scenario.py", "edit", str(self.roster), str(EDITS / "reorg-plan.csv"), "--output", str(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 added (1 proposed)", result.stdout)
        self.assertIn("original roster was not changed", result.stdout)
        again = run("apply_org_chart_scenario.py", "edit", str(self.roster), str(EDITS / "reorg-plan.csv"), "--output", str(out))
        self.assertEqual(again.returncode, 2)
        self.assertNotIn("Traceback", again.stderr)
        same = run("apply_org_chart_scenario.py", "edit", str(self.roster), str(EDITS / "reorg-plan.csv"), "--output", str(self.roster))
        self.assertEqual(same.returncode, 2)
        self.assertEqual(json.loads(self.roster.read_text()), self.render)

    def test_cli_errors_are_plain(self):
        out = self.dir / "x.json"
        for args in (
            [str(self.dir / "missing.json"), str(EDITS / "reorg-plan.csv")],
            [str(self.roster), str(self.dir / "missing.csv")],
        ):
            result = run("apply_org_chart_scenario.py", "edit", *args, "--output", str(out))
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("could not find", result.stderr)
        bad = self.dir / "bad.json"
        bad.write_text("{nope")
        result = run("apply_org_chart_scenario.py", "edit", str(self.roster), str(bad), "--output", str(out))
        self.assertEqual(result.returncode, 2)
        self.assertIn("not valid JSON", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        columns = self.dir / "cols.csv"
        columns.write_text("op,mystery\nadd,1\n")
        result = run("apply_org_chart_scenario.py", "edit", str(self.roster), str(columns), "--output", str(out))
        self.assertEqual(result.returncode, 2)
        self.assertIn("mystery", result.stderr)

    def test_legacy_scenario_command_still_works(self):
        out, receipt = self.dir / "c.json", self.dir / "r.json"
        result = run("apply_org_chart_scenario.py", str(SKILL / "examples" / "synthetic-scenario.json"),
                     "--output", str(out), "--receipt", str(receipt))
        self.assertEqual(result.returncode, 0, result.stderr)


class DiffPreview(EditBase):
    def test_diff_shows_side_by_side_and_headcount(self):
        planned, _ = self.apply(scenario.load_edit_rows(str(EDITS / "reorg-plan.csv")))
        text = preview.diff(self.render, planned)
        self.assertIn("CURRENT", text)
        self.assertIn("PLANNED", text)
        self.assertIn("1 added, 1 changed, 1 moved, 1 removed", text)
        self.assertIn("headcount 7 -> 7 (+0)", text)
        self.assertIn("Removed: Open | Product Operations Lead", text)

    def test_diff_headcount_rules(self):
        planned, _ = self.apply([
            {"op": "add", "node_id": "n", "display_name": "Person Eta 2", "title": "A", "manager_node_id": "demo-030"},
            {"op": "add", "node_id": "o", "title": "B", "manager_node_id": "demo-030", "status": "open"},
            {"op": "modify", "node_id": "demo-022", "status": "resigned"},
        ])
        self.assertIn("headcount 7 -> 6 (-1)", preview.diff(self.render, planned))  # +1 new filled, 0 open, filled to resigned is -2

    def test_cli_diff_and_errors(self):
        out = self.dir / "p.json"
        run("apply_org_chart_scenario.py", "edit", str(self.roster), str(EDITS / "reorg-plan.csv"), "--output", str(out))
        ok = run("preview_org_chart.py", "diff", str(self.roster), str(out))
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("CURRENT", ok.stdout)
        one = run("preview_org_chart.py", "diff", str(self.roster))
        self.assertEqual(one.returncode, 2)
        self.assertIn("two files", one.stderr)
        gone = run("preview_org_chart.py", "diff", str(self.roster), str(self.dir / "nope.json"))
        self.assertEqual(gone.returncode, 2)
        self.assertNotIn("Traceback", gone.stderr)


if __name__ == "__main__":
    unittest.main()
