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


def main(argv: list[str] | None = None) -> int:
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
