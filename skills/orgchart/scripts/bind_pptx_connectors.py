#!/usr/bin/env python3
"""Bind native PowerPoint connector shapes to named org-chart cards.

The presentation renderer and the geometry planner communicate through stable
shape names.  This helper resolves those names to slide-local OOXML shape IDs
and writes ``a:stCxn`` / ``a:endCxn`` references.  PowerPoint can then keep the
connector attached when a user moves either card.

Only slide XML is changed.  A plain line shape may be converted to a native
``p:cxnSp`` when its preset geometry is connector-compatible; other shapes
fail closed.  The input package is never overwritten.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile


SCHEMA = "collibra-org-chart-connectors/v1"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"

NS = {"p": P, "a": A, "r": R, "pr": PR}
for prefix, uri in (("p", P), ("a", A), ("r", R)):
    ET.register_namespace(prefix, uri)

CONNECTOR_PRESETS = {
    "line",
    "straightConnector1",
    "bentConnector2",
    "bentConnector3",
    "bentConnector4",
    "bentConnector5",
    "curvedConnector2",
    "curvedConnector3",
    "curvedConnector4",
    "curvedConnector5",
}
SITE_INDEX = {"top": 0, "left": 1, "bottom": 2, "right": 3}


class ConnectorBindingError(ValueError):
    """Raised when binding would be ambiguous or produce invalid OOXML."""


def _q(namespace: str, local: str) -> str:
    return f"{{{namespace}}}{local}"


def _read_json(path: str) -> dict[str, Any]:
    if path == "-":
        value = json.load(sys.stdin)
    else:
        with Path(path).open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    if not isinstance(value, dict):
        raise ConnectorBindingError("The relationship manifest must be a JSON object.")
    return value


def _presentation_order(package: ZipFile) -> list[str]:
    try:
        presentation = ET.fromstring(package.read("ppt/presentation.xml"))
        rels = ET.fromstring(package.read("ppt/_rels/presentation.xml.rels"))
    except KeyError as exc:
        raise ConnectorBindingError(f"The PPTX is missing {exc.args[0]!r}.") from exc
    targets = {
        relation.get("Id"): relation.get("Target")
        for relation in rels.findall(f".//{{{PR}}}Relationship")
    }
    parts: list[str] = []
    for slide_id in presentation.findall("./p:sldIdLst/p:sldId", NS):
        relationship_id = slide_id.get(_q(R, "id"))
        target = targets.get(relationship_id)
        if not target:
            raise ConnectorBindingError(
                f"Presentation relationship {relationship_id!r} has no target."
            )
        part = posixpath.normpath(posixpath.join("ppt", target.lstrip("/")))
        if not part.startswith("ppt/"):
            raise ConnectorBindingError(f"Unsafe slide relationship target: {target!r}")
        parts.append(part)
    if not parts:
        raise ConnectorBindingError("The presentation has no slides.")
    return parts


def _resolve_slide_part(slide: dict[str, Any], order: list[str]) -> str:
    has_index = "slide_index" in slide
    has_part = "slide_part" in slide
    if has_index == has_part:
        raise ConnectorBindingError(
            "Each manifest slide must contain exactly one of slide_index or slide_part."
        )
    if has_index:
        raw_index = slide["slide_index"]
        if isinstance(raw_index, bool):
            raise ConnectorBindingError("slide_index must be a positive integer.")
        try:
            index = int(raw_index)
        except (TypeError, ValueError) as exc:
            raise ConnectorBindingError("slide_index must be a positive integer.") from exc
        if index < 1 or index > len(order):
            raise ConnectorBindingError(
                f"slide_index {index} is outside the presentation range 1..{len(order)}."
            )
        return order[index - 1]
    part = str(slide["slide_part"]).lstrip("/")
    if part not in order:
        raise ConnectorBindingError(f"slide_part {part!r} is not in presentation order.")
    return part


def _shape_name(shape: ET.Element) -> tuple[str, str] | None:
    container_by_tag = {
        _q(P, "sp"): "nvSpPr",
        _q(P, "grpSp"): "nvGrpSpPr",
        _q(P, "pic"): "nvPicPr",
        _q(P, "graphicFrame"): "nvGraphicFramePr",
        _q(P, "cxnSp"): "nvCxnSpPr",
    }
    container_name = container_by_tag.get(shape.tag)
    if not container_name:
        return None
    properties = shape.find(f"./p:{container_name}/p:cNvPr", NS)
    if properties is None:
        return None
    return properties.get("name", ""), properties.get("id", "")


def _shape_index(root: ET.Element) -> tuple[dict[str, list[ET.Element]], dict[ET.Element, ET.Element]]:
    parent_map = {child: parent for parent in root.iter() for child in parent}
    by_name: dict[str, list[ET.Element]] = defaultdict(list)
    shape_tags = {
        _q(P, "sp"),
        _q(P, "grpSp"),
        _q(P, "pic"),
        _q(P, "graphicFrame"),
        _q(P, "cxnSp"),
    }
    for element in root.iter():
        if element.tag not in shape_tags:
            continue
        identity = _shape_name(element)
        if identity and identity[0]:
            by_name[identity[0]].append(element)
    return by_name, parent_map


def _unique_shape(by_name: dict[str, list[ET.Element]], name: Any, role: str) -> ET.Element:
    normalized = str(name or "").strip()
    if not normalized:
        raise ConnectorBindingError(f"A connection is missing its {role} shape name.")
    matches = by_name.get(normalized, [])
    if not matches:
        raise ConnectorBindingError(f"{role} shape {normalized!r} was not found on the slide.")
    if len(matches) != 1:
        raise ConnectorBindingError(f"{role} shape name {normalized!r} is not unique on the slide.")
    return matches[0]


def _shape_id(shape: ET.Element) -> str:
    identity = _shape_name(shape)
    if not identity or not identity[1].isdigit() or int(identity[1]) < 1:
        raise ConnectorBindingError(f"Shape {identity[0] if identity else '<unknown>'!r} has an invalid OOXML id.")
    return identity[1]


def _site(value: Any, field: str, default: str) -> int:
    candidate = default if value is None else value
    if isinstance(candidate, str):
        normalized = candidate.strip().casefold()
        if normalized in SITE_INDEX:
            return SITE_INDEX[normalized]
        if normalized.isdigit():
            candidate = int(normalized)
        else:
            raise ConnectorBindingError(
                f"{field} must be top, left, bottom, right, or a non-negative integer."
            )
    if isinstance(candidate, bool) or not isinstance(candidate, int) or candidate < 0:
        raise ConnectorBindingError(
            f"{field} must be top, left, bottom, right, or a non-negative integer."
        )
    return candidate


def _convert_line_shape(shape: ET.Element, parent_map: dict[ET.Element, ET.Element]) -> ET.Element:
    if shape.tag == _q(P, "cxnSp"):
        return shape
    if shape.tag != _q(P, "sp"):
        identity = _shape_name(shape)
        raise ConnectorBindingError(
            f"Connector {identity[0] if identity else '<unknown>'!r} is not a connector or line shape."
        )
    geometry = shape.find("./p:spPr/a:prstGeom", NS)
    preset = geometry.get("prst") if geometry is not None else None
    if preset not in CONNECTOR_PRESETS or shape.find("./p:txBody", NS) is not None:
        identity = _shape_name(shape)
        raise ConnectorBindingError(
            f"Shape {identity[0] if identity else '<unknown>'!r} cannot be safely converted to a native connector."
        )
    parent = parent_map.get(shape)
    if parent is None:
        raise ConnectorBindingError("Connector line has no XML parent.")
    old_nonvisual = shape.find("./p:nvSpPr", NS)
    nonvisual_properties = old_nonvisual.find("./p:cNvPr", NS) if old_nonvisual is not None else None
    application_properties = old_nonvisual.find("./p:nvPr", NS) if old_nonvisual is not None else None
    shape_properties = shape.find("./p:spPr", NS)
    if nonvisual_properties is None or application_properties is None or shape_properties is None:
        raise ConnectorBindingError("Connector line is missing required PowerPoint shape properties.")

    connector = ET.Element(_q(P, "cxnSp"))
    nonvisual = ET.SubElement(connector, _q(P, "nvCxnSpPr"))
    nonvisual.append(nonvisual_properties)
    ET.SubElement(nonvisual, _q(P, "cNvCxnSpPr"))
    nonvisual.append(application_properties)
    connector.append(shape_properties)
    style = shape.find("./p:style", NS)
    if style is not None:
        connector.append(style)

    position = list(parent).index(shape)
    parent.remove(shape)
    parent.insert(position, connector)
    return connector


def _connection_properties(connector: ET.Element) -> ET.Element:
    value = connector.find("./p:nvCxnSpPr/p:cNvCxnSpPr", NS)
    if value is None:
        raise ConnectorBindingError("Native connector is missing cNvCxnSpPr.")
    return value


def _bind_one(
    connection: dict[str, Any],
    by_name: dict[str, list[ET.Element]],
    parent_map: dict[ET.Element, ET.Element],
) -> dict[str, Any]:
    if not isinstance(connection, dict):
        raise ConnectorBindingError("Every connection must be a JSON object.")
    connector_name = connection.get("connector")
    connector = _unique_shape(by_name, connector_name, "connector")
    source = _unique_shape(by_name, connection.get("from"), "source")
    target = _unique_shape(by_name, connection.get("to"), "target")
    if source is target:
        raise ConnectorBindingError(f"Connector {connector_name!r} cannot connect a shape to itself.")
    if connector in (source, target):
        raise ConnectorBindingError(f"Connector {connector_name!r} cannot use itself as an endpoint.")
    if source.tag == _q(P, "cxnSp") or target.tag == _q(P, "cxnSp"):
        raise ConnectorBindingError(
            f"Connector {connector_name!r} endpoints must be card shapes, not other connectors."
        )

    converted = connector.tag != _q(P, "cxnSp")
    connector = _convert_line_shape(connector, parent_map)
    # Preserve name resolution for validation after a line-to-connector conversion.
    by_name[str(connector_name)] = [connector]
    properties = _connection_properties(connector)
    for child in list(properties):
        if child.tag in {_q(A, "stCxn"), _q(A, "endCxn")}:
            properties.remove(child)
    start_site = _site(connection.get("from_site"), "from_site", "bottom")
    end_site = _site(connection.get("to_site"), "to_site", "top")
    ET.SubElement(properties, _q(A, "stCxn"), {"id": _shape_id(source), "idx": str(start_site)})
    ET.SubElement(properties, _q(A, "endCxn"), {"id": _shape_id(target), "idx": str(end_site)})
    return {
        "connector": str(connector_name),
        "from": str(connection.get("from")),
        "to": str(connection.get("to")),
        "from_shape_id": int(_shape_id(source)),
        "to_shape_id": int(_shape_id(target)),
        "from_site": start_site,
        "to_site": end_site,
        "converted_line_shape": converted,
    }


def _validate_bound_connection(
    connection: dict[str, Any], by_name: dict[str, list[ET.Element]]
) -> dict[str, Any]:
    connector = _unique_shape(by_name, connection.get("connector"), "connector")
    source = _unique_shape(by_name, connection.get("from"), "source")
    target = _unique_shape(by_name, connection.get("to"), "target")
    if connector.tag != _q(P, "cxnSp"):
        raise ConnectorBindingError(f"Connector {connection.get('connector')!r} is not a native p:cxnSp.")
    properties = _connection_properties(connector)
    starts = properties.findall("./a:stCxn", NS)
    ends = properties.findall("./a:endCxn", NS)
    if len(starts) != 1 or len(ends) != 1:
        raise ConnectorBindingError(
            f"Connector {connection.get('connector')!r} must have exactly one start and one end connection."
        )
    expected_start_site = _site(connection.get("from_site"), "from_site", "bottom")
    expected_end_site = _site(connection.get("to_site"), "to_site", "top")
    if starts[0].get("id") != _shape_id(source) or starts[0].get("idx") != str(expected_start_site):
        raise ConnectorBindingError(f"Connector {connection.get('connector')!r} has the wrong start binding.")
    if ends[0].get("id") != _shape_id(target) or ends[0].get("idx") != str(expected_end_site):
        raise ConnectorBindingError(f"Connector {connection.get('connector')!r} has the wrong end binding.")
    return {
        "connector": str(connection.get("connector")),
        "from": str(connection.get("from")),
        "to": str(connection.get("to")),
        "from_shape_id": int(_shape_id(source)),
        "to_shape_id": int(_shape_id(target)),
        "from_site": expected_start_site,
        "to_site": expected_end_site,
    }


def _manifest_slides(manifest: dict[str, Any], order: list[str]) -> list[tuple[str, list[dict[str, Any]]]]:
    if manifest.get("schema") not in (None, SCHEMA):
        raise ConnectorBindingError(f"Unsupported manifest schema {manifest.get('schema')!r}.")
    slides = manifest.get("slides")
    if not isinstance(slides, list) or not slides:
        raise ConnectorBindingError("The manifest must contain a non-empty slides array.")
    result: list[tuple[str, list[dict[str, Any]]]] = []
    seen: set[str] = set()
    for slide in slides:
        if not isinstance(slide, dict):
            raise ConnectorBindingError("Every manifest slide must be a JSON object.")
        part = _resolve_slide_part(slide, order)
        if part in seen:
            raise ConnectorBindingError(f"Manifest repeats slide {part!r}; combine its connections.")
        seen.add(part)
        connections = slide.get("connections")
        if not isinstance(connections, list) or not connections:
            raise ConnectorBindingError(f"Manifest slide {part!r} has no connections.")
        connector_names = [
            str(connection.get("connector", "")).strip()
            for connection in connections
            if isinstance(connection, dict)
        ]
        if len(connector_names) != len(connections) or any(not name for name in connector_names):
            raise ConnectorBindingError(f"Manifest slide {part!r} has an invalid connector entry.")
        if len(connector_names) != len(set(connector_names)):
            raise ConnectorBindingError(
                f"Manifest slide {part!r} repeats a connector; each native connector may bind once."
            )
        result.append((part, connections))
    return result


def bind_presentation(input_path: Path, manifest: dict[str, Any], output_path: Path) -> dict[str, Any]:
    input_path = input_path.resolve()
    output_path = output_path.resolve()
    if input_path == output_path:
        raise ConnectorBindingError("Refusing to overwrite the input PPTX; choose a distinct output path.")
    if not input_path.is_file():
        raise ConnectorBindingError(f"Input PPTX does not exist: {input_path}")
    if output_path.exists():
        raise ConnectorBindingError(f"Output already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(input_path, "r") as source:
        order = _presentation_order(source)
        requested = _manifest_slides(manifest, order)
        modified: dict[str, bytes] = {}
        report_slides: list[dict[str, Any]] = []
        for part, connections in requested:
            try:
                root = ET.fromstring(source.read(part))
            except KeyError as exc:
                raise ConnectorBindingError(f"The PPTX is missing slide part {part!r}.") from exc
            by_name, parent_map = _shape_index(root)
            bound = [_bind_one(connection, by_name, parent_map) for connection in connections]
            # Re-index the final tree and independently verify all requested references.
            final_index, _ = _shape_index(root)
            validated = [_validate_bound_connection(connection, final_index) for connection in connections]
            modified[part] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            report_slides.append({"slide_part": part, "bound": bound, "validated": validated})

        try:
            with ZipFile(output_path, "x", compression=ZIP_DEFLATED) as destination:
                for info in source.infolist():
                    destination.writestr(info, modified.get(info.filename, source.read(info.filename)))
        except Exception:
            output_path.unlink(missing_ok=True)
            raise

    return {
        "schema": SCHEMA,
        "valid": True,
        "input": str(input_path),
        "output": str(output_path),
        "slide_count": len(report_slides),
        "connection_count": sum(len(slide["bound"]) for slide in report_slides),
        "slides": report_slides,
    }


def validate_presentation(input_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    input_path = input_path.resolve()
    if not input_path.is_file():
        raise ConnectorBindingError(f"Input PPTX does not exist: {input_path}")
    with ZipFile(input_path, "r") as package:
        order = _presentation_order(package)
        requested = _manifest_slides(manifest, order)
        report_slides: list[dict[str, Any]] = []
        for part, connections in requested:
            root = ET.fromstring(package.read(part))
            by_name, _ = _shape_index(root)
            validated = [_validate_bound_connection(connection, by_name) for connection in connections]
            report_slides.append({"slide_part": part, "validated": validated})
    return {
        "schema": SCHEMA,
        "valid": True,
        "input": str(input_path),
        "slide_count": len(report_slides),
        "connection_count": sum(len(slide["validated"]) for slide in report_slides),
        "slides": report_slides,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    bind = subparsers.add_parser("bind", help="Write a new PPTX with native connector bindings.")
    bind.add_argument("pptx", type=Path)
    bind.add_argument("manifest", help="Manifest JSON path, or - for stdin.")
    bind.add_argument("--output", required=True, type=Path)
    validate = subparsers.add_parser("validate", help="Validate native connector bindings without editing.")
    validate.add_argument("pptx", type=Path)
    validate.add_argument("manifest", help="Manifest JSON path, or - for stdin.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = _read_json(args.manifest)
        if args.command == "bind":
            result = bind_presentation(args.pptx, manifest, args.output)
        else:
            result = validate_presentation(args.pptx, manifest)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ConnectorBindingError, BadZipFile, ET.ParseError, OSError, KeyError, ValueError) as exc:
        sys.stderr.write(f"bind-pptx-connectors: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
