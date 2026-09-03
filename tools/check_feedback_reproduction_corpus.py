#!/usr/bin/env python3
"""Validate the deterministic search corpus and formal many-to-many evidence map."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FACTORS = {
    "root_kind", "root_fanout", "fixed_port_order", "chain_depth",
    "consumer_band_gap", "feasible_root_rank", "input_insertion_order",
}


def _load(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path.name}: cannot read valid JSON: {exc}")
        return None


def _source_names(value: object) -> list[str]:
    if isinstance(value, str):
        return [value.split("[", 1)[0]]
    if isinstance(value, dict):
        return [item.split("[", 1)[0] for item in value.values() if isinstance(item, str)]
    return []


def _validate_topology(path: Path, root: Path, errors: list[str]) -> None:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        errors.append(f"case path escapes project root: {path}")
        return
    graph = _load(path, errors)
    if not isinstance(graph, dict) or not graph:
        errors.append(f"{relative}: topology must be a non-empty object")
        return
    names = set(graph)
    adjacency: dict[str, list[str]] = {name: [] for name in names}
    indegree = {name: 0 for name in names}
    for target, node in graph.items():
        if not isinstance(node, dict) or not isinstance(node.get("kind"), str):
            errors.append(f"{relative}: {target} must be an object with kind")
            continue
        for source in _source_names(node.get("source")):
            if source not in names:
                errors.append(f"{relative}: {target} references missing source {source}")
                continue
            adjacency[source].append(target)
            indegree[target] += 1
    queue = [name for name, degree in indegree.items() if degree == 0]
    visited = 0
    while queue:
        source = queue.pop()
        visited += 1
        for target in adjacency[source]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(names):
        errors.append(f"{relative}: topology contains a cycle")


def validate(search_path: Path, evidence_path: Path, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    search = _load(search_path, errors)
    evidence = _load(evidence_path, errors)
    if not isinstance(search, dict) or not isinstance(evidence, dict):
        return errors
    if search.get("coverage_model") != "many_to_many" or evidence.get("coverage_model") != "many_to_many":
        errors.append("both corpus manifests must declare coverage_model=many_to_many")
    factors = search.get("factors")
    if not isinstance(factors, list) or not REQUIRED_FACTORS.issubset(factors):
        errors.append("search corpus does not cover every required factor")
    issues = search.get("issues")
    cases = search.get("cases")
    if not isinstance(issues, list) or not issues or len(issues) != len(set(issues)):
        errors.append("search corpus issue set is empty or duplicated")
        issues = []
    if not isinstance(cases, list) or not cases:
        errors.append("search corpus cases are missing")
        cases = []
    case_ids: set[str] = set()
    tuples: set[tuple[object, object, object]] = set()
    for case in cases:
        if not isinstance(case, dict):
            errors.append("search corpus case must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in case_ids:
            errors.append(f"invalid or duplicate search case id: {case_id!r}")
            continue
        case_ids.add(case_id)
        tuples.add((case.get("family"), case.get("rows"), case.get("seed")))
        relative = case.get("path")
        if not isinstance(relative, str):
            errors.append(f"{case_id}: case path is missing")
            continue
        _validate_topology(root / relative, root, errors)
    families = {"mux", "pad", "asym", "middle", "port"}
    expected = {(family, rows, seed) for family in families for rows in (4, 8, 12) for seed in range(4)}
    if tuples != expected:
        errors.append(f"search corpus tuple coverage mismatch: expected {len(expected)}, got {len(tuples)}")

    formal = evidence.get("cases")
    if not isinstance(formal, list) or not formal:
        errors.append("formal evidence cases are missing")
        formal = []
    mapped: set[str] = set()
    has_multi_issue_case = False
    for case in formal:
        if not isinstance(case, dict):
            errors.append("formal evidence case must be an object")
            continue
        mapped_ids = case.get("issues")
        if not isinstance(mapped_ids, list) or not mapped_ids:
            errors.append(f"{case.get('id', '<missing>')}: issues must be non-empty")
            continue
        if len(mapped_ids) > 1:
            has_multi_issue_case = True
        mapped.update(item for item in mapped_ids if isinstance(item, str))
        relative = case.get("input")
        if not isinstance(relative, str):
            errors.append(f"{case.get('id', '<missing>')}: input is missing")
        else:
            _validate_topology(root / relative, root, errors)
    missing = set(issues) - mapped
    unknown = mapped - set(issues)
    if missing:
        errors.append(f"formal evidence mapping misses issues: {', '.join(sorted(missing))}")
    if unknown:
        errors.append(f"formal evidence mapping has unknown issues: {', '.join(sorted(unknown))}")
    if not has_multi_issue_case:
        errors.append("formal evidence mapping does not exercise a multi-issue case")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search", type=Path, default=ROOT / "tests/reproduction-corpus/corpus.json")
    parser.add_argument("--evidence", type=Path, default=ROOT / "tests/reproduction-corpus/evidence-corpus.json")
    args = parser.parse_args()
    errors = validate(args.search, args.evidence)
    if errors:
        print(f"feedback corpus gate: FAIL ({len(errors)} errors)", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("feedback corpus gate: PASS cases=60 coverage=many_to_many")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
