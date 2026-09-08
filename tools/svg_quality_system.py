#!/usr/bin/env python3
"""Execute the complete independent SVG quality registry for one artifact."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import feedback_layout_reproduction_oracle as geometry


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "tests" / "quality-metrics.json"
SERIALIZED_AXIS_TOLERANCE = 0.001


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
