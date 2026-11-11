#!/usr/bin/env python3
"""Deterministic, dependency-free org-chart geometry planner.

The planner deliberately separates roster semantics from rendering.  It emits
portable JSON geometry in slide inches; a presentation implementation can map
the stable names to native PowerPoint or Google Slides shapes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import defaultdict, deque
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


VERSION = "1.3.0"
MODES = (
    "compact_hierarchy",
    "leadership_bands",
    "functional_columns",
    "matrix_relationships",
    "enterprise_overview",
)
DEFAULT_CANVAS = {"width": 13.333, "height": 7.5}
MARGIN = 0.42
GAP = 0.14
EPSILON = 1e-6
CARDINAL_SITES = ("top", "left", "bottom", "right")
GOOGLE_SLIDES_SITE_INDEX = {"top": 0, "left": 1, "bottom": 2, "right": 3}
GOOGLE_SLIDES_PORTABLE_CATEGORY = "STRAIGHT"
GOOGLE_OBJECT_ID = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_:-]{4,49}$")


class GeometryError(ValueError):
    """Raised for input that cannot be laid out safely."""


def _read_json(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(value: dict[str, Any], path: str | None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path:
        Path(path).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _number(value: float) -> float:
    return round(float(value), 4)


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return cleaned[:30] or "item"


def stable_name(kind: str, identity: str, suffix: str = "") -> str:
    raw = f"{kind}|{identity}|{suffix}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    parts = ["org", _slug(kind), _slug(identity)]
    if suffix:
        parts.append(_slug(suffix))
    return "-".join(parts)[:74] + "-" + digest


def google_object_id(kind: str, identity: str, suffix: str = "") -> str:
    """Return a deterministic Google Slides-safe object ID (5..50 chars)."""
    raw = f"{kind}|{identity}|{suffix}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
    label = re.sub(r"[^a-z0-9_]+", "_", f"{kind}_{identity}".casefold()).strip("_")
    return f"org_{label[:32]}_{digest}"


def _canonical_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _rect(x: float, y: float, w: float, h: float) -> dict[str, float]:
    return {"x": _number(x), "y": _number(y), "w": _number(w), "h": _number(h)}


def _intersects(a: dict[str, float], b: dict[str, float]) -> bool:
    return not (
        a["x"] + a["w"] <= b["x"] + EPSILON
        or b["x"] + b["w"] <= a["x"] + EPSILON
        or a["y"] + a["h"] <= b["y"] + EPSILON
        or b["y"] + b["h"] <= a["y"] + EPSILON
    )


def _site_point(element: dict[str, Any], site: str) -> dict[str, float]:
    box = element["box"]
    if site == "top":
        return {"x": _number(box["x"] + box["w"] / 2), "y": _number(box["y"])}
    if site == "left":
        return {"x": _number(box["x"]), "y": _number(box["y"] + box["h"] / 2)}
    if site == "bottom":
        return {"x": _number(box["x"] + box["w"] / 2), "y": _number(box["y"] + box["h"])}
    if site == "right":
        return {"x": _number(box["x"] + box["w"]), "y": _number(box["y"] + box["h"] / 2)}
    raise GeometryError(f"Unknown cardinal connection site {site!r}.")


def _segment_intersects_rect(segment: dict[str, float], rect: dict[str, float]) -> bool:
    """Return whether an orthogonal segment touches or crosses a rectangle."""
    x1, y1 = float(segment["x1"]), float(segment["y1"])
    x2, y2 = float(segment["x2"]), float(segment["y2"])
    left, right = rect["x"], rect["x"] + rect["w"]
    top, bottom = rect["y"], rect["y"] + rect["h"]
    if abs(x1 - x2) <= EPSILON:
        return (
            left - EPSILON <= x1 <= right + EPSILON
            and max(min(y1, y2), top) <= min(max(y1, y2), bottom) + EPSILON
        )
    if abs(y1 - y2) <= EPSILON:
        return (
            top - EPSILON <= y1 <= bottom + EPSILON
            and max(min(x1, x2), left) <= min(max(x1, x2), right) + EPSILON
        )
    return True


def _segment_intersects_rect_any(segment: dict[str, float], rect: dict[str, float]) -> bool:
    """Return whether a straight segment of any angle intersects a rectangle."""
    x1, y1 = float(segment["x1"]), float(segment["y1"])
    x2, y2 = float(segment["x2"]), float(segment["y2"])
    left, right = rect["x"], rect["x"] + rect["w"]
    top, bottom = rect["y"], rect["y"] + rect["h"]
    dx, dy = x2 - x1, y2 - y1
    enter, leave = 0.0, 1.0
    for coefficient, distance in (
        (-dx, x1 - left),
        (dx, right - x1),
        (-dy, y1 - top),
        (dy, bottom - y1),
    ):
        if abs(coefficient) <= EPSILON:
            if distance < -EPSILON:
                return False
            continue
        ratio = distance / coefficient
        if coefficient < 0:
            enter = max(enter, ratio)
        else:
            leave = min(leave, ratio)
        if enter > leave + EPSILON:
            return False
    return True


def _connector_hits_non_endpoint_card(
    connector: dict[str, Any], elements: Iterable[dict[str, Any]]
) -> bool:
    endpoints = {connector.get("from"), connector.get("to")}
    for element in elements:
        if element.get("collision_class") != "card" or element.get("stable_name") in endpoints:
            continue
        box = _rect_from_element(element)
        if box and any(_segment_intersects_rect(segment, box) for segment in connector.get("segments") or []):
            return True
    return False


def _google_straight_connector_hits_non_endpoint_card(
    connector: dict[str, Any], elements: Iterable[dict[str, Any]]
) -> bool:
    """Validate the actual Google portable default, not the PPTX elbow route."""
    by_name = {
        element.get("stable_name"): element
        for element in elements
        if element.get("collision_class") == "card"
    }
    source = by_name.get(connector.get("from"))
    target = by_name.get(connector.get("to"))
    if source is None or target is None:
        return True
    start = _site_point(source, connector.get("from_site"))
    end = _site_point(target, connector.get("to_site"))
    segment = {"x1": start["x"], "y1": start["y"], "x2": end["x"], "y2": end["y"]}
    endpoints = {connector.get("from"), connector.get("to")}
    for name, element in by_name.items():
        if name in endpoints:
            continue
        box = _rect_from_element(element)
        if box and _segment_intersects_rect_any(segment, box):
            return True
    return False


def _validate_input(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(data, dict):
        raise GeometryError("Input must be a JSON object.")
    people = data.get("people")
    if not isinstance(people, list) or not people:
        raise GeometryError("Input must contain a non-empty 'people' array.")
    if len(people) > 200:
        raise GeometryError("This chart supports up to 200 people or positions. Split the roster into smaller charts.")
    if len(data.get("relationships") or []) > 8:
        raise GeometryError("This chart supports up to 8 matrix links. Use a separate relationship list for the rest.")
    by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(people):
        if not isinstance(raw, dict):
            raise GeometryError(f"people[{index}] must be an object.")
        node_id = str(raw.get("id", "")).strip()
        if not node_id:
            raise GeometryError(f"people[{index}] is missing a stable id.")
        if node_id in by_id:
            raise GeometryError(f"Duplicate person id: {node_id}")
        if not str(raw.get("name", "")).strip():
            raise GeometryError(f"Person {node_id} is missing name.")
        if not str(raw.get("title", "")).strip():
            raise GeometryError(f"Person {node_id} is missing title.")
        person = deepcopy(raw)
        person["id"] = node_id
        person["manager_id"] = (
            str(raw["manager_id"]).strip() if raw.get("manager_id") not in (None, "") else None
        )
        person["function"] = str(raw.get("function") or "Unassigned").strip()
        by_id[node_id] = person
    for person in by_id.values():
        manager_id = person["manager_id"]
        if manager_id and manager_id not in by_id:
            raise GeometryError(f"Unknown manager_id {manager_id!r} for {person['id']!r}.")
        if manager_id == person["id"]:
            raise GeometryError(f"Person {person['id']!r} cannot manage itself.")

    # Kahn traversal proves that the reporting graph is acyclic.
    indegree = {node_id: 0 for node_id in by_id}
    children: dict[str, list[str]] = defaultdict(list)
    for person in by_id.values():
        if person["manager_id"]:
            indegree[person["id"]] += 1
            children[person["manager_id"]].append(person["id"])
    queue = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for child in sorted(children[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if visited != len(by_id):
        raise GeometryError("The manager_id graph contains a cycle.")
    return by_id


def _ordered_people(by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        by_id.values(),
        key=lambda person: (
            person.get("order") if person.get("order") is not None else 10_000,
            person.get("function", "").casefold(),
            person.get("title", "").casefold(),
            person.get("name", "").casefold(),
            person["id"],
        ),
    )


def _children(by_id: dict[str, dict[str, Any]]) -> dict[str | None, list[dict[str, Any]]]:
    result: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    for person in _ordered_people(by_id):
        result[person["manager_id"]].append(person)
    return result


def _depths(by_id: dict[str, dict[str, Any]]) -> dict[str, int]:
    children = _children(by_id)
    result: dict[str, int] = {}
    queue: deque[tuple[dict[str, Any], int]] = deque((root, 0) for root in children[None])
    while queue:
        person, depth = queue.popleft()
        result[person["id"]] = depth
        for child in children[person["id"]]:
            queue.append((child, depth + 1))
    return result


def recommend(data: dict[str, Any]) -> dict[str, Any]:
    by_id = _validate_input(data)
    people = _ordered_people(by_id)
    roots = [person for person in people if not person["manager_id"]]
    direct_reports = sum(1 for person in people if person["manager_id"] in {r["id"] for r in roots})
    function_count = len({person["function"] for person in people})
    relationship_count = len(data.get("relationships") or [])
    max_depth = max(_depths(by_id).values(), default=0)

    if relationship_count:
        preferred = "matrix_relationships"
        rationale = "The input contains explicit non-hierarchical relationships."
    elif len(roots) == 1 and direct_reports > 8:
        preferred = "compact_hierarchy"
        rationale = "A wide team stays clearest as a simple tree; extra branches continue on their own pages with reporting lines kept."
    elif len(people) >= 35:
        preferred = "enterprise_overview"
        rationale = "The roster is too large for a single readable chart."
    elif len(people) <= 14 and max_depth <= 1:
        preferred = "leadership_bands"
        rationale = "The roster is a shallow leadership cohort."
    elif function_count >= 4 and (max_depth >= 3 or len(people) >= 12):
        preferred = "functional_columns"
        rationale = "Function grouping will clarify uneven branch depth."
    else:
        preferred = "compact_hierarchy"
        rationale = "The roster fits a conventional manager hierarchy."

    return {
        "version": VERSION,
        "recommended_mode": preferred,
        "rationale": rationale,
        "facts": {
            "people": len(people),
            "root_count": len(roots),
            "root_direct_reports": direct_reports,
            "function_count": function_count,
            "max_depth": max_depth,
            "matrix_relationships": relationship_count,
        },
        "options": [
            {
                "mode": mode,
                "single_page_likelihood": _single_page_likelihood(mode, len(people), max_depth, function_count, relationship_count),
            }
            for mode in MODES
        ],
    }


def _single_page_likelihood(mode: str, count: int, depth: int, functions: int, links: int) -> str:
    if mode == "compact_hierarchy":
        return "likely" if count <= 26 and depth <= 4 else "split-recommended"
    if mode == "leadership_bands":
        return "likely" if count <= 14 else "split-required"
    if mode == "functional_columns":
        return "likely" if count <= 40 and functions <= 6 else "split-recommended"
    if mode == "matrix_relationships":
        return "likely" if count <= 24 and links <= 8 else "split-required"
    return "overview-and-drilldowns"


def _reserved_zones(data: dict[str, Any], canvas: dict[str, float]) -> tuple[list[dict[str, Any]], dict[str, float]]:
    options = data.get("options") or {}
    zones: list[dict[str, Any]] = [
        {"name": "header", "purpose": "title", **_rect(MARGIN, 0.22, canvas["width"] - 2 * MARGIN, 0.58)},
    ]
    left = MARGIN
    top = 0.92
    right = canvas["width"] - MARGIN
    bottom = canvas["height"] - 0.32
    if options.get("include_legend", True) or data.get("legend_items"):
        legend_h = 0.66
        zones.append(
            {
                "name": "legend",
                "purpose": "legend",
                **_rect(left, bottom - legend_h, right - left, legend_h),
            }
        )
        bottom -= legend_h + 0.12
    if options.get("include_insights") or data.get("insights"):
        insight_w = 2.28
        zones.append(
            {
                "name": "insights",
                "purpose": "at-a-glance insights",
                **_rect(right - insight_w, top, insight_w, bottom - top),
            }
        )
        right -= insight_w + 0.22
    return zones, _rect(left, top, right - left, bottom - top)


def _new_page(data: dict[str, Any], index: int, section: str, title: str) -> dict[str, Any]:
    canvas = _canvas(data)
    zones, content = _reserved_zones(data, canvas)
    return {
        "id": stable_name("page", section, str(index)),
        "index": index,
        "section": section,
        "title": title,
        "canvas": canvas,
        "reserved_zones": zones,
        "content_bounds": content,
        "elements": [],
        "connectors": [],
        "alignment_groups": [],
        "split_reason": None,
    }


def _canvas(data: dict[str, Any]) -> dict[str, float]:
    supplied = (data.get("options") or {}).get("canvas") or {}
    width = float(supplied.get("width", DEFAULT_CANVAS["width"]))
    height = float(supplied.get("height", DEFAULT_CANVAS["height"]))
    if width < 8 or height < 5:
        raise GeometryError("Canvas must be at least 8 by 5 inches.")
    return {"width": _number(width), "height": _number(height)}


def _card(person: dict[str, Any], box: dict[str, float], page_id: str, role: str = "person_card") -> dict[str, Any]:
    return {
        "stable_name": stable_name("card", person["id"], page_id),
        "google_slides_object_id": google_object_id("card", person["id"], page_id),
        "type": role,
        "collision_class": "card",
        "node_id": person["id"],
        "box": box,
        "text_align": "left",
        "data": {
            "name": person["name"],
            "title": person["title"],
            "function": person["function"],
            "kind": person.get("kind", "person"),
            "status": person.get("status", "filled"),
            "statusLabel": person.get("statusLabel", ""),
            "context": person.get("context", False),
            "details": person.get("details", []),
            "markers": person.get("markers", []),
        },
    }


def _summary_card(identity: str, title: str, subtitle: str, box: dict[str, float], page_id: str) -> dict[str, Any]:
    return {
        "stable_name": stable_name("summary", identity, page_id),
        "google_slides_object_id": google_object_id("summary", identity, page_id),
        "type": "group_summary_card",
        "collision_class": "card",
        "group_id": identity,
        "box": box,
        "text_align": "left",
        "data": {"name": title, "title": subtitle},
    }


def _direct_connector(source: dict[str, Any], target: dict[str, Any], page_id: str, lane_offset: float = 0.0) -> dict[str, Any]:
    start = _site_point(source, "bottom")
    end = _site_point(target, "top")
    if end["y"] <= start["y"] + EPSILON:
        raise GeometryError("Direct-report connector requires the manager card above the report card.")
    bus_y = _number(start["y"] + max(0.06, (end["y"] - start["y"]) / 2) + lane_offset)
    identity = f"{source.get('node_id', source.get('group_id'))}-{target.get('node_id', target.get('group_id'))}"
    return {
        "stable_name": stable_name("connector", identity, page_id),
        "google_slides_object_id": google_object_id("connector", identity, page_id),
        "type": "direct_report",
        "line_style": "solid",
        "from": source["stable_name"],
        "to": target["stable_name"],
        "from_site": "bottom",
        "to_site": "top",
        "google_slides_from_site_index": GOOGLE_SLIDES_SITE_INDEX["bottom"],
        "google_slides_to_site_index": GOOGLE_SLIDES_SITE_INDEX["top"],
        "google_slides_category": GOOGLE_SLIDES_PORTABLE_CATEGORY,
        "google_slides_reroute_policy": "disabled-unless-deck-canary",
        "native_category": "BENT",
        "pptx_native_category": "BENT",
        "reroute_safe": True,
        "routing": "orthogonal-bus",
        "segments": [
            {"x1": start["x"], "y1": start["y"], "x2": start["x"], "y2": bus_y},
            {"x1": start["x"], "y1": bus_y, "x2": end["x"], "y2": bus_y},
            {"x1": end["x"], "y1": bus_y, "x2": end["x"], "y2": end["y"]},
        ],
    }


def _matrix_connector(source: dict[str, Any], target: dict[str, Any], page: dict[str, Any], relation_index: int) -> dict[str, Any]:
    content = page["content_bounds"]
    candidates = []
    if abs(source["box"]["y"] - target["box"]["y"]) < EPSILON:
        source_left = source["box"]["x"] < target["box"]["x"]
        candidates.append(("right" if source_left else "left", "left" if source_left else "right", None, "side-to-side"))
    lane_y = min(source["box"]["y"], target["box"]["y"]) - 0.08 - relation_index * 0.035
    if lane_y >= content["y"]:
        candidates.append(("top", "top", lane_y, "top-lane"))
    candidates.extend([(site, site, x, "external-lane") for site, x in (
        ("right", content["x"] + content["w"] - 0.05 - relation_index * 0.035),
        ("left", content["x"] + 0.04 + relation_index * 0.035))])
    identity = f"{source['node_id']}-{target['node_id']}"
    for start_site, end_site, lane, routing in candidates:
        start, end = _site_point(source, start_site), _site_point(target, end_site)
        if routing == "side-to-side":
            segments = [{"x1": start["x"], "y1": start["y"], "x2": end["x"], "y2": end["y"]}]
        elif routing == "top-lane":
            segments = [{"x1": start["x"], "y1": start["y"], "x2": start["x"], "y2": lane}, {"x1": start["x"], "y1": lane, "x2": end["x"], "y2": lane}, {"x1": end["x"], "y1": lane, "x2": end["x"], "y2": end["y"]}]
        else:
            if (start_site == "right" and lane <= max(start["x"], end["x"])) or (start_site == "left" and lane >= min(start["x"], end["x"])):
                continue
            segments = [{"x1": start["x"], "y1": start["y"], "x2": lane, "y2": start["y"]}, {"x1": lane, "y1": start["y"], "x2": lane, "y2": end["y"]}, {"x1": lane, "y1": end["y"], "x2": end["x"], "y2": end["y"]}]
        connector = {"from": source["stable_name"], "to": target["stable_name"], "segments": segments}
        if not _connector_hits_non_endpoint_card(connector, page["elements"]):
            break
    else:
        return None
    identity = f"{source['node_id']}-{target['node_id']}"
    return {
        "stable_name": stable_name("matrix-connector", identity, page["id"]),
        "google_slides_object_id": google_object_id("matrix-connector", identity, page["id"]),
        "type": "matrix_relationship",
        "line_style": "dotted",
        "from": source["stable_name"],
        "to": target["stable_name"],
        "from_site": start_site,
        "to_site": end_site,
        "google_slides_from_site_index": GOOGLE_SLIDES_SITE_INDEX[start_site],
        "google_slides_to_site_index": GOOGLE_SLIDES_SITE_INDEX[end_site],
        "google_slides_category": GOOGLE_SLIDES_PORTABLE_CATEGORY,
        "google_slides_reroute_policy": "disabled-unless-deck-canary",
        "native_category": "STRAIGHT" if routing == "side-to-side" else "BENT",
        "pptx_native_category": "STRAIGHT" if routing == "side-to-side" else "BENT",
        "reroute_safe": True,
        "routing": routing,
        "segments": segments,
    }


def _add_row_alignment(page: dict[str, Any], elements: Iterable[dict[str, Any]], row_id: str) -> None:
    members = [element["stable_name"] for element in elements]
    if len(members) > 1:
        page["alignment_groups"].append(
            {
                "stable_name": stable_name("alignment", row_id, page["id"]),
                "axis": "y",
                "edge": "top",
                "members": members,
                "equal_size": "height",
                "distribution_axis": "x",
                "tolerance": 0.002,
            }
        )


def _layout_levels(data: dict[str, Any], page: dict[str, Any], people: list[dict[str, Any]], leadership: bool = False) -> None:
    subset = {person["id"]: person for person in people}
    depth: dict[str, int] = {}
    ordered = _ordered_people(subset)
    unresolved = list(ordered)
    while unresolved:
        next_unresolved = []
        advanced = False
        for person in unresolved:
            manager_id = person["manager_id"]
            if not manager_id or manager_id not in subset:
                depth[person["id"]] = 0
                advanced = True
            elif manager_id in depth:
                depth[person["id"]] = depth[manager_id] + 1
                advanced = True
            else:
                next_unresolved.append(person)
        if not advanced:
            raise GeometryError("Could not resolve hierarchy depth for page subset.")
        unresolved = next_unresolved
    levels: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for person in ordered:
        levels[depth[person["id"]]].append(person)
    content = page["content_bounds"]
    level_count = len(levels)
    vertical_gap = min(0.3, content["h"] / (2 * max(level_count, 1))) if leadership else 0.3
    card_h = min(0.72, (content["h"] - (level_count - 1) * vertical_gap) / max(level_count, 1)) if leadership else min(0.72, max(0.48, (content["h"] - (level_count - 1) * vertical_gap) / max(level_count, 1)))
    total_h = level_count * card_h + max(0, level_count - 1) * vertical_gap
    top = content["y"] + max(0.0, (content["h"] - total_h) / 2)
    # Allocate contiguous horizontal space to each subtree, then center each
    # parent over the span of its immediate children.
    children: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    for person in ordered:
        parent = person["manager_id"] if person["manager_id"] in subset else None
        children[parent].append(person)
    def width(person: dict[str, Any]) -> int:
        return max(1, sum(width(child) for child in children[person["id"]]))
    roots = children[None]
    units = sum(width(root) for root in roots)
    card_w = min(2.0, (content["w"] - GAP * (units - 1)) / units)
    if card_w < 0.72:
        raise GeometryError("Hierarchy row is too wide; split the chart before rendering.")
    pitch = card_w + GAP
    positions: dict[str, float] = {}
    def place(person: dict[str, Any], left: float) -> float:
        descendants = children[person["id"]]
        if not descendants:
            center = left + card_w / 2
        else:
            centers = []
            for child in descendants:
                centers.append(place(child, left))
                left += width(child) * pitch
            center = (centers[0] + centers[-1]) / 2
        positions[person["id"]] = center
        return center
    left = content["x"] + (content["w"] - (units * pitch - GAP)) / 2
    for root in roots:
        place(root, left)
        left += width(root) * pitch
    created: dict[str, dict[str, Any]] = {}
    for level_index in sorted(levels):
        row_elements = []
        for person in levels[level_index]:
            element = _card(person, _rect(positions[person["id"]] - card_w / 2, top + level_index * (card_h + vertical_gap), card_w, card_h), page["id"])
            page["elements"].append(element)
            row_elements.append(element)
            created[person["id"]] = element
        _add_row_alignment(page, row_elements, f"level-{level_index}")
        if len(row_elements) > 1:
            page["alignment_groups"][-1].pop("distribution_axis", None)
    for person in ordered:
        manager_id = person["manager_id"]
        if manager_id in created:
            page["connectors"].append(_direct_connector(created[manager_id], created[person["id"]], page["id"]))


def _layout_roster_grid(page: dict[str, Any], people: list[dict[str, Any]], columns: int = 5) -> None:
    """Lay out a bounded drilldown roster when a hierarchy row would be too wide."""
    content = page["content_bounds"]
    columns = min(columns, max(1, len(people)))
    rows = math.ceil(len(people) / columns)
    card_w = (content["w"] - GAP * (columns - 1)) / columns
    card_h = min(0.82, (content["h"] - 0.22 * (rows - 1)) / rows)
    if card_w < 1.05 or card_h < 0.48:
        raise GeometryError("Roster grid exceeds readable geometry; reduce cards per drilldown.")
    row_elements: dict[int, list[dict[str, Any]]] = defaultdict(list)
    created: dict[str, dict[str, Any]] = {}
    for index, person in enumerate(people):
        row, column = divmod(index, columns)
        element = _card(
            person,
            _rect(
                content["x"] + column * (card_w + GAP),
                content["y"] + row * (card_h + 0.22),
                card_w,
                card_h,
            ),
            page["id"],
        )
        page["elements"].append(element)
        row_elements[row].append(element)
        created[person["id"]] = element
    for row, elements in row_elements.items():
        _add_row_alignment(page, elements, f"roster-row-{row}")
    # Draw only relationships whose vertical geometry supports an unobstructed
    # bus. Same-row relationships remain encoded in the data and are better
    # handled by the rendering layer's optional relationship table.
    for person in people:
        manager = created.get(person.get("manager_id"))
        child = created.get(person["id"])
        if manager and child and manager["box"]["y"] < child["box"]["y"]:
            connector = _direct_connector(manager, child, page["id"])
            if not _connector_hits_non_endpoint_card(connector, page["elements"]):
                page["connectors"].append(connector)


def _branch_members(root_id: str, children: dict[str | None, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    queue: deque[dict[str, Any]] = deque(children[root_id])
    while queue:
        person = queue.popleft()
        result.append(person)
        queue.extend(children[person["id"]])
    return result


def _chunk(items: list[Any], size: int) -> list[list[Any]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def _supports_level_layout(people: list[dict[str, Any]]) -> bool:
    subset = {person["id"]: person for person in people}
    depth: dict[str, int] = {}
    unresolved = list(_ordered_people(subset))
    while unresolved:
        next_unresolved = []
        advanced = False
        for person in unresolved:
            manager_id = person["manager_id"]
            if not manager_id or manager_id not in subset:
                depth[person["id"]] = 0
                advanced = True
            elif manager_id in depth:
                depth[person["id"]] = depth[manager_id] + 1
                advanced = True
            else:
                next_unresolved.append(person)
        if not advanced:
            return False
        unresolved = next_unresolved
    widths = [sum(1 for value in depth.values() if value == level) for level in set(depth.values())]
    return max(widths, default=0) <= 8 and max(depth.values(), default=0) <= 6


def _compact_pages(data: dict[str, Any], by_id: dict[str, dict[str, Any]], mode: str = "compact_hierarchy") -> list[dict[str, Any]]:
    people = _ordered_people(by_id)
    depth_map = _depths(by_id)
    max_width = max((sum(1 for value in depth_map.values() if value == depth) for depth in set(depth_map.values())), default=0)
    if len(people) <= 26 and max(depth_map.values(), default=0) <= 4 and max_width <= 8:
        page = _new_page(data, 1, mode, data.get("title") or "Organization chart")
        _layout_levels(data, page, people)
        return [page]

    children = _children(by_id)
    roots = children[None]
    page = _new_page(data, 1, f"{mode}-overview", data.get("title") or "Organization overview")
    content = page["content_bounds"]
    summaries: list[tuple[str, str, int]] = []
    for root in roots:
        branches = children[root["id"]] or [root]
        for branch in branches:
            count = 1 + len(_branch_members(branch["id"], children))
            summaries.append((branch["id"], branch["name"], count))
    columns = min(4, max(1, len(summaries)))
    rows = math.ceil(len(summaries) / columns)
    card_w = (content["w"] - GAP * (columns - 1)) / columns
    card_h = min(1.05, (content["h"] - GAP * (rows - 1)) / max(rows, 1))
    overview_elements = []
    for index, (branch_id, name, count) in enumerate(summaries):
        row, column = divmod(index, columns)
        element = _summary_card(branch_id, name, f"{count} {'position' if count == 1 else 'positions'} · detail follows", _rect(content["x"] + column * (card_w + GAP), content["y"] + row * (card_h + GAP), card_w, card_h), page["id"])
        page["elements"].append(element)
        overview_elements.append(element)
    for row in range(rows):
        _add_row_alignment(page, overview_elements[row * columns:(row + 1) * columns], f"overview-row-{row}")
    page["split_reason"] = "Compact hierarchy exceeded 26 positions, four layers, or eight cards in one row."
    pages = [page]
    groups: list[list[dict[str, Any]]] = []
    pending: list[dict[str, Any]] = []
    for branch_id, name, _ in summaries:
        branch_root = by_id[branch_id]
        members = [branch_root] + _branch_members(branch_id, children)
        parent = by_id.get(branch_root["manager_id"])
        context = [parent] if parent else []
        candidate = pending + [person for person in context + members if person not in pending]
        # The layout uses leaf spans, which can exceed the widest level.
        def fits(group: list[dict[str, Any]]) -> bool:
            if len(group) > 26 or not _supports_level_layout(group):
                return False
            subset = {person["id"] for person in group}
            leaf_count = sum(not any(child["id"] in subset for child in children[person["id"]]) for person in group)
            return leaf_count <= 8 and max(_depths({person["id"]: {**person, "manager_id": person["manager_id"] if person["manager_id"] in subset else None} for person in group}).values(), default=0) <= 4
        if pending and not fits(candidate):
            groups.append(pending)
            pending = []
        candidate = context + members
        if not fits(candidate):
            for chunk in _chunk(members, 22):
                groups.append(chunk)
        else:
            pending = pending + [person for person in candidate if person not in pending]
    if pending:
        groups.append(pending)
    for group in groups:
        detail = _new_page(data, len(pages) + 1, f"branch-{group[0]['id']}", "Organization detail")
        if _supports_level_layout(group):
            _layout_levels(data, detail, group)
        else:
            _layout_roster_grid(detail, group)
        detail["split_reason"] = "Branch drilldown generated to preserve readable card geometry."
        pages.append(detail)
    return pages


def _leadership_pages(data: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    depth = _depths(by_id)
    people = sorted(
        _ordered_people(by_id),
        key=lambda person: (
            depth[person["id"]],
            person.get("order") if person.get("order") is not None else 10_000,
            person.get("function", "").casefold(),
            person.get("title", "").casefold(),
            person["id"],
        ),
    )
    pages: list[dict[str, Any]] = []
    for page_group in _chunk(people, 14):
        page = _new_page(data, len(pages) + 1, "leadership-bands", data.get("title") or "Leadership")
        _layout_levels(data, page, page_group, leadership=True)
        if len(people) > 14:
            page["split_reason"] = "Leadership bands allow at most 14 readable cards per page."
        pages.append(page)
    return pages


def _function_groups(by_id: dict[str, dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for person in _ordered_people(by_id):
        groups[person["function"]].append(person)
    return sorted(groups.items(), key=lambda item: item[0].casefold())


def _functional_pages(data: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    groups = _function_groups(by_id)
    panels: list[tuple[str, list[dict[str, Any]], int]] = []
    for function, members in groups:
        for part, member_chunk in enumerate(_chunk(members, 7), start=1):
            panels.append((function, member_chunk, part))
    pages: list[dict[str, Any]] = []
    for panel_group in _chunk(panels, 5):
        page = _new_page(data, len(pages) + 1, "functional-columns", data.get("title") or "Organization by function")
        content = page["content_bounds"]
        columns = len(panel_group)
        panel_gap = 0.18
        panel_w = (content["w"] - panel_gap * (columns - 1)) / columns
        card_h = min(0.66, (content["h"] - 0.43 - GAP * 6) / 7)
        for column, (function, members, part) in enumerate(panel_group):
            x = content["x"] + column * (panel_w + panel_gap)
            panel_name = stable_name("function-panel", function, f"{page['id']}-{part}")
            page["elements"].append(
                {
                    "stable_name": panel_name,
                    "type": "function_panel",
                    "collision_class": "container",
                    "group_id": function,
                    "box": _rect(x, content["y"], panel_w, content["h"]),
                    "data": {"name": function, "continuation": part > 1},
                }
            )
            column_cards = []
            for row, person in enumerate(members):
                element = _card(person, _rect(x + 0.08, content["y"] + 0.43 + row * (card_h + GAP), panel_w - 0.16, card_h), page["id"])
                page["elements"].append(element)
                column_cards.append(element)
            page["alignment_groups"].append(
                {
                    "stable_name": stable_name("alignment", function, page["id"] if part == 1 else f"{page['id']}-part-{part}"),
                    "axis": "x",
                    "edge": "left",
                    "members": [card["stable_name"] for card in column_cards],
                    "equal_size": "width",
                    "distribution_axis": "y",
                    "tolerance": 0.002,
                }
            )
        if len(panels) > 5:
            page["split_reason"] = "Functional columns allow five functions and seven cards per column."
        pages.append(page)
    return pages


def _matrix_pages(data: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    people = _ordered_people(by_id)
    relationships = data.get("relationships") or []
    for index, relation in enumerate(relationships):
        if not isinstance(relation, dict):
            raise GeometryError(f"relationships[{index}] must be an object.")
        if relation.get("from") not in by_id or relation.get("to") not in by_id:
            raise GeometryError(f"relationships[{index}] refers to an unknown person id.")
        if relation.get("from") == relation.get("to"):
            raise GeometryError(f"relationships[{index}] cannot be a self-link.")
    if len(people) > 24:
        pages = _functional_pages(data, by_id)
        for page in pages:
            page["section"] = "matrix-sections"
            page["split_reason"] = "Matrix charts allow at most 24 positions; sections preserve readable geometry."
    else:
        pages = _compact_pages(data, by_id, mode="matrix_relationships")
    element_lookup: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for page in pages:
        for element in page["elements"]:
            if element.get("node_id"):
                element_lookup[element["node_id"]] = (page, element)
    drawn = 0
    undrawn = []
    for relation in relationships:
        source_info = element_lookup.get(relation["from"])
        target_info = element_lookup.get(relation["to"])
        if not source_info or not target_info or source_info[0]["id"] != target_info[0]["id"] or drawn >= 8:
            undrawn.append(relation)
            continue
        page, source = source_info
        connector = _matrix_connector(source, target_info[1], page, drawn)
        if connector is None:
            undrawn.append(relation)
            continue
        page["connectors"].append(connector)
        drawn += 1
    if undrawn:
        table_page = _new_page(data, len(pages) + 1, "relationship-table", "Matrix relationships")
        content = table_page["content_bounds"]
        table_page["elements"].append(
            {
                "stable_name": stable_name("relationship-table", data.get("title", "org"), table_page["id"]),
                "type": "relationship_table",
                "collision_class": "annotation",
                "box": content,
                "data": {"rows": [{**relation, "from_display": "\n".join(filter(None, (by_id[relation["from"]].get("name") or relation["from"], by_id[relation["from"]].get("title")))), "to_display": "\n".join(filter(None, (by_id[relation["to"]].get("name") or relation["to"], by_id[relation["to"]].get("title"))))} for relation in undrawn], "reason": f"{len(undrawn)} link(s) cross pages or could not be drawn without crossing a card"},
            }
        )
        table_page["split_reason"] = "Relationship table prevents connector clutter and preserves every cross-link."
        pages.append(table_page)
    return pages


TEAM_PAGE_UNITS = 8
TEAM_PAGE_ROWS = 5


def _preorder(by_id: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Return each person's position in a depth-first walk of the whole org."""
    children = _children(by_id)
    order: dict[str, int] = {}
    stack = list(reversed(children[None]))
    while stack:
        person = stack.pop()
        order[person["id"]] = len(order)
        stack.extend(reversed(children[person["id"]]))
    return order


def _pack_team_pages(members: list[dict[str, Any]], by_id: dict[str, dict[str, Any]], order: dict[str, int]) -> list[list[str]]:
    """Split one team into pages that keep its reporting lines drawable.

    Each page holds at most ``TEAM_PAGE_UNITS`` leaf columns and
    ``TEAM_PAGE_ROWS`` rows, counting one row for context cards. When a
    branch does not fit, the manager stays on the page and the branch's
    reports continue on a later page under a context card for that manager.
    """
    member_ids = {person["id"] for person in members}
    kids: dict[str, list[str]] = defaultdict(list)
    for person_id in sorted(member_ids, key=order.__getitem__):
        manager_id = by_id[person_id]["manager_id"]
        if manager_id in member_ids:
            kids[manager_id].append(person_id)
    roots = sorted(
        (person_id for person_id in member_ids if by_id[person_id]["manager_id"] not in member_ids),
        key=lambda person_id: (order.get(by_id[person_id]["manager_id"], -1), order[person_id]),
    )
    pages: list[dict[str, Any]] = []
    queue: deque[list[str]] = deque([roots])
    while queue:
        forest = queue.popleft()
        rows = TEAM_PAGE_ROWS - (1 if any(by_id[root]["manager_id"] for root in forest) else 0)
        moved: dict[str, list[str]] = {}

        def clear_below(node: str) -> None:
            stack = [node]
            while stack:
                current = stack.pop()
                moved.pop(current, None)
                stack.extend(kids[current])

        def measure(node: str, depth: int, is_root: bool) -> int:
            reports = kids[node]
            if not reports:
                return 1
            if depth >= rows - 1:
                moved[node] = list(reports)
                return 1
            sizes = {child: measure(child, depth + 1, False) for child in reports}
            total = sum(sizes.values())
            # Move the widest branches first; their managers stay on this page.
            for child in sorted(reports, key=lambda item: (-sizes[item], order[item])):
                if total <= TEAM_PAGE_UNITS:
                    break
                if sizes[child] > 1:
                    clear_below(child)
                    moved[child] = list(kids[child])
                    total -= sizes[child] - 1
                    sizes[child] = 1
            if total <= TEAM_PAGE_UNITS:
                return total
            if is_root:
                moved[node] = list(reports[TEAM_PAGE_UNITS:])
                return TEAM_PAGE_UNITS
            clear_below(node)
            moved[node] = list(reports)
            return 1

        sizes = [(root, measure(root, 0, True)) for root in forest]
        chunks: list[tuple[list[str], int]] = []
        for root, size in sizes:
            if not chunks or chunks[-1][1] + size > TEAM_PAGE_UNITS:
                chunks.append(([], 0))
            chunks[-1][0].append(root)
            chunks[-1] = (chunks[-1][0], chunks[-1][1] + size)
        for chunk, size in chunks:
            chunk_members: list[str] = []
            stack = list(reversed(chunk))
            while stack:
                current = stack.pop()
                chunk_members.append(current)
                away = set(moved.get(current, ()))
                stack.extend(reversed([child for child in kids[current] if child not in away]))
            # Share a page with an earlier continuation when the columns fit and
            # neither part manages the other's top people, so a context card
            # never has to sit below its own reports.
            chunk_set = set(chunk_members)
            chunk_managers = {by_id[root]["manager_id"] for root in chunk}
            for page in pages:
                if (
                    page["units"] + size <= TEAM_PAGE_UNITS
                    and not chunk_managers & page["members"]
                    and not page["managers"] & chunk_set
                ):
                    break
            else:
                page = {"ids": [], "members": set(), "managers": set(), "units": 0}
                pages.append(page)
            page["ids"].extend(chunk_members)
            page["members"] |= chunk_set
            page["managers"] |= chunk_managers
            page["units"] += size
            for current in chunk_members:
                if moved.get(current):
                    queue.append(moved[current])
    return [page["ids"] for page in pages]


def _team_page_people(page_ids: list[str], by_id: dict[str, dict[str, Any]], order: dict[str, int]) -> list[dict[str, Any]]:
    """Return page people plus one context card per off-page manager."""
    on_page = set(page_ids)
    context_ids = sorted(
        {by_id[person_id]["manager_id"] for person_id in page_ids if by_id[person_id]["manager_id"] and by_id[person_id]["manager_id"] not in on_page},
        key=order.__getitem__,
    )
    context = [
        {**deepcopy(by_id[manager_id]), "manager_id": None, "context": True, "order": -1}
        for manager_id in context_ids
    ]
    return context + [by_id[person_id] for person_id in page_ids]


def _enterprise_pages(data: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    groups = _function_groups(by_id)
    roots = [person for person in by_id.values() if not person["manager_id"]]
    root = roots[0] if len(roots) == 1 else None
    if root:
        groups = [(function, members) for function, members in groups
                  if not (len(members) == 1 and members[0]["id"] == root["id"])]
    pages: list[dict[str, Any]] = []
    overview_chunks = _chunk(groups, 12) or [[]]
    for overview_index, group_chunk in enumerate(overview_chunks, start=1):
        page = _new_page(data, len(pages) + 1, "enterprise-overview", (data.get("title") or "Enterprise organization") + (" · continued" if overview_index > 1 else ""))
        content = page["content_bounds"]
        columns = min(6 if root else 4, len(group_chunk)) or 1
        rows = math.ceil(len(group_chunk) / columns) or 1
        card_w = (content["w"] - GAP * (columns - 1)) / columns
        summary_top = content["y"]
        if root:
            root_h = 0.7
            root_w = min(2.5, content["w"])
            root_card = _card(root, _rect(content["x"] + (content["w"] - root_w) / 2, content["y"], root_w, root_h), page["id"])
            page["elements"].append(root_card)
            summary_top += root_h + 0.35
        card_h = min(1.06, (content["y"] + content["h"] - summary_top - GAP * (rows - 1)) / rows)
        row_elements: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for index, (function, members) in enumerate(group_chunk):
            row, column = divmod(index, columns)
            filled = sum(1 for member in members if member.get("kind", "person") != "open_role")
            open_roles = len(members) - filled
            element = _summary_card(function, function, f"{len(members)} {'position' if len(members) == 1 else 'positions'} · {open_roles} open", _rect(content["x"] + column * (card_w + GAP), summary_top + row * (card_h + GAP), card_w, card_h), page["id"])
            page["elements"].append(element)
            row_elements[row].append(element)
        for row, elements in row_elements.items():
            _add_row_alignment(page, elements, f"enterprise-overview-{row}")
        if root:
            candidates = []
            for (function, members), element in zip(group_chunk, page["elements"][1:]):
                member_ids = {member["id"] for member in members}
                heads = [member for member in members if member["manager_id"] not in member_ids]
                if any(head["manager_id"] == root["id"] for head in heads):
                    candidates.append(_direct_connector(root_card, element, page["id"]))
            for connector in candidates:
                if _connector_hits_non_endpoint_card(connector, page["elements"]):
                    # Try the gaps between columns for a wrapped-row route.
                    start = _site_point(root_card, "bottom")
                    target = next(e for e in page["elements"] if e["stable_name"] == connector["to"])
                    end = _site_point(target, "top")
                    upper_y = _number((start["y"] + summary_top) / 2)
                    lower_y = _number(end["y"] - GAP / 2)
                    for column in range(columns - 1):
                        gap_x = _number(content["x"] + (column + 1) * card_w + (column + 0.5) * GAP)
                        points = [(start["x"], start["y"]), (start["x"], upper_y),
                                  (gap_x, upper_y), (gap_x, lower_y),
                                  (end["x"], lower_y), (end["x"], end["y"])]
                        connector["segments"] = [
                            {"x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1]}
                            for a, b in zip(points, points[1:])
                        ]
                        if not _connector_hits_non_endpoint_card(connector, page["elements"]):
                            break
                if not (_connector_hits_non_endpoint_card(connector, page["elements"]) or
                        _google_straight_connector_hits_non_endpoint_card(connector, page["elements"])):
                    page["connectors"].append(connector)
        page["split_reason"] = "Enterprise mode always separates summary from team pages."
        pages.append(page)
    order = _preorder(by_id)
    for function, members in groups:
        team_pages = _pack_team_pages(members, by_id, order)
        placement = {person_id: index for index, ids in enumerate(team_pages) for person_id in ids}
        for part, page_ids in enumerate(team_pages, start=1):
            detail = _new_page(data, len(pages) + 1, f"enterprise-{function}", f"{function}{' · continued' if part > 1 else ''}")
            _layout_levels(data, detail, _team_page_people(page_ids, by_id, order))
            for card in detail["elements"]:
                person_id = card.get("node_id")
                if person_id and not card["data"].get("context") and any(
                    member["manager_id"] == person_id and placement[member["id"]] > part - 1
                    for member in members
                ):
                    later = min(placement[member["id"]] for member in members
                                if member["manager_id"] == person_id and placement[member["id"]] > part - 1)
                    card["data"]["continuation_hint"] = f"Team continues on page {len(pages) - part + 1 + later + 1}"
            detail["split_reason"] = (
                f"Team pages allow {TEAM_PAGE_UNITS} cards across and {TEAM_PAGE_ROWS} rows; "
                "grey context cards show managers who appear on another page."
            )
            pages.append(detail)
    return pages


def layout(data: dict[str, Any], mode_override: str | None = None) -> dict[str, Any]:
    by_id = _validate_input(data)
    mode = mode_override or (data.get("options") or {}).get("mode") or recommend(data)["recommended_mode"]
    if mode not in MODES:
        raise GeometryError(f"Unknown mode {mode!r}. Choose one of: {', '.join(MODES)}")
    _canvas(data)  # fail early
    if mode == "compact_hierarchy":
        pages = _compact_pages(data, by_id)
    elif mode == "leadership_bands":
        pages = _leadership_pages(data, by_id)
    elif mode == "functional_columns":
        pages = _functional_pages(data, by_id)
    elif mode == "matrix_relationships":
        pages = _matrix_pages(data, by_id)
    else:
        pages = _enterprise_pages(data, by_id)

    if len(pages) > 30:
        raise GeometryError("This chart would need more than 30 pages. Split the roster into smaller charts.")
    result = {
        "schema": "collibra-org-chart-geometry/v1",
        "generator_version": VERSION,
        "mode": mode,
        "input_hash": _canonical_hash(data),
        "title": data.get("title") or "Organization chart",
        "as_of": data.get("as_of"),
        "page_count": len(pages),
        "split": {
            "used": len(pages) > 1,
            "thresholds": {
                "compact_hierarchy": "26 positions, 4 layers, or 8 cards in one row",
                "leadership_bands": "14 leader cards",
                "functional_columns": "5 function panels and 7 cards per panel",
                "matrix_relationships": "24 positions and 8 visible cross-links",
                "enterprise_overview": "summary plus team pages; 8 cards across and 5 rows per team page, with reporting lines",
            },
        },
        "relationships": [
            {
                "stable_name": stable_name("reporting-relationship", f"{person['manager_id']}-{person['id']}"),
                "type": "direct_report",
                "from_node_id": person["manager_id"],
                "to_node_id": person["id"],
            }
            for person in _ordered_people(by_id)
            if person["manager_id"]
        ]
        + [
            {
                "stable_name": stable_name("matrix-relationship", f"{relation.get('from')}-{relation.get('to')}", str(index)),
                "type": relation.get("type", "matrix_relationship"),
                "from_node_id": relation.get("from"),
                "to_node_id": relation.get("to"),
                "label": relation.get("label"),
            }
            for index, relation in enumerate(data.get("relationships") or [])
        ],
        "pages": pages,
    }
    validation = validate_layout(result)
    result["validation"] = validation
    if not validation["valid"]:
        raise GeometryError("Generated invalid geometry: " + "; ".join(validation["errors"]))
    return result


def _rect_from_element(element: dict[str, Any]) -> dict[str, float] | None:
    box = element.get("box")
    if not isinstance(box, dict):
        return None
    if not all(key in box for key in ("x", "y", "w", "h")):
        return None
    try:
        return {key: float(box[key]) for key in ("x", "y", "w", "h")}
    except (TypeError, ValueError):
        return None


def validate_layout(result: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    pages = result.get("pages")
    if not isinstance(pages, list) or not pages:
        return {"valid": False, "errors": ["Layout has no pages."], "warnings": []}
    if len(pages) > 30:
        errors.append("This chart supports up to 30 pages. Split it into smaller charts.")
    names: set[str] = set()
    google_object_ids: set[str] = set()
    for page in pages:
        page_id = page.get("id", "unknown-page")
        canvas = page.get("canvas") or DEFAULT_CANVAS
        width, height = float(canvas["width"]), float(canvas["height"])
        elements = page.get("elements") or []
        local: dict[str, dict[str, Any]] = {}
        collision_elements: list[tuple[str, dict[str, float]]] = []
        for element in elements:
            name = element.get("stable_name")
            if not name:
                errors.append(f"{page_id}: element missing stable_name")
                continue
            if name in names:
                errors.append(f"Duplicate stable_name: {name}")
            names.add(name)
            local[name] = element
            box = _rect_from_element(element)
            if box is None:
                errors.append(f"{page_id}/{name}: invalid box")
                continue
            if box["w"] <= 0 or box["h"] <= 0:
                errors.append(f"{page_id}/{name}: non-positive size")
            if box["x"] < -EPSILON or box["y"] < -EPSILON or box["x"] + box["w"] > width + EPSILON or box["y"] + box["h"] > height + EPSILON:
                errors.append(f"{page_id}/{name}: out of canvas bounds")
            if element.get("collision_class") == "card":
                collision_elements.append((name, box))
                object_id = element.get("google_slides_object_id")
                if not isinstance(object_id, str) or not GOOGLE_OBJECT_ID.fullmatch(object_id):
                    errors.append(f"{page_id}/{name}: invalid Google Slides object ID")
                elif object_id in google_object_ids:
                    errors.append(f"Duplicate Google Slides object ID: {object_id}")
                else:
                    google_object_ids.add(object_id)
                for zone in page.get("reserved_zones") or []:
                    zone_box = {key: float(zone[key]) for key in ("x", "y", "w", "h")}
                    if _intersects(box, zone_box):
                        errors.append(f"{page_id}/{name}: overlaps reserved {zone['name']} zone")
        for index, (name_a, box_a) in enumerate(collision_elements):
            for name_b, box_b in collision_elements[index + 1:]:
                if _intersects(box_a, box_b):
                    errors.append(f"{page_id}: card overlap between {name_a} and {name_b}")
        for connector in page.get("connectors") or []:
            name = connector.get("stable_name")
            if not name:
                errors.append(f"{page_id}: connector missing stable_name")
                continue
            if name in names:
                errors.append(f"Duplicate stable_name: {name}")
            names.add(name)
            object_id = connector.get("google_slides_object_id")
            if not isinstance(object_id, str) or not GOOGLE_OBJECT_ID.fullmatch(object_id):
                errors.append(f"{page_id}/{name}: invalid Google Slides object ID")
            elif object_id in google_object_ids:
                errors.append(f"Duplicate Google Slides object ID: {object_id}")
            else:
                google_object_ids.add(object_id)
            source_name = connector.get("from")
            target_name = connector.get("to")
            if source_name not in local or target_name not in local:
                errors.append(f"{page_id}/{name}: connector endpoint not present on page")
                source = target = None
            else:
                source, target = local[source_name], local[target_name]
                if source is target:
                    errors.append(f"{page_id}/{name}: connector endpoints must be different cards")
            from_site = connector.get("from_site")
            to_site = connector.get("to_site")
            if from_site not in CARDINAL_SITES or to_site not in CARDINAL_SITES:
                errors.append(f"{page_id}/{name}: invalid cardinal connection site")
            if connector.get("native_category") not in {"BENT", "STRAIGHT"}:
                errors.append(f"{page_id}/{name}: invalid native connector category")
            if connector.get("pptx_native_category") != connector.get("native_category"):
                errors.append(f"{page_id}/{name}: PPTX connector category must preserve the native OOXML profile")
            if connector.get("google_slides_category") != GOOGLE_SLIDES_PORTABLE_CATEGORY:
                errors.append(f"{page_id}/{name}: portable Google Slides connector category must be STRAIGHT")
            if connector.get("google_slides_reroute_policy") != "disabled-unless-deck-canary":
                errors.append(f"{page_id}/{name}: unsafe Google Slides reroute policy")
            expected_google_start = GOOGLE_SLIDES_SITE_INDEX.get(from_site)
            expected_google_end = GOOGLE_SLIDES_SITE_INDEX.get(to_site)
            if connector.get("google_slides_from_site_index") != expected_google_start:
                errors.append(f"{page_id}/{name}: wrong Google Slides start site index")
            if connector.get("google_slides_to_site_index") != expected_google_end:
                errors.append(f"{page_id}/{name}: wrong Google Slides end site index")
            segments = connector.get("segments") or []
            if not isinstance(segments, list) or not segments:
                errors.append(f"{page_id}/{name}: connector has no route segments")
                segments = []
            normalized_segments: list[dict[str, float]] = []
            for segment_index, segment in enumerate(segments):
                try:
                    normalized = {key: float(segment[key]) for key in ("x1", "y1", "x2", "y2")}
                except (KeyError, TypeError, ValueError):
                    errors.append(f"{page_id}/{name}: connector segment {segment_index} is invalid")
                    continue
                coordinates = list(normalized.values())
                if min(coordinates[0], coordinates[2]) < -EPSILON or max(coordinates[0], coordinates[2]) > width + EPSILON or min(coordinates[1], coordinates[3]) < -EPSILON or max(coordinates[1], coordinates[3]) > height + EPSILON:
                    errors.append(f"{page_id}/{name}: connector segment out of bounds")
                if abs(normalized["x1"] - normalized["x2"]) > EPSILON and abs(normalized["y1"] - normalized["y2"]) > EPSILON:
                    errors.append(f"{page_id}/{name}: connector segment {segment_index} is not orthogonal")
                if normalized_segments:
                    previous = normalized_segments[-1]
                    if abs(previous["x2"] - normalized["x1"]) > EPSILON or abs(previous["y2"] - normalized["y1"]) > EPSILON:
                        errors.append(f"{page_id}/{name}: connector route is not continuous")
                normalized_segments.append(normalized)
            if source is not None and target is not None and normalized_segments and from_site in CARDINAL_SITES and to_site in CARDINAL_SITES:
                expected_start = _site_point(source, from_site)
                expected_end = _site_point(target, to_site)
                first, last = normalized_segments[0], normalized_segments[-1]
                if abs(first["x1"] - expected_start["x"]) > EPSILON or abs(first["y1"] - expected_start["y"]) > EPSILON:
                    errors.append(f"{page_id}/{name}: route does not start at the declared source site")
                if abs(last["x2"] - expected_end["x"]) > EPSILON or abs(last["y2"] - expected_end["y"]) > EPSILON:
                    errors.append(f"{page_id}/{name}: route does not end at the declared target site")
                if connector.get("type") == "direct_report":
                    source_box = _rect_from_element(source)
                    target_box = _rect_from_element(target)
                    if from_site != "bottom" or to_site != "top" or connector.get("reroute_safe") is not True:
                        errors.append(f"{page_id}/{name}: direct hierarchy is not reroute-safe")
                    elif source_box and target_box and source_box["y"] + source_box["h"] >= target_box["y"] - EPSILON:
                        errors.append(f"{page_id}/{name}: manager card is not above report card")
                endpoint_names = {source_name, target_name}
                for card_name, card_box in collision_elements:
                    if card_name in endpoint_names:
                        continue
                    if any(_segment_intersects_rect(segment, card_box) for segment in normalized_segments):
                        errors.append(f"{page_id}/{name}: connector intersects non-endpoint card {card_name}")
                if (
                    connector.get("type") != "matrix_relationship"
                    and connector.get("google_slides_category") == GOOGLE_SLIDES_PORTABLE_CATEGORY
                    and _google_straight_connector_hits_non_endpoint_card(connector, elements)
                ):
                    errors.append(f"{page_id}/{name}: Google Slides straight connector intersects a non-endpoint card")
        for group in page.get("alignment_groups") or []:
            group_name = group.get("stable_name")
            if not group_name:
                errors.append(f"{page_id}: alignment group missing stable_name")
            elif group_name in names:
                errors.append(f"Duplicate stable_name: {group_name}")
            else:
                names.add(group_name)
            members = group.get("members") or []
            if len(members) != len(set(members)):
                errors.append(f"{page_id}/{group_name}: alignment members repeat")
            if any(member not in local for member in members):
                errors.append(f"{page_id}/{group_name}: alignment member missing")
                continue
            if len(members) < 2:
                continue
            axis = group.get("axis")
            edge = group.get("edge")
            tolerance = float(group.get("tolerance", 0.002))
            if tolerance < 0:
                errors.append(f"{page_id}/{group_name}: alignment tolerance must be non-negative")
                continue
            allowed_edges = {"x": {"left", "right"}, "y": {"top", "bottom"}}
            if axis not in allowed_edges or edge not in allowed_edges[axis]:
                errors.append(f"{page_id}/{group_name}: invalid alignment axis or edge")
                continue
            member_boxes = [_rect_from_element(local[member]) for member in members]
            if any(box is None for box in member_boxes):
                errors.append(f"{page_id}/{group_name}: alignment member has invalid box")
                continue
            values = []
            for box in member_boxes:
                if axis == "x":
                    values.append(box["x"] if edge == "left" else box["x"] + box["w"])
                else:
                    values.append(box["y"] if edge == "top" else box["y"] + box["h"])
            if values and max(values) - min(values) > tolerance + EPSILON:
                errors.append(f"{page_id}/{group_name}: alignment tolerance exceeded")
            equal_size = group.get("equal_size")
            if equal_size is not None:
                if equal_size not in {"width", "height"}:
                    errors.append(f"{page_id}/{group_name}: invalid equal_size")
                else:
                    size_key = "w" if equal_size == "width" else "h"
                    sizes = [box[size_key] for box in member_boxes]
                    if max(sizes) - min(sizes) > tolerance + EPSILON:
                        errors.append(f"{page_id}/{group_name}: equal-size tolerance exceeded")
            distribution_axis = group.get("distribution_axis")
            if distribution_axis is not None:
                if distribution_axis not in {"x", "y"}:
                    errors.append(f"{page_id}/{group_name}: invalid distribution axis")
                elif len(member_boxes) >= 3:
                    position_key, size_key = (("x", "w") if distribution_axis == "x" else ("y", "h"))
                    ordered_boxes = sorted(member_boxes, key=lambda box: box[position_key])
                    gaps = [
                        following[position_key] - (current[position_key] + current[size_key])
                        for current, following in zip(ordered_boxes, ordered_boxes[1:])
                    ]
                    if max(gaps) - min(gaps) > tolerance + EPSILON:
                        errors.append(f"{page_id}/{group_name}: distribution tolerance exceeded")
        cards = len(collision_elements)
        if cards > 26 and result.get("mode") == "compact_hierarchy":
            warnings.append(f"{page_id}: compact page has {cards} cards; review readability")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    layout_parser = subparsers.add_parser("layout", help="Generate deterministic geometry from an org JSON file.")
    layout_parser.add_argument("input", help="Input JSON path, or - for stdin.")
    layout_parser.add_argument("--mode", choices=MODES, help="Override options.mode.")
    layout_parser.add_argument("--output", help="Write JSON here instead of stdout.")
    recommend_parser = subparsers.add_parser("recommend", help="Recommend and compare layout modes.")
    recommend_parser.add_argument("input", help="Input JSON path, or - for stdin.")
    recommend_parser.add_argument("--output", help="Write JSON here instead of stdout.")
    validate_parser = subparsers.add_parser("validate", help="Validate previously generated geometry.")
    validate_parser.add_argument("input", help="Geometry JSON path, or - for stdin.")
    validate_parser.add_argument("--output", help="Write validation JSON here instead of stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        source = _read_json(args.input)
        if args.command == "layout":
            output = layout(source, args.mode)
        elif args.command == "recommend":
            output = recommend(source)
        else:
            output = validate_layout(source)
        _write_json(output, args.output)
        return 0 if output.get("valid", True) else 2
    except (GeometryError, json.JSONDecodeError, OSError, KeyError, TypeError, ValueError) as exc:
        sys.stderr.write(f"org-chart-geometry: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
