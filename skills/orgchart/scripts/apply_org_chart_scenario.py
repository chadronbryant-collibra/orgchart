#!/usr/bin/env python3
"""Apply deterministic current/planning/mixed org-chart scenario changes."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any


SCHEMA = "org-chart-scenario/v1"
RECEIPT_SCHEMA = "org-chart-scenario-receipt/v1"
MODES = {"current", "planning", "mixed"}
POSITION_FIELDS = {
    "personId", "title", "function", "location", "workerType", "status",
    "level", "tenureYears", "compaRatio", "markers", "notes", "sourceAsOf",
    "sortOrder",
}
RELATION_TYPES = {"direct", "matrix", "advisory"}


class ScenarioError(ValueError):
    pass


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ScenarioError(f"{label} must be an object.")
    return value


def indexes(model: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    people = model.get("people")
    positions = model.get("positions")
    relationships = model.get("relationships")
    if not isinstance(people, list) or not isinstance(positions, list) or not isinstance(relationships, list):
        raise ScenarioError("baseline requires people, positions, and relationships arrays.")
    person_by_id: dict[str, dict[str, Any]] = {}
    position_by_id: dict[str, dict[str, Any]] = {}
    for person in people:
        item = require_object(person, "person")
        person_id = text(item.get("personId"))
        if not person_id or person_id in person_by_id:
            raise ScenarioError("personId values must be non-empty and unique.")
        person_by_id[person_id] = item
    for position in positions:
        item = require_object(position, "position")
        position_id = text(item.get("positionId"))
        if not position_id or position_id in position_by_id:
            raise ScenarioError("positionId values must be non-empty and unique.")
        if not text(item.get("title")):
            raise ScenarioError(f"Position {position_id!r} requires a title.")
        person_id = text(item.get("personId"))
        if person_id and person_id not in person_by_id:
            raise ScenarioError(f"Position {position_id!r} refers to unknown person {person_id!r}.")
        position_by_id[position_id] = item
    return person_by_id, position_by_id


def relation_key(relation: dict[str, Any]) -> tuple[str, str, str]:
    return (
        text(relation.get("fromPositionId")),
        text(relation.get("toPositionId")),
        (text(relation.get("type")) or "direct").casefold(),
    )


def validate_model(model: dict[str, Any]) -> None:
    _, position_by_id = indexes(model)
    seen: set[tuple[str, str, str]] = set()
    direct_manager: dict[str, str] = {}
    children: dict[str, list[str]] = {position_id: [] for position_id in position_by_id}
    for relation in model["relationships"]:
        item = require_object(relation, "relationship")
        source, target, kind = relation_key(item)
        if source not in position_by_id or target not in position_by_id:
            raise ScenarioError(f"Relationship endpoint does not exist: {source!r} -> {target!r}.")
        if source == target:
            raise ScenarioError("A position cannot relate to itself.")
        if kind not in RELATION_TYPES:
            raise ScenarioError(f"Unsupported relationship type: {kind!r}.")
        key = (source, target, kind)
        if key in seen:
            raise ScenarioError(f"Duplicate relationship: {source!r} -> {target!r} ({kind}).")
        seen.add(key)
        if kind == "direct":
            if target in direct_manager and direct_manager[target] != source:
                raise ScenarioError(f"Position {target!r} has more than one direct manager.")
            direct_manager[target] = source
            children[source].append(target)

    state: dict[str, int] = {position_id: 0 for position_id in position_by_id}

    def visit(position_id: str) -> None:
        if state[position_id] == 1:
            raise ScenarioError("Direct-report relationships contain a cycle.")
        if state[position_id] == 2:
            return
        state[position_id] = 1
        for child in children[position_id]:
            visit(child)
        state[position_id] = 2

    for position_id in sorted(position_by_id):
        visit(position_id)


def remove_direct_manager(model: dict[str, Any], position_id: str) -> None:
    model["relationships"] = [
        relation for relation in model["relationships"]
        if not (relation_key(relation)[1] == position_id and relation_key(relation)[2] == "direct")
    ]


def add_relation(model: dict[str, Any], relation: dict[str, Any]) -> None:
    candidate = deepcopy(relation)
    source, target, kind = relation_key(candidate)
    candidate["fromPositionId"] = source
    candidate["toPositionId"] = target
    candidate["type"] = kind
    if not source or not target:
        raise ScenarioError("A relationship requires fromPositionId and toPositionId.")
    if kind == "direct":
        remove_direct_manager(model, target)
    if relation_key(candidate) not in {relation_key(item) for item in model["relationships"]}:
        model["relationships"].append(candidate)


def descendants(model: dict[str, Any], position_id: str) -> set[str]:
    children: dict[str, list[str]] = {}
    for relation in model["relationships"]:
        source, target, kind = relation_key(relation)
        if kind == "direct":
            children.setdefault(source, []).append(target)
    found: set[str] = set()
    stack = list(children.get(position_id, []))
    while stack:
        current = stack.pop()
        if current in found:
            continue
        found.add(current)
        stack.extend(children.get(current, []))
    return found


def apply_change(model: dict[str, Any], change: dict[str, Any]) -> None:
    op = text(change.get("op")).casefold()
    _, position_by_id = indexes(model)

    if op == "add_position":
        position = deepcopy(require_object(change.get("position"), "add_position.position"))
        position_id = text(position.get("positionId"))
        if not position_id or position_id in position_by_id:
            raise ScenarioError("add_position requires a new non-empty positionId.")
        if not text(position.get("title")):
            raise ScenarioError("add_position requires position.title.")
        person = change.get("person")
        if person is not None:
            person = deepcopy(require_object(person, "add_position.person"))
            person_id = text(person.get("personId"))
            if not person_id or any(text(item.get("personId")) == person_id for item in model["people"]):
                raise ScenarioError("add_position.person requires a new non-empty personId.")
            if not text(person.get("displayName")):
                raise ScenarioError("add_position.person requires displayName.")
            model["people"].append(person)
            position["personId"] = person_id
        if not text(position.get("personId")):
            position["personId"] = None
            position.setdefault("status", "planned")
        model["positions"].append(position)
        manager_id = text(change.get("managerPositionId"))
        if manager_id:
            add_relation(model, {
                "fromPositionId": manager_id,
                "toPositionId": position_id,
                "type": "direct",
            })

    elif op in {"move_position", "change_manager"}:
        position_id = text(change.get("positionId"))
        manager_id = text(change.get("newManagerPositionId"))
        if position_id not in position_by_id or manager_id not in position_by_id:
            raise ScenarioError("move_position requires existing positionId and newManagerPositionId.")
        if position_id == manager_id:
            raise ScenarioError("A position cannot manage itself.")
        add_relation(model, {
            "fromPositionId": manager_id,
            "toPositionId": position_id,
            "type": "direct",
        })

    elif op == "update_position":
        position_id = text(change.get("positionId"))
        if position_id not in position_by_id:
            raise ScenarioError(f"Unknown positionId: {position_id!r}.")
        changes = require_object(change.get("changes"), "update_position.changes")
        blocked = sorted(set(changes) - POSITION_FIELDS)
        if blocked:
            raise ScenarioError("Unsupported position fields: " + ", ".join(blocked))
        position_by_id[position_id].update(deepcopy(changes))

    elif op == "annotate_position":
        position_id = text(change.get("positionId"))
        annotation = text(change.get("annotation"))
        if position_id not in position_by_id or not annotation:
            raise ScenarioError("annotate_position requires an existing positionId and annotation.")
        previous = text(position_by_id[position_id].get("notes"))
        position_by_id[position_id]["notes"] = f"{previous}\n{annotation}" if previous else annotation

    elif op == "add_relationship":
        add_relation(model, require_object(change.get("relationship"), "add_relationship.relationship"))

    elif op == "remove_relationship":
        relation = require_object(change.get("relationship"), "remove_relationship.relationship")
        key = relation_key(relation)
        before = len(model["relationships"])
        model["relationships"] = [item for item in model["relationships"] if relation_key(item) != key]
        if len(model["relationships"]) == before:
            raise ScenarioError("remove_relationship did not match an existing relationship.")

    elif op == "remove_position":
        position_id = text(change.get("positionId"))
        if position_id not in position_by_id:
            raise ScenarioError(f"Unknown positionId: {position_id!r}.")
        strategy = text(change.get("strategy")) or "error"
        direct_children = [
            relation_key(item)[1] for item in model["relationships"]
            if relation_key(item)[0] == position_id and relation_key(item)[2] == "direct"
        ]
        removed = {position_id}
        if direct_children and strategy == "error":
            raise ScenarioError("remove_position would orphan direct reports; choose cascade or reassign.")
        if strategy == "cascade":
            removed.update(descendants(model, position_id))
        elif strategy == "reassign":
            manager_id = text(change.get("reassignToPositionId"))
            if manager_id not in position_by_id or manager_id in removed:
                raise ScenarioError("reassign requires an existing reassignToPositionId.")
            for child in direct_children:
                add_relation(model, {
                    "fromPositionId": manager_id,
                    "toPositionId": child,
                    "type": "direct",
                })
        elif strategy not in {"error", "cascade"}:
            raise ScenarioError("remove_position strategy must be error, cascade, or reassign.")
        model["positions"] = [item for item in model["positions"] if text(item.get("positionId")) not in removed]
        model["relationships"] = [
            item for item in model["relationships"]
            if relation_key(item)[0] not in removed and relation_key(item)[1] not in removed
        ]

    elif op == "update_organization":
        changes = require_object(change.get("changes"), "update_organization.changes")
        organization = model.setdefault("organization", {})
        require_object(organization, "baseline.organization").update(deepcopy(changes))

    else:
        raise ScenarioError(f"Unsupported scenario operation: {op!r}.")

    validate_model(model)


def apply_scenario(source: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    require_object(source, "scenario")
    if source.get("schema") != SCHEMA:
        raise ScenarioError(f"scenario.schema must be {SCHEMA!r}.")
    mode = text(source.get("mode")).casefold()
    if mode not in MODES:
        raise ScenarioError("scenario.mode must be current, planning, or mixed.")
    changes = source.get("changes", [])
    if not isinstance(changes, list):
        raise ScenarioError("scenario.changes must be an array.")
    if mode == "current" and changes:
        raise ScenarioError("current mode cannot contain scenario changes.")
    baseline = deepcopy(require_object(source.get("baseline"), "scenario.baseline"))
    baseline.setdefault("organization", {})
    validate_model(baseline)
    before_positions = len(baseline["positions"])
    before_relationships = len(baseline["relationships"])
    operations: Counter[str] = Counter()
    for index, change in enumerate(changes, start=1):
        item = require_object(change, f"scenario.changes[{index}]")
        operations[text(item.get("op")).casefold()] += 1
        apply_change(baseline, item)
    baseline["people"] = sorted(baseline["people"], key=lambda item: text(item.get("personId")))
    baseline["positions"] = sorted(baseline["positions"], key=lambda item: text(item.get("positionId")))
    baseline["relationships"] = sorted(baseline["relationships"], key=relation_key)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "mode": mode,
        "changeCount": len(changes),
        "operationCounts": dict(sorted(operations.items())),
        "before": {"positions": before_positions, "relationships": before_relationships},
        "after": {
            "positions": len(baseline["positions"]),
            "relationships": len(baseline["relationships"]),
            "filled": sum(1 for item in baseline["positions"] if text(item.get("status")).casefold() == "filled"),
            "open": sum(1 for item in baseline["positions"] if text(item.get("status")).casefold() == "open"),
            "planned": sum(1 for item in baseline["positions"] if text(item.get("status")).casefold() == "planned"),
        },
        "containsPeopleData": False,
    }
    return baseline, receipt


def read_json(path: str) -> Any:
    if path == "-":
        return json.load(sys.stdin)
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str, value: Any) -> None:
    target = Path(path)
    if target.exists():
        raise ScenarioError(f"Refusing to overwrite existing output: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Friendly edit path: flat roster (render JSON) + flat edit list -> planned view
# ---------------------------------------------------------------------------

EDIT_SCHEMA = "collibra-org-chart-render-input/v1"
EDIT_COLUMNS = (
    "op", "node_id", "display_name", "title", "manager_node_id", "function",
    "status", "note", "dotted_to_node_ids", "reports", "reassign_to_node_id",
)
EDIT_OPS = {
    "add": "add", "modify": "modify", "change": "modify", "update": "modify",
    "move": "move", "remove": "remove", "delete": "remove",
    "propose": "propose", "open": "open",
    "dotted_add": "dotted_add", "add_dotted": "dotted_add",
    "dotted_remove": "dotted_remove", "remove_dotted": "dotted_remove",
}
EDIT_STATUSES = ("filled", "open", "planned", "resigned", "other")
IMPACT = {"filled": 1, "open": 0, "planned": 0, "resigned": -1, "other": 0}
MAX_DRAWN_LINKS = 8
LABELS = {
    "added": "New", "modified": "Updated", "moved": "Moved",
    "proposed": "Proposed", "opened": "Open role",
}
DEFAULT_PROPOSAL_NOTE = "assumption not yet confirmed"


def _name_of(person: dict[str, Any]) -> str:
    return text(person.get("name")) or text(person.get("id"))


def _who(person: dict[str, Any]) -> str:
    return f"{_name_of(person)} ({text(person.get('title'))})"


def _split_ids(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        raw = text(value).replace(",", ";").split(";")
    return [text(item) for item in raw if text(item)]


def load_edit_rows(path: str) -> list[dict[str, Any]]:
    """Read an edit list from CSV or JSON (a list, or an object with 'edits')."""
    import csv
    if path.lower().endswith(".csv"):
        try:
            with Path(path).open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames or "op" not in [c.strip() for c in reader.fieldnames]:
                    raise ScenarioError("The edit list needs a column named 'op' (add, modify, move, remove, ...).")
                rows = [{(k or "").strip(): v for k, v in row.items()} for row in reader]
        except UnicodeDecodeError:
            raise ScenarioError("The edit list is not a readable text file.")
    else:
        try:
            data = read_json(path)
        except json.JSONDecodeError as exc:
            raise ScenarioError(f"The edit list is not valid JSON (line {exc.lineno}).")
        rows = data.get("edits") if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise ScenarioError("The edit list must be a list of edits, or an object with an 'edits' list.")
    rows = [row for row in rows if isinstance(row, dict) and any(text(v) for v in row.values())]
    if not rows:
        raise ScenarioError("The edit list is empty. Nothing to change.")
    unknown = {text(k) for row in rows for k in row} - set(EDIT_COLUMNS)
    if unknown:
        raise ScenarioError("The edit list has columns I do not recognise: " + ", ".join(sorted(unknown))
                            + ". Expected: " + ", ".join(EDIT_COLUMNS) + ".")
    return rows


def _check_render(render: Any) -> dict[str, Any]:
    if not isinstance(render, dict) or not isinstance(render.get("people"), list) or not render["people"]:
        raise ScenarioError("The roster file is not a normalized org chart. Run the normalize step on your CSV first.")
    model = deepcopy(render)
    model.setdefault("relationships", [])
    ids: set[str] = set()
    for person in model["people"]:
        pid = text(person.get("id")) if isinstance(person, dict) else ""
        if not pid or pid in ids:
            raise ScenarioError("The roster has a missing or repeated ID. Fix the roster and normalize again.")
        ids.add(pid)
    # Any extra links the baseline kept in a companion list rejoin the pool.
    model["relationships"] = list(model["relationships"]) + list(model.pop("companion_links", []) or [])
    return model


def _index(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {text(p["id"]): p for p in model["people"]}


def _children(model: dict[str, Any], node_id: str) -> list[dict[str, Any]]:
    return [p for p in model["people"] if text(p.get("manager_id")) == node_id]


def _descendant_ids(model: dict[str, Any], node_id: str) -> set[str]:
    found: set[str] = set()
    stack = [node_id]
    while stack:
        current = stack.pop()
        for child in _children(model, current):
            cid = text(child["id"])
            if cid not in found:
                found.add(cid)
                stack.append(cid)
    return found


def _names(people: list[dict[str, Any]]) -> str:
    return ", ".join(_who(p) for p in people)


def _set_annotation(person: dict[str, Any], change: str, note: str) -> None:
    label = LABELS.get(change, "Updated")
    previous = text(person.get("annotation"))
    details = [d for d in (person.get("details") or []) if text(d) != previous]
    annotation = f"{label}: {note}" if note else label
    person["annotation"] = annotation
    person["note"] = note
    person["change"] = change
    person["details"] = [annotation] + details


def _set_status(person: dict[str, Any], status: str, label: str = "") -> None:
    person["status"] = status
    person["statusLabel"] = label if status == "other" else ""
    person["headcount_impact"] = IMPACT[status]
    if status in {"open", "planned"}:
        person["kind"] = "open_role"
    elif person.get("kind") == "open_role":
        person["kind"] = "person"


def _row_status(row: dict[str, Any], where: str) -> str:
    status = text(row.get("status")).casefold()
    if status and status not in EDIT_STATUSES:
        raise ScenarioError(f"{where}: '{text(row.get('status'))}' is not a status I know. Use one of: "
                            + ", ".join(EDIT_STATUSES) + ".")
    if status == "other" and not text(row.get("note")):
        raise ScenarioError(f"{where}: status 'other' needs a short label in the note column.")
    return status


def _need_person(people: dict[str, dict[str, Any]], node_id: str, where: str) -> dict[str, Any]:
    if not node_id:
        raise ScenarioError(f"{where}: this edit needs a position ID in the node_id column.")
    if node_id not in people:
        raise ScenarioError(f"{where}: I could not find '{node_id}' in the roster.")
    return people[node_id]


def _check_manager(model, people, person_id, manager_id, where):
    if manager_id not in people:
        raise ScenarioError(f"{where}: the manager '{manager_id}' is not in the roster.")
    if manager_id == person_id:
        raise ScenarioError(f"{where}: {_name_of(people[person_id])} cannot report to themselves.")
    if manager_id in _descendant_ids(model, person_id):
        raise ScenarioError(
            f"{where}: {_name_of(people[person_id])} cannot report to {_name_of(people[manager_id])}, "
            "who already sits below them. Move that person first.")


def _links(model: dict[str, Any]) -> list[dict[str, Any]]:
    return model["relationships"]


def _add_links(model, people, source, targets, where):
    existing = {frozenset((text(r.get("from")), text(r.get("to")))) for r in _links(model)}
    for target in targets:
        if target not in people:
            raise ScenarioError(f"{where}: dotted-line target '{target}' is not in the roster.")
        if target == source:
            raise ScenarioError(f"{where}: {_name_of(people[source])} cannot have a dotted line to themselves.")
        key = frozenset((source, target))
        if key in existing:
            raise ScenarioError(f"{where}: there is already a dotted line between {_name_of(people[source])} "
                                f"and {_name_of(people[target])}.")
        existing.add(key)
        _links(model).append({"from": source, "to": target, "type": "matrix"})


def apply_edits(render: Any, rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply a flat edit list to a normalized roster. Returns (planned, summary)."""
    baseline = _check_render(render)
    model = deepcopy(baseline)
    for person in model["people"]:
        person.setdefault("headcount_impact", IMPACT.get(text(person.get("status")) or "filled", 0))
    people = _index(model)
    start_headcount = sum(int(p.get("headcount_impact", 0)) for p in model["people"])
    start_ids = set(people)
    start_manager = {pid: text(p.get("manager_id")) for pid, p in people.items()}
    start_links = len(_links(model))
    touched: dict[str, str] = {}
    removed: list[dict[str, Any]] = []
    notes: list[str] = []

    for number, raw in enumerate(rows, start=1):
        where = f"Edit {number}"
        op = EDIT_OPS.get(text(raw.get("op")).casefold().replace(" ", "_").replace("-", "_"))
        if not op:
            raise ScenarioError(f"{where}: '{text(raw.get('op'))}' is not something I can do. Use add, modify, "
                                "move, remove, propose, open, dotted_add or dotted_remove.")
        node_id = text(raw.get("node_id"))
        note = text(raw.get("note"))
        status = _row_status(raw, where)
        people = _index(model)

        if op == "add":
            if not node_id:
                raise ScenarioError(f"{where}: a new position needs an ID in the node_id column.")
            if node_id in people:
                raise ScenarioError(f"{where}: '{node_id}' already exists. Use modify to change it.")
            if not text(raw.get("title")):
                raise ScenarioError(f"{where}: a new position needs a title.")
            manager = text(raw.get("manager_node_id"))
            if not manager:
                raise ScenarioError(f"{where}: a new position needs a manager (manager_node_id).")
            name = text(raw.get("display_name"))
            status = status or ("filled" if name else "planned")
            if not name:
                if status == "filled":
                    raise ScenarioError(f"{where}: a filled position needs a name.")
                name = "Planned" if status == "planned" else "Open"
            person = {"id": node_id, "name": name, "title": text(raw.get("title")),
                      "manager_id": None, "function": text(raw.get("function")) or people.get(manager, {}).get("function", "Unassigned"),
                      "kind": "person", "worker_type": "employee", "details": [], "markers": [], "order": None}
            model["people"].append(person)
            people = _index(model)
            _check_manager(model, people, node_id, manager, where)
            person["manager_id"] = manager
            _set_status(person, status, note)
            if status == "planned" and not note:
                note = DEFAULT_PROPOSAL_NOTE
            _set_annotation(person, "proposed" if status == "planned" else ("opened" if status == "open" else "added"), note)
            _add_links(model, people, node_id, _split_ids(raw.get("dotted_to_node_ids")), where)
            touched[node_id] = "added"

        elif op == "modify":
            person = _need_person(people, node_id, where)
            changed = False
            for field, key in (("name", "display_name"), ("title", "title"), ("function", "function")):
                if text(raw.get(key)):
                    person[field] = text(raw.get(key)); changed = True
            if status:
                _set_status(person, status, note); changed = True
            if text(raw.get("manager_node_id")):
                raise ScenarioError(f"{where}: to change who {_name_of(person)} reports to, use a move edit.")
            if not changed and not note:
                raise ScenarioError(f"{where}: nothing to change for {_name_of(person)}. Fill in a name, title, function, status or note.")
            if touched.get(node_id) != "added":
                touched[node_id] = touched.get(node_id) or "modified"
            _set_annotation(person, touched[node_id] if touched[node_id] in LABELS else "modified", note or text(person.get("note")))

        elif op == "move":
            person = _need_person(people, node_id, where)
            manager = text(raw.get("manager_node_id"))
            if not manager:
                raise ScenarioError(f"{where}: say who {_name_of(person)} should report to (manager_node_id).")
            _check_manager(model, people, node_id, manager, where)
            if text(person.get("manager_id")) == manager:
                raise ScenarioError(f"{where}: {_name_of(person)} already reports to {_name_of(people[manager])}.")
            person["manager_id"] = manager
            if touched.get(node_id) != "added":
                touched[node_id] = "moved"
            _set_annotation(person, touched[node_id] if touched[node_id] in LABELS else "moved",
                            note or f"reports to {_name_of(people[manager])}")

        elif op in {"propose", "open"}:
            person = _need_person(people, node_id, where)
            target = "planned" if op == "propose" else "open"
            if op == "open" and text(person.get("status")) != "open":
                person["_was"] = _name_of(person)
                person["name"] = "Open"
            _set_status(person, target)
            if op == "propose" and not note:
                note = DEFAULT_PROPOSAL_NOTE
            if touched.get(node_id) != "added":
                touched[node_id] = "proposed" if op == "propose" else "opened"
            _set_annotation(person, touched[node_id] if touched[node_id] in LABELS else "proposed", note)
            person.pop("_was", None)

        elif op == "remove":
            person = _need_person(people, node_id, where)
            kids = _children(model, node_id)
            choice = text(raw.get("reports")).casefold()
            target = text(raw.get("reassign_to_node_id"))
            if choice.startswith("reassign:"):
                target = target or choice.split(":", 1)[1].strip()
                choice = "reassign"
            if kids and choice not in {"reassign", "cascade"}:
                raise ScenarioError(
                    f"{where}: removing {_who(person)} would leave {len(kids)} "
                    f"{'person' if len(kids) == 1 else 'people'} without a manager: {_names(kids)}. "
                    "Choose one: reassign them to someone (reports = reassign, reassign_to_node_id = their new manager), "
                    "remove them too (reports = cascade), or stop and leave things as they are.")
            gone = {node_id}
            if kids and choice == "cascade":
                gone |= _descendant_ids(model, node_id)
            elif kids:
                if target not in people or target in gone:
                    raise ScenarioError(f"{where}: pick an existing person to take over the reports of "
                                        f"{_name_of(person)} (reassign_to_node_id).")
                for kid in kids:
                    kid["manager_id"] = target
                    if touched.get(text(kid["id"])) != "added":
                        touched[text(kid["id"])] = "moved"
                    _set_annotation(kid, touched[text(kid["id"])] if touched[text(kid["id"])] in LABELS else "moved",
                                    f"now reports to {_name_of(people[target])}")
            for gid in gone:
                if gid in start_ids:
                    removed.append(deepcopy(people[gid]))
                touched.pop(gid, None)
            model["people"] = [p for p in model["people"] if text(p["id"]) not in gone]
            model["relationships"] = [r for r in _links(model)
                                      if text(r.get("from")) not in gone and text(r.get("to")) not in gone]

        elif op == "dotted_add":
            person = _need_person(people, node_id, where)
            targets = _split_ids(raw.get("dotted_to_node_ids"))
            if not targets:
                raise ScenarioError(f"{where}: say who the dotted line goes to (dotted_to_node_ids).")
            _add_links(model, people, node_id, targets, where)

        elif op == "dotted_remove":
            person = _need_person(people, node_id, where)
            targets = _split_ids(raw.get("dotted_to_node_ids"))
            if not targets:
                raise ScenarioError(f"{where}: say which dotted line to remove (dotted_to_node_ids).")
            for target in targets:
                keep = [r for r in _links(model)
                        if frozenset((text(r.get("from")), text(r.get("to")))) != frozenset((node_id, target))]
                if len(keep) == len(_links(model)):
                    raise ScenarioError(f"{where}: there is no dotted line between {_name_of(person)} and '{target}'.")
                model["relationships"] = keep

    # A person who was moved and also edited keeps the most informative label.
    people = _index(model)
    if not model["people"]:
        raise ScenarioError("These edits would remove everyone. Nothing was changed.")
    roots = [p for p in model["people"] if not text(p.get("manager_id"))]
    if not roots:
        raise ScenarioError("These edits would leave nobody at the top of the chart.")

    links = _links(model)
    drawn, listed = links[:MAX_DRAWN_LINKS], links[MAX_DRAWN_LINKS:]
    model["relationships"] = drawn
    if listed:
        model["companion_links"] = listed
    else:
        model.pop("companion_links", None)

    end_headcount = sum(int(p.get("headcount_impact", 0)) for p in model["people"])
    new_ids = [text(p["id"]) for p in model["people"] if text(p["id"]) not in start_ids]
    existing = {pid: v for pid, v in touched.items() if pid in start_ids}
    summary = {
        "added": len(new_ids),
        "added_proposed": sum(1 for pid in new_ids if text(people[pid].get("status")) == "planned"),
        "proposed": sum(1 for v in existing.values() if v == "proposed"),
        "marked_open": sum(1 for v in existing.values() if v == "opened"),
        "moved": sum(1 for v in existing.values() if v == "moved"),
        "modified": sum(1 for v in existing.values() if v == "modified"),
        "removed": len(removed),
        "headcount_before": start_headcount,
        "headcount_after": end_headcount,
        "dotted_before": start_links,
        "dotted_after": len(links),
        "dotted_drawn": len(drawn),
        "dotted_listed": len(listed),
        "removed_positions": [{"id": text(p["id"]), "name": _name_of(p), "title": text(p.get("title"))} for p in removed],
    }
    summary["text"] = plain_summary(summary)
    model["title"] = text(model.get("title"))
    model["edit_summary"] = {k: v for k, v in summary.items() if k != "removed_positions"}
    model["edit_summary"]["removed_positions"] = summary["removed_positions"]
    return model, summary


def plain_summary(s: dict[str, Any]) -> str:
    parts = []
    if s["added"]:
        extra = f" ({s['added_proposed']} proposed)" if s["added_proposed"] else ""
        parts.append(f"{s['added']} added{extra}")
    if s["proposed"]:
        parts.append(f"{s['proposed']} marked proposed")
    if s["marked_open"]:
        parts.append(f"{s['marked_open']} marked open")
    if s["modified"]:
        parts.append(f"{s['modified']} changed")
    if s["moved"]:
        parts.append(f"{s['moved']} moved")
    if s["removed"]:
        parts.append(f"{s['removed']} removed")
    if s["dotted_after"] != s["dotted_before"]:
        parts.append(f"dotted lines {s['dotted_before']} -> {s['dotted_after']}")
    head = ", ".join(parts) or "no changes"
    out = f"{head}; headcount {s['headcount_before']} -> {s['headcount_after']}"
    if s["dotted_after"]:
        out += f"; dotted lines: {s['dotted_drawn']} drawn on the chart"
        out += f", {s['dotted_listed']} listed in a companion table" if s["dotted_listed"] else ""
    return out


def _edit_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="apply_org_chart_scenario.py edit",
                                     description="Apply a flat edit list (CSV or JSON) to a normalized roster.")
    parser.add_argument("roster", help="Normalized roster JSON (from the normalize step). It is never changed.")
    parser.add_argument("edits", help="Edit list: CSV or JSON.")
    parser.add_argument("--output", required=True, help="New planned-view JSON path (must not exist).")
    args = parser.parse_args(argv)
    try:
        if Path(args.output).resolve() in {Path(args.roster).resolve(), Path(args.edits).resolve()}:
            raise ScenarioError("The output file must be a new file, not your roster or edit list.")
        try:
            render = read_json(args.roster)
        except json.JSONDecodeError:
            raise ScenarioError("The roster file is not valid JSON. Run the normalize step on your CSV first.")
        planned, summary = apply_edits(render, load_edit_rows(args.edits))
        write_json(args.output, planned)
    except FileNotFoundError as exc:
        print(f"error: I could not find the file {exc.filename}.", file=sys.stderr)
        return 2
    except (OSError, ScenarioError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(summary["text"])
    print(f"Planned view written to {args.output}. Your original roster was not changed.")
    return 0



def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "edit":
        return _edit_main(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Scenario JSON path or - for stdin")
    parser.add_argument("--output", required=True, help="Canonical output JSON path")
    parser.add_argument("--receipt", required=True, help="Count-only receipt JSON path")
    args = parser.parse_args(argv)
    try:
        canonical, receipt = apply_scenario(read_json(args.input))
        if Path(args.output).resolve() == Path(args.receipt).resolve():
            raise ScenarioError("--output and --receipt must be different files.")
        write_json(args.output, canonical)
        write_json(args.receipt, receipt)
    except (OSError, json.JSONDecodeError, ScenarioError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
