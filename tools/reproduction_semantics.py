#!/usr/bin/env python3
"""Evaluate data-driven exact reproduction semantics without production imports."""

from __future__ import annotations

from collections import Counter
from typing import Any


def _sources(item: dict[str, Any]) -> list[str]:
    source = item.get("source")
    if isinstance(source, str):
        return [source.split("[", 1)[0]]
    if isinstance(source, dict):
        return [
            value.split("[", 1)[0]
            for value in source.values()
            if isinstance(value, str)
        ]
    return []


def observe(
    config: dict[str, Any],
    report: dict[str, Any],
    contract: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return explicit precondition and symptom results for one case/issue edge."""
    if contract is None:
        return {
            "variant_id": None,
            "preconditions_met": True,
            "symptom_observed": None,
            "errors": [],
        }
    errors: list[str] = []
    indegree = Counter(
        {name: len(_sources(item)) for name, item in config.items()}
    )
    outdegree = Counter(source for item in config.values() for source in _sources(item))
    for expected in contract.get("nodes", []):
        name = expected.get("name")
        item = config.get(name)
        if not isinstance(item, dict):
            errors.append(f"missing node {name}")
            continue
        if "kind" in expected and item.get("kind") != expected["kind"]:
            errors.append(
                f"{name} kind is {item.get('kind')!r}, expected {expected['kind']!r}"
            )
        if expected.get("root") is True and indegree[name] != 0:
            errors.append(f"{name} is not a zero-indegree root")
        if outdegree[name] < int(expected.get("min_outdegree", 0)):
            errors.append(
                f"{name} outdegree is {outdegree[name]}, "
                f"expected >= {expected['min_outdegree']}"
            )
    fanin = contract.get("direct_mux_fanin")
    if isinstance(fanin, dict):
        target = fanin.get("target")
        target_item = config.get(target)
        if not isinstance(target_item, dict):
            errors.append(f"missing mux target {target}")
        else:
            target_kind = str(target_item.get("kind", ""))
            if not target_kind.startswith("mux"):
                errors.append(f"{target} kind is not mux: {target_kind!r}")
            actual_sources = set(_sources(target_item))
            expected_sources = set(fanin.get("sources", []))
            if actual_sources != expected_sources:
                errors.append(
                    f"{target} direct sources differ: "
                    f"{sorted(actual_sources)} != {sorted(expected_sources)}"
                )
            allowed_kinds = set(fanin.get("source_kinds", []))
            for source in expected_sources:
                item = config.get(source)
                if not isinstance(item, dict):
                    errors.append(f"missing direct source {source}")
                elif allowed_kinds and item.get("kind") not in allowed_kinds:
                    errors.append(
                        f"{source} kind {item.get('kind')!r} "
                        f"not in {sorted(allowed_kinds)}"
                    )
                if indegree[source] != 0:
                    errors.append(f"{source} is not a zero-indegree root")
    symptom = contract.get("symptom", {})
    symptom_type = symptom.get("type")
    observed = False
    if symptom_type == "split_rejoin":
        token = f"{symptom['root']}:{symptom.get('port', 'right')}"
        observed = token in report.get("witnesses", {}).get(
            "split_rejoin_roots", []
        )
    elif symptom_type == "direct_root_fanin_columns":
        expected_sources = set(symptom.get("sources", []))
        for witness in report.get("witnesses", {}).get(
            "direct_root_fanin_column_witnesses", []
        ):
            if (
                witness.get("target") == symptom.get("target")
                and set(witness.get("sources", [])) == expected_sources
                and len(witness.get("distinct_columns", []))
                >= int(symptom.get("min_distinct_columns", 2))
            ):
                observed = True
                break
    else:
        errors.append(f"unknown symptom contract type: {symptom_type!r}")
    return {
        "variant_id": contract.get("variant_id"),
        "preconditions_met": not errors,
        "symptom_observed": observed,
        "errors": errors,
    }
