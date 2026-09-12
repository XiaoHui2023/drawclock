#!/usr/bin/env python3
"""Execute the complete independent SVG quality registry for one artifact."""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

import feedback_layout_reproduction_oracle as geometry
import svg_graph_inspector as geometry_inventory


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "tests" / "quality-metrics.json"
SERIALIZED_AXIS_TOLERANCE = 0.001
NS = "{http://www.w3.org/2000/svg}"
FREQUENCY_COLUMNS = ("func_freq", "scan_freq", "bist_freq")


def _svg_edge_bridge_centers(root: ET.Element) -> list[list[tuple[float, float]]]:
    """Read arc centers from serialized edge paths without production imports."""
    result: list[list[tuple[float, float]]] = []
    token_pattern = re.compile(
        r"[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
    )
    for element in root.iter():
        if "edge" not in (element.get("class") or "").split():
            continue
        centers: list[tuple[float, float]] = []
        if element.tag == f"{NS}path":
            tokens = token_pattern.findall(element.get("d", ""))
            index = 0
            command = ""
            current: tuple[float, float] | None = None

            def take(count: int) -> list[float]:
                nonlocal index
                values = tokens[index:index + count]
                if len(values) != count or any(value.isalpha() for value in values):
                    raise ValueError("invalid serialized SVG edge path")
                index += count
                return [float(value) for value in values]

            while index < len(tokens):
                if tokens[index].isalpha():
                    command = tokens[index]
                    index += 1
                if command in {"M", "L"}:
                    current = tuple(take(2))
                    command = "L"
                elif command == "A":
                    _rx, _ry, _rotation, _large, _sweep, x, y = take(7)
                    if current is None:
                        raise ValueError("arc appears before an edge start")
                    centers.append((
                        round((current[0] + x) / 2.0, 4),
                        round((current[1] + y) / 2.0, 4),
                    ))
                    current = (x, y)
                else:
                    raise ValueError(f"unsupported serialized SVG edge command: {command}")
        result.append(centers)
    return result


def _crossing_treatment_witnesses(
    root: ET.Element, routes: list[geometry.Route]
) -> list[dict[str, Any]]:
    """Require exactly one bridge and no junction at each visible cross-net cross."""
    bridges = _svg_edge_bridge_centers(root)
    if len(bridges) != len(routes):
        raise ValueError("edge/bridge extraction count mismatch")
    bridge_by_edge = {
        route.edge_id: set(bridges[index]) for index, route in enumerate(routes)
    }
    crossings, _ = geometry.route_crossings(routes)
    junctions = {
        (round(float(element.get("cx", "nan")), 4),
         round(float(element.get("cy", "nan")), 4))
        for element in root
        if element.tag == f"{NS}circle" and element.get("r") == "3"
    }
    witnesses: list[dict[str, Any]] = []
    used: set[tuple[str, tuple[float, float]]] = set()
    for event in crossings:
        point = tuple(event["point"])
        participating = [
            edge_id for edge_id in event["edges"]
            if point in bridge_by_edge[edge_id]
        ]
        used.update((edge_id, point) for edge_id in participating)
        if len(participating) != 1:
            witnesses.append({
                "kind": "missing_bridge" if not participating else "multiple_bridges",
                "point": list(point),
                "edges": event["edges"],
                "bridge_edges": participating,
            })
        if point in junctions:
            witnesses.append({
                "kind": "junction_at_different_net_crossing",
                "point": list(point),
                "edges": event["edges"],
            })
    for edge_id, points in bridge_by_edge.items():
        for point in sorted(points):
            if (edge_id, point) not in used:
                witnesses.append({
                    "kind": "orphan_bridge", "point": list(point),
                    "edge": edge_id,
                })
    return witnesses


def load_registry(path: Path = DEFAULT_REGISTRY) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    metrics = payload.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise ValueError("quality registry must contain a non-empty metrics list")
    ids = [str(item.get("id", "")) for item in metrics]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("quality metric ids must be non-empty and unique")
    return metrics


def validate_metric_receipt(
    required: list[str], executed: list[str], results: list[dict[str, Any]]
) -> None:
    """Reject any missing, extra, duplicate, reordered, or unreceipted metric."""
    receipted = [str(item.get("metric_id", "")) for item in results]
    for label, ids in (
        ("required", required), ("executed", executed), ("receipted", receipted)
    ):
        if any(not item for item in ids) or len(ids) != len(set(ids)):
            raise ValueError(f"{label} quality metric ids must be non-empty and unique")
    if not (required == executed == receipted):
        raise ValueError(
            "quality receipt is not the exact ordered registry: "
            f"required={required!r}, executed={executed!r}, receipted={receipted!r}"
        )


def _geometry_inventory_failures(
    inventory: dict[str, Any], routes: list[geometry.Route]
) -> list[dict[str, Any]]:
    """Fail closed when the reusable per-line fact surface is incomplete."""
    failures: list[dict[str, Any]] = []

    def reject(kind: str, **details: Any) -> None:
        failures.append({"kind": kind, **details})

    if inventory.get("schema_version") != 2:
        reject(
            "schema_version", expected=2,
            actual=inventory.get("schema_version"),
        )
    edge_rows = inventory.get("edges")
    if not isinstance(edge_rows, list):
        return [*failures, {"kind": "edges_not_array"}]
    by_id = {
        row.get("id"): row for row in edge_rows if isinstance(row, dict)
    }
    route_ids = [route.edge_id for route in routes]
    if sorted(by_id) != sorted(route_ids):
        reject(
            "edge_exact_set", expected=sorted(route_ids), actual=sorted(by_id),
        )
    crossings, overlaps = geometry.route_crossings(routes)
    crossing_by_edge: Counter[str] = Counter(
        edge_id for event in crossings for edge_id in event["edges"]
    )
    crossing_points = {route.edge_id: set() for route in routes}
    crossing_partners = {route.edge_id: set() for route in routes}
    for event in crossings:
        left, right = event["edges"]
        point = tuple(event["point"])
        crossing_points[left].add(point)
        crossing_points[right].add(point)
        crossing_partners[left].add(right)
        crossing_partners[right].add(left)
    overlap_by_edge: Counter[str] = Counter(
        edge_id for event in overlaps for edge_id in event["edges"]
    )
    required_edge_fields = {
        "id", "source", "source_port", "target", "target_port",
        "points", "bounds", "segment_count", "bend_count", "bend_points",
        "direction_sequence", "segments", "crossing_count",
        "crossing_points", "crossed_edge_ids", "crossings",
        "different_net_overlap_count", "different_net_overlap_length_px",
        "different_net_overlaps",
    }
    for route in routes:
        row = by_id.get(route.edge_id)
        if not isinstance(row, dict):
            continue
        missing = sorted(required_edge_fields - set(row))
        if missing:
            reject("edge_fields", edge_id=route.edge_id, missing=missing)
            continue
        raw_segments = geometry.segments(route)
        expected_directions = []
        for start, end in raw_segments:
            if abs(start[1] - end[1]) <= geometry.EPS:
                expected_directions.append(
                    "right" if end[0] > start[0] else "left"
                )
            elif abs(start[0] - end[0]) <= geometry.EPS:
                expected_directions.append(
                    "down" if end[1] > start[1] else "up"
                )
            else:
                expected_directions.append("non_orthogonal")
        expected = {
            "segment_count": len(raw_segments),
            "bend_count": max(0, len(route.points) - 2),
            "direction_sequence": expected_directions,
            "crossing_count": crossing_by_edge[route.edge_id],
            "crossing_points": [
                list(point) for point in sorted(crossing_points[route.edge_id])
            ],
            "crossed_edge_ids": sorted(crossing_partners[route.edge_id]),
            "different_net_overlap_count": overlap_by_edge[route.edge_id],
        }
        for field, value in expected.items():
            if row.get(field) != value:
                reject(
                    "edge_fact_mismatch", edge_id=route.edge_id,
                    field=field, expected=value, actual=row.get(field),
                )
        segment_rows = row.get("segments")
        if not isinstance(segment_rows, list) or len(segment_rows) != len(raw_segments):
            reject("segment_rows", edge_id=route.edge_id)
            continue
        for index, (segment, pair) in enumerate(zip(segment_rows, raw_segments)):
            required = {
                "index", "start", "end", "orientation", "direction",
                "length_px", "bounds",
            }
            if not isinstance(segment, dict) or required - set(segment):
                reject(
                    "segment_fields", edge_id=route.edge_id, index=index,
                    missing=sorted(required - set(segment or {})),
                )
                continue
            if (
                segment["index"] != index
                or segment["start"] != list(pair[0])
                or segment["end"] != list(pair[1])
                or segment["direction"] != expected_directions[index]
            ):
                reject(
                    "segment_fact_mismatch", edge_id=route.edge_id, index=index,
                )
    network_rows = inventory.get("networks")
    expected_networks = sorted({
        f"{route.source}:{route.source_port}" for route in routes
    })
    if not isinstance(network_rows, list):
        reject("networks_not_array")
    else:
        network_ids = sorted(
            row.get("id") for row in network_rows if isinstance(row, dict)
        )
        if network_ids != expected_networks:
            reject(
                "network_exact_set", expected=expected_networks,
                actual=network_ids,
            )
        graph_fields = {
            "vertex_count", "segment_count", "connected_components",
            "cycle_rank", "junction_points", "leaf_points",
            "shared_segments", "shared_segment_length_px",
        }
        for row in network_rows:
            if not isinstance(row, dict):
                reject("network_row_not_object")
                continue
            graph = row.get("geometry_graph")
            if not isinstance(graph, dict) or graph_fields - set(graph):
                reject(
                    "network_graph_fields", network_id=row.get("id"),
                    missing=sorted(graph_fields - set(graph or {})),
                )
    return failures


def _artifact_metric_witnesses(
    input_path: Path, svg_path: Path
) -> dict[str, Any]:
    """Measure identity and segment shape from the serialized artifact itself."""
    config, logical = geometry.parse_topology(input_path)
    root = ET.parse(svg_path).getroot()
    boxes, routes = geometry.parse_svg(svg_path, set(config))
    geometry.bind_routes(routes, boxes, logical)
    rendered_nodes = {box.node for box in boxes}
    expected_nodes = set(config)
    topology = {
        "missing_nodes": sorted(expected_nodes - rendered_nodes),
        "unexpected_nodes": sorted(rendered_nodes - expected_nodes),
        "expected_edge_count": len(logical),
        "rendered_edge_count": len(routes),
    }
    topology_failures = {
        key: value for key, value in topology.items()
        if (
            bool(value) if key in {"missing_nodes", "unexpected_nodes"}
            else value != topology["expected_edge_count"]
        )
    }
    if topology_failures:
        inventory_failures = [{
            "kind": "topology_invalid",
            "topology_failures": topology_failures,
        }]
        inventory_summary = {
            "schema_version": None,
            "nodes": len(boxes),
            "edges": len(routes),
            "segments": sum(len(geometry.segments(route)) for route in routes),
            "networks": len({
                (route.source, route.source_port) for route in routes
            }),
            "crossings": None,
            "different_net_overlaps": None,
        }
    else:
        inventory = geometry_inventory.inspect(input_path, svg_path)
        inventory_failures = _geometry_inventory_failures(inventory, routes)
        inventory_summary = {
            "schema_version": inventory["schema_version"],
            "nodes": len(inventory["nodes"]),
            "edges": len(inventory["edges"]),
            "segments": sum(
                row["segment_count"] for row in inventory["edges"]
            ),
            "networks": len(inventory["networks"]),
            "crossings": len(inventory["crossings"]),
            "different_net_overlaps": len(
                inventory["different_net_overlaps"]
            ),
        }
    non_orthogonal = []
    for route in routes:
        for index, (start, end) in enumerate(geometry.segments(route)):
            if (
                abs(start[0] - end[0]) > SERIALIZED_AXIS_TOLERANCE
                and abs(start[1] - end[1]) > SERIALIZED_AXIS_TOLERANCE
            ):
                non_orthogonal.append({
                    "edge_id": route.edge_id,
                    "segment_index": index,
                    "start": list(start),
                    "end": list(end),
                })
    # Diagram captions used to be emitted as a direct child of the SVG root
    # and copied the input filename stem.  Component labels, annotation text,
    # and the frequency table are all nested in groups, so root-level text is
    # an independent, serialization-level witness for that unwanted caption.
    diagram_titles = [
        {
            "text": "".join(element.itertext()),
            "x": element.get("x"),
            "y": element.get("y"),
            "matches_input_stem": "".join(element.itertext()) == input_path.stem,
        }
        for element in root
        if element.tag == f"{NS}text"
    ]
    referenced = {edge.source for edge in logical}
    terminals = sorted(set(config) - referenced)
    expected_fields = [
        field for field in FREQUENCY_COLUMNS
        if any(str(config[name].get(field, "")) for name in terminals)
    ]
    expected_values = sorted(
        (name, field, str(config[name].get(field, "")))
        for name in terminals
        for field in expected_fields
        if str(config[name].get(field, ""))
    )
    frequency_groups = [
        element for element in root.iter()
        if element.get("class") == "frequency-table"
    ]
    headings = [
        element.get("data-frequency-field")
        for element in root.iter()
        if element.get("class") == "frequency-heading"
    ]
    values = sorted(
        (
            element.get("data-node-id"),
            element.get("data-frequency-field"),
            "".join(element.itertext()),
        )
        for element in root.iter()
        if element.get("class") == "frequency-value"
    )
    frequency_failures = []
    expected_group_count = 1 if expected_fields else 0
    if len(frequency_groups) != expected_group_count:
        frequency_failures.append({
            "kind": "table_count",
            "expected": expected_group_count,
            "actual": len(frequency_groups),
        })
    if headings != expected_fields:
        frequency_failures.append({
            "kind": "heading_fields",
            "expected": expected_fields,
            "actual": headings,
        })
    if values != expected_values:
        frequency_failures.append({
            "kind": "values",
            "expected": [list(item) for item in expected_values],
            "actual": [list(item) for item in values],
        })
    return {
        "topology_identity": topology_failures,
        "orthogonal_segments": non_orthogonal,
        "crossing_treatment": _crossing_treatment_witnesses(root, routes),
        "diagram_title_absence": diagram_titles,
        "frequency_column_visibility": frequency_failures,
        "geometry_inventory_completeness": inventory_failures,
        "_geometry_inventory_summary": inventory_summary,
    }


def _applicable(kind: str, report: dict[str, Any], config: dict[str, Any]) -> tuple[bool, str]:
    if kind == "always":
        return True, "artifact"
    if kind == "has_edges":
        return report["totals"]["logical_edges"] > 0, "logical_edges"
    if kind == "has_annotations":
        count = report["annotation_quality"]["expected"]
        return count > 0, f"annotations={count}"
    indegree = Counter()
    outdegree = Counter()
    _, logical = geometry.parse_topology(Path(report["_input_path"]))
    for edge in logical:
        indegree[edge.target] += 1
        outdegree[edge.source] += 1
    roots = {name for name in config if indegree[name] == 0 and outdegree[name] > 0}
    if kind == "has_roots":
        return bool(roots), f"roots={len(roots)}"
    if kind == "has_root_fanout":
        count = sum(outdegree[name] >= 2 for name in roots)
        return count > 0, f"root_fanouts={count}"
    if kind == "has_merge":
        count = sum(value >= 2 for value in indegree.values())
        return count > 0, f"merges={count}"
    if kind == "has_direct_root_mux_array":
        direct: Counter[str] = Counter()
        for edge in logical:
            if edge.source in roots and str(config.get(edge.target, {}).get("kind", "")).startswith("mux"):
                direct[edge.target] += 1
        count = sum(value >= 3 for value in direct.values())
        return count > 0, f"direct_root_mux_arrays={count}"
    if kind == "has_direct_root_fanin":
        direct: Counter[str] = Counter()
        for edge in logical:
            if edge.source in roots:
                direct[edge.target] += 1
        count = sum(value >= 2 for value in direct.values())
        return count > 0, f"direct_root_fanins={count}"
    raise ValueError(f"unknown applicability predicate: {kind}")


def evaluate(input_path: Path, svg_path: Path, registry_path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    registry = load_registry(registry_path)
    config = json.loads(input_path.read_text(encoding="utf-8-sig"))
    report = geometry.analyze(input_path, svg_path)
    artifact_witnesses = _artifact_metric_witnesses(input_path, svg_path)
    inventory_summary = artifact_witnesses.pop("_geometry_inventory_summary")
    report["_input_path"] = str(input_path)
    results = []
    for metric in registry:
        applicable, proof = _applicable(metric["applicability"], report, config)
        witness_name = metric.get("witness")
        if not applicable:
            witnesses: Any = []
            status = "not_applicable"
        elif metric["id"] in artifact_witnesses:
            witnesses = artifact_witnesses[metric["id"]]
            status = "fail" if witnesses else "pass"
        elif witness_name == "overlaps":
            witnesses = report["overlaps"]
            status = "fail" if witnesses else "pass"
        elif witness_name == "annotation_quality":
            witnesses = report["annotation_quality"]
            status = "fail" if report["annotation_quality"]["failure_count"] else "pass"
        elif witness_name == "annotation_color_quality":
            witnesses = report["annotation_quality"]
            status = "fail" if report["annotation_quality"]["color_failure_count"] else "pass"
        else:
            witnesses = report["witnesses"][witness_name]
            status = "fail" if witnesses else "pass"
        results.append({
            "metric_id": metric["id"],
            "status": status,
            "applicability_proof": proof,
            "witnesses": witnesses,
        })
    required = [metric["id"] for metric in registry]
    executed = [result["metric_id"] for result in results]
    validate_metric_receipt(required, executed, results)
    return {
        "schema_version": 1,
        "required_metric_ids": required,
        "executed_metric_ids": executed,
        "metric_results": results,
        "failed_metric_ids": [item["metric_id"] for item in results if item["status"] == "fail"],
        "geometry_inventory_summary": inventory_summary,
        "passed": all(item["status"] != "fail" for item in results),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--svg", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate(args.input, args.svg, args.registry)
    if args.output:
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(
        "svg-quality: "
        + ("PASS" if report["passed"] else "FAIL")
        + f" metrics={len(report['executed_metric_ids'])}"
        + f" failed={','.join(report['failed_metric_ids']) or '-'}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
