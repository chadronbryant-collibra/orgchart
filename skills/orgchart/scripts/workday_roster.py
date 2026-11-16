#!/usr/bin/env python3
"""Merge Workday roster tool pages into an orgchart roster file. Stdlib only, local only.

Prints counts and field names, never row values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
import re
from datetime import date
from pathlib import Path

FIELDS = [
    "node_id", "display_name", "title", "manager_node_id", "node_type", "status",
    "worker_type", "function", "location", "metadata", "dotted_to_node_ids",
    "markers", "sort_order", "source_as_of", "source_ref",
]
CALLS_UNIT0_PAGE = 3
CALLS_SUBORG_PAGE = 5
SECONDS_PER_CALL = 0.45


def truthy(value) -> bool:
    return str(value).strip().lower() == "true"


def load_page(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {"rows": data}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: not a JSON object or list")
    if isinstance(data.get("result"), dict):  # the tools wrap the envelope in "result"
        data = data["result"]
    return data


def completeness_of(page: dict) -> tuple[str, list[str]]:
    comp = page.get("completeness")
    raw = page.get("reason_codes") or []
    codes = [raw] if isinstance(raw, str) else list(raw)
    if isinstance(comp, dict):
        extra = comp.get("reason_codes") or []
        codes += [extra] if isinstance(extra, str) else list(extra)
        comp = comp.get("status")
    flat: list[str] = []
    for c in codes:
        flat += [p.strip() for p in str(c).split(",") if p.strip()]
    return str(comp or "unknown"), flat


CONTINGENT_MARK = re.compile(r"\s*\[C\]\s*$")


def strip_trailing_parens(text: str) -> str:
    """Remove one trailing balanced (...) group, e.g. a manager name on a function label."""
    t = text.rstrip()
    if not t.endswith(")"):
        return text
    depth = 0
    for i in range(len(t) - 1, -1, -1):
        depth += 1 if t[i] == ")" else -1 if t[i] == "(" else 0
        if depth == 0:
            return t[:i].rstrip() or text
    return text


def as_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def page_gaps(pages: list[dict]) -> int:
    """Count breaks in the unit/offset chain (a page that was skipped or reordered)."""
    if not any("unit" in p for p in pages):
        return 0
    gaps, expect_unit, expect_offset = 0, 0, 0
    for p in pages:
        if str(p.get("outcome", "ok")) != "ok":
            continue
        unit = as_int(p.get("unit"))
        if unit is None:
            continue
        if unit != expect_unit:
            gaps += 1
        if truthy(p.get("has_more", "false")):
            nu, no = as_int(p.get("next_unit")), as_int(p.get("next_offset"))
            if nu is None or no is None:
                gaps += 1
                break
            if nu == unit and no != (expect_offset or 0) + len(p.get("rows") or []):
                gaps += 1  # next_offset does not follow from the rows returned
            expect_unit, expect_offset = nu, no
        else:
            expect_unit, expect_offset = None, None
    return gaps


DECK_LIMIT = 1000   # orgchart: people per deck
STAGE_AT = 200      # above this, chart as overview plus team pages


def size_advice(rows: int) -> str:
    return "split_decks" if rows > DECK_LIMIT else "staged" if rows > STAGE_AT else "single_chart"


DIGEST_FIELDS = ["node_id", "display_name", "title", "manager_node_id", "function",
                 "status", "worker_type", "node_type", "location"]
DIGEST_ALG = "sha256-lines-v1"


def rows_digest(rows: list[dict]) -> str:
    """sha256 over one pipe-joined line per row, in returned order."""
    lines = ["|".join(str(r.get(f, "")) for f in DIGEST_FIELDS) for r in rows]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


NODE_ID_SHAPE = re.compile(r"^[0-9a-f]{64}$")


def integrity(pages: list[dict]) -> dict:
    """Checks that catch a page whose rows were changed or dropped when it was saved.

    Without a page digest these see only count and consistency breaks (a changed
    location is invisible).
    """
    count_mismatch = digest_checked = digest_bad = ok_pages = 0
    unit_rows: dict[int, int] = {}
    unit_total: dict[int, int] = {}
    unit_functions: dict[int, set] = {}
    for p in pages:
        if str(p.get("outcome", "ok")) != "ok":
            continue
        ok_pages += 1
        rows = p.get("rows") or []
        rc = as_int(p.get("returned_count"))
        if rc is not None and rc != len(rows):
            count_mismatch += 1
        if p.get("rows_digest") and p.get("rows_digest_alg") == DIGEST_ALG:
            digest_checked += 1
            if rows_digest(rows) != str(p["rows_digest"]).lower():
                digest_bad += 1
        unit = as_int(p.get("unit"))
        if unit is None:
            continue
        unit_rows[unit] = unit_rows.get(unit, 0) + len(rows)
        total = as_int(p.get("total_in_unit"))
        if total is not None:
            unit_total[unit] = total
        unit_functions.setdefault(unit, set()).update(str(r.get("function", "")) for r in rows)
    return {
        "page_count_mismatch": count_mismatch,
        "unit_total_mismatch": sum(1 for u, t in unit_total.items() if unit_rows.get(u, 0) != t),
        "units_with_mixed_function": sum(1 for f in unit_functions.values() if len(f) > 1),
        "page_digest_mismatch": digest_bad,
        "pages_digest_checked": digest_checked,
        "pages_without_digest": ok_pages - digest_checked,
    }


def plan(args) -> int:
    # Inactive sub-orgs are included and each still costs a page, so they are
    # not subtracted. --inactive-sub-orgs is kept only so older calls still run.
    if args.depth == 1:
        pages = max(1, math.ceil(args.people / 100)) if args.people else 1
        calls = pages * CALLS_UNIT0_PAGE
    else:
        pages = max(1 + args.sub_orgs, math.ceil(args.people / 100) if args.people else 0)
        calls = CALLS_UNIT0_PAGE + (pages - 1) * CALLS_SUBORG_PAGE
    tier = "just_pull" if pages <= 5 else "heads_up" if pages <= 20 else "ask_for_yes"
    print(json.dumps({
        "min_pages": pages,
        "workday_calls": calls,
        "approx_seconds": round(calls * SECONDS_PER_CALL),
        "observed_note": "Expect roughly 3 to 4 seconds per page, including turn overhead.",
        "advice": tier,
        "note": "Lower bound; large units need more pages.",
    }, indent=2))
    return 0


def assemble(args) -> int:
    # The report holds counts only and is rewritten on every run, so a stopped run
    # can be repeated with new flags. The roster holds People rows and is never overwritten.
    if Path(args.output).exists():
        print(f"refusing to overwrite {args.output}", file=sys.stderr)
        return 2
    paths = sorted(Path(p) for p in args.pages)
    if not paths:
        print("no page files given", file=sys.stderr)
        return 2
    pages = [load_page(p) for p in paths]

    outcomes, comps, codes = Counter(), Counter(), Counter()
    inactive_units = 0
    unexplained_partial = 0
    contingent_fixed = 0
    rows_in = 0
    merged: dict[str, dict] = {}
    duplicates = conflicting = 0
    for page in pages:
        outcomes[str(page.get("outcome", "ok"))] += 1
        status, reasons = completeness_of(page)
        comps[status] += 1
        codes.update(reasons)
        if status == "partial" and not reasons:
            unexplained_partial += 1
        if str(page.get("unit_status", "")).lower() == "inactive":
            inactive_units += 1
        for row in page.get("rows") or []:
            rows_in += 1
            nid = str(row.get("node_id", "")).strip()
            if not nid:
                outcomes["row_without_node_id"] += 1
                continue
            if nid in merged:
                duplicates += 1
                if str(row.get("manager_node_id", "")) != merged[nid]["manager_node_id"]:
                    conflicting += 1
                continue
            merged[nid] = {k: ("" if row.get(k) is None else str(row.get(k, ""))) for k in FIELDS}
            merged[nid]["manager_node_id"] = str(row.get("manager_node_id") or "").strip()
            if CONTINGENT_MARK.search(merged[nid]["display_name"]):
                merged[nid]["display_name"] = CONTINGENT_MARK.sub("", merged[nid]["display_name"])
                if merged[nid]["worker_type"] in ("", "employee", "unknown"):
                    merged[nid]["worker_type"] = "contingent"
                contingent_fixed += 1
            if args.clean_function:
                merged[nid]["function"] = strip_trailing_parens(merged[nid]["function"])

    ids = set(merged)
    dangling = [n for n, r in merged.items() if r["manager_node_id"] and r["manager_node_id"] not in ids]
    cycles = 0
    for start in merged:
        seen, cur = set(), start
        while cur and cur in merged and cur not in seen:
            seen.add(cur)
            cur = merged[cur]["manager_node_id"]
        if cur and cur in seen:
            cycles += 1

    last = pages[-1]
    unfinished = truthy(last.get("has_more", "false"))
    partial_reasons = sorted({c for c in codes if c != "more_pages"})
    bad_outcomes = sorted(o for o in outcomes if o not in ("ok", "row_without_node_id"))
    gaps = page_gaps(pages)
    checks = integrity(pages)
    integrity_failed = any(v for k, v in checks.items() if k not in ("pages_digest_checked", "pages_without_digest"))
    if unfinished:
        partial_reasons.append("pull_not_finished")
    if gaps:
        partial_reasons.append("page_gap")
    if integrity_failed:
        partial_reasons.append("integrity_check_failed")
    if bad_outcomes:
        partial_reasons += [f"outcome:{o}" for o in bad_outcomes]
    if unexplained_partial:
        partial_reasons.append("partial_without_reason")
    verdict = "partial" if partial_reasons else "complete"

    report = {
        "verdict": verdict,
        "partial_reasons": partial_reasons,
        "pages": len(pages),
        "rows_in": rows_in,
        "rows_out": len(merged),
        "duplicates_removed": duplicates,
        "duplicates_with_different_manager": conflicting,
        "dangling_manager_links": len(dangling),
        "distinct_missing_managers": len({merged[n]["manager_node_id"] for n in dangling}),
        "cycles": cycles,
        "inactive_units_flagged": inactive_units,
        "size_advice": size_advice(len(merged)),
        "page_gaps": gaps,
        "integrity": checks,
        "nonstandard_node_ids": sum(1 for n in merged if not NODE_ID_SHAPE.match(n)),
        "warnings": ([f"{checks['pages_without_digest']} page(s) saved without rows_digest: a changed location or similar value cannot be detected; save rows_digest and rows_digest_alg with every page"] if checks["pages_without_digest"] else []),
        "contingent_marker_fixed": contingent_fixed,
        "outcomes": dict(outcomes),
        "completeness_values": dict(comps),
        "reason_codes": dict(codes),
        "status_counts": dict(Counter(r["status"] for r in merged.values())),
        "worker_type_counts": dict(Counter(r["worker_type"] for r in merged.values())),
        "node_type_counts": dict(Counter(r["node_type"] for r in merged.values())),
        "roots": sum(1 for r in merged.values() if not r["manager_node_id"]),
        "wrote_roster": False,
    }

    if integrity_failed and not args.accept_integrity:
        Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        print("integrity checks failed: a saved page does not match its own counts or unit; "
              "re-save the affected pages from the tool responses and rerun", file=sys.stderr)
        return 3
    if cycles:
        Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        print("manager cycle found; roster not written", file=sys.stderr)
        return 3
    missing = {merged[n]["manager_node_id"] for n in dangling}
    if args.add_head:
        if len(missing) != 1:
            Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            print("--add-head needs exactly one missing manager; found %d" % len(missing), file=sys.stderr)
            return 3
        head_id = next(iter(missing))
        head = {k: "" for k in FIELDS}
        unit0 = next((r for r in merged.values() if r["function"]), None)
        head.update(node_id=head_id, display_name=args.add_head, title=args.head_title,
                    node_type="person", status="filled", worker_type="employee",
                    function=unit0["function"] if unit0 else "")
        merged = {head_id: head, **merged}
        dangling = []
        report["head_row_added"] = True
        report["head_row_synthesized_fields"] = ["display_name", "title"] + (["function"] if head["function"] else [])
        report["rows_out"] = len(merged)
        report["size_advice"] = size_advice(len(merged))
    if dangling and args.dangling != "roots":
        Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        print("manager links point outside the pull (often the org head, who is not a row); ask the user, then rerun with --dangling roots", file=sys.stderr)
        return 3
    if dangling:
        for n in dangling:
            merged[n]["manager_node_id"] = ""
        report["roots"] = sum(1 for r in merged.values() if not r["manager_node_id"])
        report["dangling_made_roots"] = len(dangling)

    report["roots"] = sum(1 for r in merged.values() if not r["manager_node_id"])
    today = args.as_of or date.today().isoformat()
    out_rows = []
    for i, row in enumerate(merged.values(), 1):
        row["sort_order"] = str(i)
        row["source_as_of"] = today
        row["status"] = row["status"] or "filled"
        row["node_type"] = row["node_type"] or "person"
        out_rows.append({k: row[k] for k in FIELDS})
    Path(args.output).write_text(json.dumps(out_rows, indent=2), encoding="utf-8")
    report["wrote_roster"] = True
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="estimate pages and time")
    p.add_argument("--people", type=int, default=0)
    p.add_argument("--sub-orgs", type=int, default=0)
    p.add_argument("--inactive-sub-orgs", type=int, default=0)
    p.add_argument("--depth", type=int, choices=(1, 2), default=2)
    p.set_defaults(func=plan)
    a = sub.add_parser("assemble", help="merge page files into a roster file")
    a.add_argument("pages", nargs="+")
    a.add_argument("--output", required=True)
    a.add_argument("--report", required=True)
    a.add_argument("--dangling", choices=("fail", "roots"), default="fail")
    a.add_argument("--as-of", default="")
    a.add_argument("--add-head", default="", help="name for the one missing manager (the org head)")
    a.add_argument("--head-title", default="Organization head",
                   help="title for the added head row; /orgchart needs a title (default: Organization head)")
    a.add_argument("--accept-integrity", action="store_true", help="write the roster even if integrity checks failed")
    a.add_argument("--clean-function", action="store_true", help="drop a trailing (manager name) from function labels")
    a.set_defaults(func=assemble)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
