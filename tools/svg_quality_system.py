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


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "tests" / "quality-metrics.json"
SERIALIZED_AXIS_TOLERANCE = 0.001
NS = "{http://www.w3.org/2000/svg}"


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
    return {
        "topology_identity": topology_failures,
        "orthogonal_segments": non_orthogonal,
        "crossing_treatment": _crossing_treatment_witnesses(root, routes),
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
