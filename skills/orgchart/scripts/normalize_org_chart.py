#!/usr/bin/env python3
"""Normalize portable org-chart sources and classify connector capabilities.

The normalizer accepts the skill's flat CSV/JSON interchange format or its
canonical people/positions/relationships JSON. It emits a deterministic render
payload for ``org_chart_geometry.py`` and a separate, count-only provenance
receipt that contains no names, node IDs, raw rows, or query values.

The capability classifier is deliberately pure: callers describe tools whose
schemas were actually loaded and tag only capabilities visible in those
schemas. Negative discovery never becomes an entitlement-absence claim.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from collections import defaultdict, deque
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


NORMALIZED_SCHEMA = "collibra-org-chart-render-input/v1"
RECEIPT_SCHEMA = "collibra-org-chart-provenance-receipt/v1"
CAPABILITY_SCHEMA = "collibra-org-chart-connector-capabilities/v1"

FLAT_REQUIRED = {"node_id", "display_name", "title"}
FLAT_KNOWN = {
    "node_id",
    "display_name",
    "title",
    "manager_node_id",
    "node_type",
    "status",
    "statusLabel",
    "status_label",
    "worker_type",
    "function",
    "location",
    "metadata",
    "dotted_to_node_ids",
    "markers",
    "sort_order",
    "source_as_of",
    "source_ref",
}

# Key matching is case/punctuation-insensitive. Presence of one of these fields
# requires an explicit --allow-sensitive value even when every row is blank.
SENSITIVE_FIELDS = {
    "age",
    "compensation",
    "compa_ratio",
    "compaRatio",
    "date_of_birth",
    "disability",
    "email",
    "ethnicity",
    "gender",
    "home_address",
    "leave",
    "notes",
    "performance",
    "phone",
    "promotion_recommendation",
    "protected_class",
    "race",
    "salary",
    "succession",
}
SENSITIVE_MARKERS = {
    "critical_person",
    "critical_person_and_role",
    "critical_role",
    "no_internal_successor",
    "promotion_recommendation",
    "successor_1_2_years",
    "successor_ready_now",
}

CAPABILITIES = {
    "self_profile",
    "self_manager",
    "direct_reports",
    "email_lookup",
    "user_search",
    "user_profile",
    "people_search",
    "position_search",
    "directory_users",
    "departments",
    "locations",
    "manager_relationships",
    "roster_export",
    "table_export",
    "vacancy_status",
}
SELF_SERVICE = {"self_profile", "self_manager", "direct_reports"}
IDENTITY_LOOKUP = {"self_profile", "email_lookup", "user_search", "user_profile"}
ROSTER_NODES = {"people_search", "position_search", "directory_users"}
# ``direct_reports`` is deliberately excluded. In Claude-work it can be a
# self-service, one-level operation rooted at the signed-in user; combining it
# with an unrelated people search would not prove a traversable roster graph.
ROSTER_RELATIONSHIPS = {"manager_relationships"}
RECEIPT_KINDS = {"person", "open_role", "contractor", "unknown"}


class NormalizationError(ValueError):
    """Raised when source data is ambiguous, unsafe, or structurally invalid."""


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


SENSITIVE_KEYS = {_normalized_key(value) for value in SENSITIVE_FIELDS}
SENSITIVE_MARKER_KEYS = {_normalized_key(value) for value in SENSITIVE_MARKERS}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _iso_date(value: Any, field: str) -> str | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise NormalizationError(f"{field} must use YYYY-MM-DD: {text!r}") from exc
    return parsed.date().isoformat()


def _iso_timestamp(value: Any, field: str) -> str | None:
    text = _text(value)
    if not text:
        return None
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise NormalizationError(f"{field} must be an ISO-8601 timestamp: {text!r}") from exc
    return text


def _coarse_label(value: Any, field: str) -> str | None:
    text = _text(value)
    if not text:
        return None
    if "@" in text or len(text) > 80 or not re.fullmatch(r"[A-Za-z0-9 ._/+:-]+", text):
        raise NormalizationError(
            f"{field} must be a coarse non-personal label, not an account, query, or record value."
        )
    return text


def _list_value(value: Any, field: str) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    if not isinstance(value, str):
        raise NormalizationError(f"{field} must be a list or a semicolon-delimited string.")
    stripped = value.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise NormalizationError(f"{field} contains invalid JSON list syntax.") from exc
        return _list_value(parsed, field)
    return [item.strip() for item in stripped.split(";") if item.strip()]


def _integer(value: Any, field: str) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise NormalizationError(f"{field} must be an integer.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise NormalizationError(f"{field} must be an integer.") from exc
    if str(result) != str(value).strip() and not isinstance(value, int):
        raise NormalizationError(f"{field} must be an integer.")
    return result


def _allowed_sensitive(values: Iterable[str]) -> set[str]:
    return {_normalized_key(value) for value in values if _text(value)}


def _check_sensitive_fields(keys: Iterable[str], allowed: set[str]) -> set[str]:
    present = {_normalized_key(key) for key in keys}
    blocked = sorted(present & SENSITIVE_KEYS - allowed)
    if blocked:
        raise NormalizationError(
            "Sensitive columns require explicit allow-listing: " + ", ".join(blocked)
        )
    return present & SENSITIVE_KEYS


def _check_sensitive_markers(markers: Iterable[str], allowed: set[str]) -> set[str]:
    present = {_normalized_key(marker) for marker in markers}
    blocked = sorted(present & SENSITIVE_MARKER_KEYS - allowed)
    if blocked:
        raise NormalizationError(
            "Sensitive markers require explicit allow-listing: " + ", ".join(blocked)
        )
    return present & SENSITIVE_MARKER_KEYS


def _stable_sort_people(people: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        people,
        key=lambda person: (
            person.get("order") if person.get("order") is not None else 10_000_000,
            _text(person.get("function")).casefold(),
            _text(person.get("title")).casefold(),
            _text(person.get("name")).casefold(),
            person["id"],
        ),
    )


def _kind(node_type: Any, status: Any = None, worker_type: Any = None, has_person: bool = True) -> str:
    supplied = _text(node_type).casefold().replace("-", "_").replace(" ", "_")
    if supplied:
        return supplied
    normalized_status = _text(status).casefold().replace("-", "_").replace(" ", "_")
    normalized_worker = _text(worker_type).casefold().replace("-", "_").replace(" ", "_")
    if normalized_status in {"open", "planned"}:
        return "open_role"
    if normalized_worker in {"contractor", "contingent", "contingent_worker"}:
        return "contractor"
    return "person" if has_person else "unknown"


def _validate_graph(
    people: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    allow_disconnected: bool,
) -> tuple[list[str], int]:
    by_id: dict[str, dict[str, Any]] = {}
    for person in people:
        node_id = person["id"]
        if node_id in by_id:
            raise NormalizationError(f"Duplicate node id: {node_id}")
        by_id[node_id] = person
    if not by_id:
        raise NormalizationError("The source contains no positions or nodes.")

    parent_by_child: dict[str, str] = {}
    relationship_keys: set[tuple[str, str, str]] = set()
    for person in people:
        manager_id = person.get("manager_id")
        if not manager_id:
            continue
        if manager_id not in by_id:
            raise NormalizationError(f"Unknown manager id {manager_id!r} for node {person['id']!r}.")
        if manager_id == person["id"]:
            raise NormalizationError(f"Node {person['id']!r} cannot manage itself.")
        if person["id"] in parent_by_child and parent_by_child[person["id"]] != manager_id:
            raise NormalizationError(f"Node {person['id']!r} has more than one direct manager.")
        parent_by_child[person["id"]] = manager_id

    for relation in relationships:
        source = relation.get("from")
        target = relation.get("to")
        relation_type = relation.get("type", "matrix")
        if source not in by_id or target not in by_id:
            raise NormalizationError(
                f"Relationship endpoint does not exist: {source!r} -> {target!r}."
            )
        if source == target:
            raise NormalizationError(f"Node {source!r} cannot have a relationship to itself.")
        key = (str(source), str(target), str(relation_type))
        if key in relationship_keys:
            raise NormalizationError(f"Duplicate relationship: {source!r} -> {target!r} ({relation_type}).")
        relationship_keys.add(key)

    children: dict[str, list[str]] = defaultdict(list)
    indegree = {node_id: 0 for node_id in by_id}
    for child, parent in parent_by_child.items():
        children[parent].append(child)
        indegree[child] += 1
    queue = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    roots = list(queue)
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for child in sorted(children[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if visited != len(by_id):
        raise NormalizationError("The direct-report graph contains a cycle.")
    if not roots:
        raise NormalizationError("The direct-report graph has no root.")
    if len(roots) > 1 and not allow_disconnected:
        raise NormalizationError(
            f"The direct-report graph has {len(roots)} roots/disconnected components; "
            "use --allow-disconnected only when this is intentional."
        )
    return roots, len(roots)


def _effective_summary(dates: Iterable[str | None], override: str | None) -> tuple[list[str], str, str | None]:
    values = sorted({date for date in dates if date})
    if override:
        if override not in values:
            values.append(override)
            values.sort()
        return values, "declared", override
    if not values:
        return [], "not_supplied", None
    if len(values) == 1:
        return values, "single", values[0]
    return values, "mixed", min(values)


def _normalize_flat(
    rows: list[dict[str, Any]], allowed: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not rows:
        raise NormalizationError("The flat source contains no rows.")
    if any(not isinstance(row, dict) for row in rows):
        raise NormalizationError("Every flat JSON row must be an object.")
    keys = {str(key) for row in rows for key in row}
    missing = sorted(FLAT_REQUIRED - keys)
    if missing:
        raise NormalizationError("Flat input is missing required columns: " + ", ".join(missing))
    sensitive_used = _check_sensitive_fields(keys, allowed)
    unknown_columns = sorted(keys - FLAT_KNOWN)
    people: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    effective_dates: list[str | None] = []
    marker_sensitive: set[str] = set()
    for index, row in enumerate(rows, start=1):
        node_id = _text(row.get("node_id"))
        name = _text(row.get("display_name"))
        title = _text(row.get("title"))
        if not node_id:
            raise NormalizationError(f"Flat row {index} is missing node_id.")
        if not name:
            raise NormalizationError(f"Flat row {index} is missing display_name.")
        if not title:
            raise NormalizationError(f"Flat row {index} is missing title.")
        markers = _list_value(row.get("markers"), f"row {index} markers")
        marker_sensitive.update(_check_sensitive_markers(markers, allowed))
        details = _list_value(row.get("metadata"), f"row {index} metadata")
        location = _text(row.get("location"))
        if location:
            details.insert(0, location)
        source_as_of = _iso_date(row.get("source_as_of"), f"row {index} source_as_of")
        effective_dates.append(source_as_of)
        person = {
            "id": node_id,
            "name": name,
            "title": title,
            "manager_id": _text(row.get("manager_node_id")) or None,
            "function": _text(row.get("function")) or "Unassigned",
            "kind": _kind(row.get("node_type"), row.get("status"), row.get("worker_type"), False),
            "status": _text(row.get("status")).casefold() or "filled",
            "statusLabel": _text(row.get("statusLabel") or row.get("status_label")),
            "worker_type": _text(row.get("worker_type")).casefold() or "unknown",
            "details": details,
            "markers": markers,
            "order": _integer(row.get("sort_order"), f"row {index} sort_order"),
            "source_as_of": source_as_of,
        }
        source_ref = _text(row.get("source_ref"))
        if source_ref:
            person["source_ref"] = source_ref
        people.append(person)
        for target in _list_value(row.get("dotted_to_node_ids"), f"row {index} dotted_to_node_ids"):
            relationships.append({"from": node_id, "to": target, "type": "matrix"})
    return people, relationships, {
        "effective_dates": effective_dates,
        "unknown_columns": unknown_columns,
        "sensitive_used": sorted(sensitive_used | marker_sensitive),
        "person_records": None,
    }


def _normalize_canonical(
    source: dict[str, Any], allowed: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    people_source = source.get("people")
    positions = source.get("positions")
    relations = source.get("relationships")
    if not isinstance(people_source, list) or not isinstance(positions, list) or not isinstance(relations, list):
        raise NormalizationError("Canonical input requires people, positions, and relationships arrays.")
    person_by_id: dict[str, dict[str, Any]] = {}
    for index, person in enumerate(people_source, start=1):
        if not isinstance(person, dict):
            raise NormalizationError(f"Canonical people[{index}] must be an object.")
        person_id = _text(person.get("personId"))
        if not person_id:
            raise NormalizationError(f"Canonical people[{index}] is missing personId.")
        if person_id in person_by_id:
            raise NormalizationError(f"Duplicate person id: {person_id}")
        if not _text(person.get("displayName")):
            raise NormalizationError(f"Canonical person {person_id!r} is missing displayName.")
        person_by_id[person_id] = person

    position_keys = {str(key) for position in positions if isinstance(position, dict) for key in position}
    canonical_keys = {
        str(key)
        for collection in (people_source, positions, relations)
        for item in collection
        if isinstance(item, dict)
        for key in item
    }
    organization_candidate = source.get("organization")
    if isinstance(organization_candidate, dict):
        canonical_keys.update(str(key) for key in organization_candidate)
    sensitive_used = _check_sensitive_fields(canonical_keys, allowed)
    position_by_id: dict[str, dict[str, Any]] = {}
    for index, position in enumerate(positions, start=1):
        if not isinstance(position, dict):
            raise NormalizationError(f"Canonical positions[{index}] must be an object.")
        position_id = _text(position.get("positionId"))
        if not position_id:
            raise NormalizationError(f"Canonical positions[{index}] is missing positionId.")
        if position_id in position_by_id:
            raise NormalizationError(f"Duplicate position id: {position_id}")
        person_id = _text(position.get("personId"))
        if person_id and person_id not in person_by_id:
            raise NormalizationError(f"Position {position_id!r} refers to unknown person {person_id!r}.")
        position_by_id[position_id] = position

    managers: dict[str, str] = {}
    relationships: list[dict[str, Any]] = []
    for index, relation in enumerate(relations, start=1):
        if not isinstance(relation, dict):
            raise NormalizationError(f"Canonical relationships[{index}] must be an object.")
        source_id = _text(relation.get("fromPositionId"))
        target_id = _text(relation.get("toPositionId"))
        relation_type = (_text(relation.get("type")) or "direct").casefold()
        if source_id not in position_by_id or target_id not in position_by_id:
            raise NormalizationError(
                f"Canonical relationship endpoint does not exist: {source_id!r} -> {target_id!r}."
            )
        if source_id == target_id:
            raise NormalizationError(f"Position {source_id!r} cannot have a relationship to itself.")
        if relation_type == "direct":
            if target_id in managers and managers[target_id] != source_id:
                raise NormalizationError(f"Position {target_id!r} has more than one direct manager.")
            managers[target_id] = source_id
        elif relation_type in {"matrix", "advisory"}:
            item = {"from": source_id, "to": target_id, "type": relation_type}
            label = _text(relation.get("label"))
            if label:
                item["label"] = label
            relationships.append(item)
        else:
            raise NormalizationError(f"Unsupported canonical relationship type: {relation_type!r}")

    organization = source.get("organization") or {}
    if not isinstance(organization, dict):
        raise NormalizationError("Canonical organization must be an object.")
    organization_date = _iso_date(organization.get("asOfDate"), "organization.asOfDate")
    effective_dates: list[str | None] = []
    marker_sensitive: set[str] = set()
    output_people: list[dict[str, Any]] = []
    for position_id, position in position_by_id.items():
        person_id = _text(position.get("personId"))
        person = person_by_id.get(person_id) if person_id else None
        status = _text(position.get("status")) or "filled"
        worker_type = _text(position.get("workerType")) or "unknown"
        markers = _list_value(position.get("markers"), f"position {position_id} markers")
        marker_sensitive.update(_check_sensitive_markers(markers, allowed))
        source_as_of = _iso_date(position.get("sourceAsOf"), f"position {position_id} sourceAsOf") or organization_date
        effective_dates.append(source_as_of)
        details: list[str] = []
        for value in (position.get("location"), position.get("level")):
            if _text(value):
                details.append(_text(value))
        if position.get("tenureYears") not in (None, ""):
            details.append(f"{position['tenureYears']} years")
        if position.get("compaRatio") not in (None, ""):
            details.append(f"{position['compaRatio']} compa-ratio")
        if position.get("notes") not in (None, ""):
            details.append(_text(position.get("notes")))
        display_name = ""
        if person:
            display_name = _text(person.get("preferredName")) or _text(person.get("displayName"))
        elif status.casefold() in {"open", "planned"}:
            display_name = "Open"
        else:
            display_name = "Unknown"
        title = _text(position.get("title"))
        if not title:
            raise NormalizationError(f"Position {position_id!r} is missing title.")
        output_people.append(
            {
                "id": position_id,
                "name": display_name,
                "title": title,
                "manager_id": managers.get(position_id),
                "function": _text(position.get("function")) or "Unassigned",
                "kind": _kind(None, status, worker_type, bool(person)),
                "status": status.casefold(),
                "statusLabel": _text(position.get("statusLabel")),
                "worker_type": worker_type.casefold(),
                "details": details,
                "markers": markers,
                "order": _integer(position.get("sortOrder"), f"position {position_id} sortOrder"),
                "source_as_of": source_as_of,
            }
        )
    unknown_position_keys = sorted(
        position_keys
        - {
            "positionId", "personId", "title", "function", "location", "workerType",
            "status", "statusLabel", "level", "tenureYears", "compaRatio", "markers", "notes",
            "sourceAsOf", "sortOrder",
        }
    )
    return output_people, relationships, {
        "effective_dates": effective_dates,
        "organization": organization,
        "unknown_columns": unknown_position_keys,
        "sensitive_used": sorted(sensitive_used | marker_sensitive),
        "person_records": len(people_source),
    }


def normalize_source(
    source: Any,
    *,
    source_kind: str,
    source_label: str | None = None,
    source_system: str | None = None,
    connector_name: str | None = None,
    account_plane: str = "unknown",
    identity_verified: bool = False,
    retrieved_at: str | None = None,
    effective_date: str | None = None,
    allow_sensitive: Iterable[str] = (),
    allow_disconnected: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    allowed = _allowed_sensitive(allow_sensitive)
    retrieved = _iso_timestamp(retrieved_at, "retrieved_at")
    declared_effective = _iso_date(effective_date, "effective_date")
    if account_plane not in {"work", "personal", "unknown"}:
        raise NormalizationError("account_plane must be work, personal, or unknown.")
    safe_source_system = _coarse_label(source_system, "source_system")
    safe_connector = _coarse_label(connector_name, "connector_name")
    if source_kind == "canonical_json":
        if not isinstance(source, dict):
            raise NormalizationError("Canonical JSON input must be an object.")
        people, relationships, metadata = _normalize_canonical(deepcopy(source), allowed)
        organization = metadata.get("organization") or {}
        title = _text(organization.get("name")) or "Organization chart"
        scope = _text(organization.get("scope")) or None
        resolved_source_label = source_label or _text(organization.get("sourceLabel")) or None
    elif source_kind in {"flat_json", "csv"}:
        rows = source
        if isinstance(source, dict):
            rows = source.get("nodes", source.get("rows"))
        if not isinstance(rows, list):
            raise NormalizationError("Flat input must be an array or an object containing nodes or rows.")
        people, relationships, metadata = _normalize_flat(deepcopy(rows), allowed)
        title = "Organization chart"
        scope = None
        resolved_source_label = source_label
    else:
        raise NormalizationError(f"Unsupported source_kind: {source_kind!r}")

    if len(people) > 200:
        raise NormalizationError("This chart supports up to 200 people or positions. Split the roster into smaller charts.")
    if len(relationships) > 8:
        raise NormalizationError("This chart supports up to 8 matrix links. Use a separate relationship list for the rest.")
    for person in people:
        status = person["status"]
        if status not in {"filled", "open", "planned", "resigned", "other"}:
            raise NormalizationError(f"Unsupported status {status!r}. Choose filled, open, planned, resigned, or other.")
        if status == "other" and not person.get("statusLabel"):
            raise NormalizationError("The other status needs a statusLabel describing it.")
        person["headcount_impact"] = {"filled": 1, "open": 0, "planned": 0, "resigned": -1, "other": 0}[status]
    roots, component_count = _validate_graph(people, relationships, allow_disconnected)
    people = _stable_sort_people(people)
    relationships = sorted(
        relationships,
        key=lambda item: (item["from"], item["to"], item.get("type", ""), item.get("label", "")),
    )
    dates, effective_status, chart_date = _effective_summary(
        metadata.get("effective_dates") or [], declared_effective
    )
    render_payload = {
        "schema": NORMALIZED_SCHEMA,
        "title": title,
        "scope": scope,
        "as_of": chart_date,
        "as_of_status": effective_status,
        "people": people,
        "relationships": relationships,
        "provenance": {
            "source_label": resolved_source_label,
            "source_system": safe_source_system,
            "connector_name": safe_connector,
            "account_plane": account_plane,
            "identity_verified": bool(identity_verified),
            "retrieval_timestamp": retrieved,
            "effective_dates": dates,
        },
    }
    kind_counts: dict[str, int] = defaultdict(int)
    for person in people:
        kind = person.get("kind") or "unknown"
        kind_counts[kind if kind in RECEIPT_KINDS else "other"] += 1
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "source": {
            "kind": source_kind,
            "source_label_present": bool(resolved_source_label),
            "source_system": safe_source_system,
            "connector_name": safe_connector,
            "account_plane": account_plane,
            "identity_verified": bool(identity_verified),
            "retrieval_timestamp": retrieved,
            "effective_date_status": effective_status,
            "effective_dates": dates,
        },
        "mapping": {
            "input_model": "canonical" if source_kind == "canonical_json" else "flat",
            # Unknown source fields are counted rather than copied because a
            # column label can itself contain a person's name or query value.
            "unknown_field_count": len(metadata.get("unknown_columns") or []),
            "sensitive_field_categories_allowed": sorted(metadata.get("sensitive_used") or []),
        },
        "reconciliation": {
            "input_rows": len(people),
            "person_records": metadata.get("person_records"),
            "chart_nodes": len(people),
            "direct_relationships": sum(1 for person in people if person.get("manager_id")),
            "non_direct_relationships": len(relationships),
            "root_count": len(roots),
            "disconnected_component_count": component_count,
            "kind_counts": dict(sorted(kind_counts.items())),
            "unresolved_manager_references": 0,
            "omitted_rows": 0,
        },
        "privacy": {
            "contains_names": False,
            "contains_node_ids": False,
            "contains_raw_rows": False,
        },
    }
    return render_payload, receipt


def classify_capabilities(observation: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(observation, dict):
        raise NormalizationError("Capability observation must be an object.")
    surface = _coarse_label(observation.get("surface"), "surface")
    if not surface:
        raise NormalizationError("Capability observation requires a surface label.")
    observed_at = _iso_timestamp(observation.get("observed_at"), "observed_at")
    entitlement = _text(observation.get("entitlement") or "unknown").casefold()
    if entitlement not in {"confirmed", "unconfirmed", "unknown"}:
        raise NormalizationError(
            "entitlement must be confirmed, unconfirmed, or unknown; a session cannot prove absence."
        )
    exposed = observation.get("session_exposed")
    if exposed not in {True, False, None}:
        raise NormalizationError("session_exposed must be true, false, or null.")
    tools = observation.get("tools") or []
    if not isinstance(tools, list):
        raise NormalizationError("tools must be an array.")
    active: set[str] = set()
    schema_loaded_tools = 0
    for index, tool in enumerate(tools, start=1):
        if not isinstance(tool, dict):
            raise NormalizationError(f"tools[{index}] must be an object.")
        if not _text(tool.get("name")):
            raise NormalizationError(f"tools[{index}] is missing name.")
        capabilities = tool.get("capabilities") or []
        if not isinstance(capabilities, list):
            raise NormalizationError(f"tools[{index}].capabilities must be an array.")
        unknown = sorted({_text(capability) for capability in capabilities} - CAPABILITIES)
        if unknown:
            raise NormalizationError("Unknown capability tags: " + ", ".join(unknown))
        schema_loaded = tool.get("schema_loaded")
        if schema_loaded not in {True, False, None}:
            raise NormalizationError(f"tools[{index}].schema_loaded must be true, false, or null.")
        if schema_loaded is True:
            schema_loaded_tools += 1
            active.update(_text(capability) for capability in capabilities)
    if schema_loaded_tools and exposed is False:
        raise NormalizationError(
            "session_exposed=false contradicts a schema-loaded tool observation."
        )
    if schema_loaded_tools:
        l2 = "confirmed"
        l3 = "confirmed"
    elif exposed is True:
        l2 = "confirmed"
        l3 = "not_loaded"
    elif exposed is False:
        l2 = "not_exposed_this_session"
        l3 = "unknown"
    else:
        l2 = "unknown"
        l3 = "unknown"

    roster_from_search = bool(active & ROSTER_NODES) and bool(active & ROSTER_RELATIONSHIPS)
    roster_from_export = "roster_export" in active
    negative = observation.get("negative_discovery") or []
    if not isinstance(negative, list):
        raise NormalizationError("negative_discovery must be an array.")
    return {
        "schema": CAPABILITY_SCHEMA,
        "surface": surface,
        "observed_at": observed_at,
        "availability": {
            "l1_entitlement": entitlement,
            "l2_session_exposure": l2,
            "l3_schema_loaded": l3,
            "absence_proven": False,
            "negative_discovery_observations_ignored_for_absence": len(negative),
        },
        "capabilities": sorted(active),
        "readiness": {
            "identity_lookup": bool(active & IDENTITY_LOOKUP),
            "organization_dimensions": bool(active & {"departments", "locations"}),
            "roster_nodes": bool(active & ROSTER_NODES) or roster_from_export,
            "reporting_relationships": bool(active & ROSTER_RELATIONSHIPS) or roster_from_export,
            "roster_search": roster_from_search or roster_from_export,
            "vacancy_status": "vacancy_status" in active,
            "self_service_only": bool(active) and active <= SELF_SERVICE,
        },
        "decision": (
            "connector_roster_lane"
            if roster_from_search or roster_from_export
            else "portable_export_or_user_input_required"
        ),
    }


def _read_source(path: str, source_format: str) -> tuple[Any, str]:
    if path == "-":
        text = sys.stdin.read()
        if source_format == "auto":
            raise NormalizationError("--format is required when reading source data from stdin.")
    else:
        text = Path(path).read_text(encoding="utf-8-sig")
        if source_format == "auto":
            source_format = "csv" if Path(path).suffix.casefold() == ".csv" else "json"
    if source_format == "csv":
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise NormalizationError("CSV input is missing a header row.")
        rows = list(reader)
        return rows, "csv"
    try:
        source = json.loads(text)
    except json.JSONDecodeError as exc:
        raise NormalizationError(f"Invalid JSON input: {exc}") from exc
    if isinstance(source, dict) and "people" in source and "positions" in source:
        return source, "canonical_json"
    return source, "flat_json"


def _write_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise NormalizationError(f"Refusing to overwrite existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    normalize = commands.add_parser("normalize", help="Normalize CSV or JSON into planner input and a non-PII receipt.")
    normalize.add_argument("input", help="Source path, or - for stdin.")
    normalize.add_argument("--format", choices=("auto", "csv", "json"), default="auto")
    normalize.add_argument("--output", type=Path, required=True, help="New render-payload JSON path.")
    normalize.add_argument("--receipt", type=Path, required=True, help="New non-PII receipt JSON path.")
    normalize.add_argument("--source-label")
    normalize.add_argument("--source-system")
    normalize.add_argument("--connector-name")
    normalize.add_argument("--account-plane", choices=("work", "personal", "unknown"), default="unknown")
    normalize.add_argument("--identity-verified", action="store_true")
    normalize.add_argument("--retrieved-at")
    normalize.add_argument("--effective-date")
    normalize.add_argument("--allow-sensitive", action="append", default=[])
    normalize.add_argument("--allow-disconnected", action="store_true")
    classify = commands.add_parser("classify-capabilities", help="Classify schema-loaded connector capabilities from a JSON observation.")
    classify.add_argument("input", help="Observation JSON path, or - for stdin.")
    classify.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "normalize":
            if args.output.resolve() == args.receipt.resolve():
                raise NormalizationError("Render output and receipt must use distinct paths.")
            source, source_kind = _read_source(args.input, args.format)
            render, receipt = normalize_source(
                source,
                source_kind=source_kind,
                source_label=args.source_label,
                source_system=args.source_system,
                connector_name=args.connector_name,
                account_plane=args.account_plane,
                identity_verified=args.identity_verified,
                retrieved_at=args.retrieved_at,
                effective_date=args.effective_date,
                allow_sensitive=args.allow_sensitive,
                allow_disconnected=args.allow_disconnected,
            )
            if args.output.exists() or args.receipt.exists():
                existing = args.output if args.output.exists() else args.receipt
                raise NormalizationError(f"Refusing to overwrite existing output: {existing}")
            _write_json(args.output, render)
            try:
                _write_json(args.receipt, receipt)
            except Exception:
                args.output.unlink(missing_ok=True)
                raise
            print(json.dumps({"valid": True, "output": str(args.output), "receipt": str(args.receipt)}, sort_keys=True))
        else:
            if args.input == "-":
                observation = json.load(sys.stdin)
            else:
                observation = json.loads(Path(args.input).read_text(encoding="utf-8"))
            result = classify_capabilities(observation)
            if args.output:
                _write_json(args.output, result)
            else:
                print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (NormalizationError, OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        sys.stderr.write(f"normalize-org-chart: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
