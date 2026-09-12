#!/usr/bin/env python3
"""Fail closed when an established requirement or quality metric disappears."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = ROOT / "tests/quality-contract-baseline.json"
DEFAULT_REGISTRY = ROOT / "tests/quality-metrics.json"
BASELINE_CANONICAL_SHA256 = "6fd84d32abe809932d2707df56e66fe15caa9b4c863503d3a7c7fbda172160fe"


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate(
    baseline_path: Path = DEFAULT_BASELINE,
    registry_path: Path = DEFAULT_REGISTRY,
) -> list[str]:
    errors: list[str] = []
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8-sig"))
        registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"quality contract input is invalid: {exc}"]
    if canonical_hash(baseline) != BASELINE_CANONICAL_SHA256:
        errors.append("protected quality baseline changed without explicit review")
    contracts = baseline.get("contracts")
    metrics = registry.get("metrics")
    if not isinstance(contracts, list) or not isinstance(metrics, list):
        return [*errors, "contracts/metrics must both be arrays"]
    requirement_ids = [item.get("requirement_id") for item in contracts]
    protected_ids = [item.get("metric_id") for item in contracts]
    current_ids = [item.get("id") for item in metrics]
    if len(requirement_ids) != len(set(requirement_ids)):
        errors.append("requirement IDs are missing or duplicated")
    if len(protected_ids) != len(set(protected_ids)):
        errors.append("protected metric IDs are missing or duplicated")
    if len(current_ids) != len(set(current_ids)):
        errors.append("current metric IDs are missing or duplicated")
    if current_ids != protected_ids:
        errors.append(
            "current metric exact-set/order differs from the protected baseline"
        )
    current_by_id = {item.get("id"): item for item in metrics}
    for contract in contracts:
        metric_id = contract.get("metric_id")
        current = current_by_id.get(metric_id)
        if current is None:
            errors.append(f"protected metric disappeared: {metric_id}")
            continue
        for field in ("witness", "applicability"):
            if current.get(field) != contract.get(field):
                errors.append(
                    f"protected metric {metric_id} changed {field}: "
                    f"{current.get(field)!r} != {contract.get(field)!r}"
                )
    conflicts = baseline.get("approved_conflicts")
    if not isinstance(conflicts, list):
        errors.append("approved_conflicts must be an array")
    else:
        for index, conflict in enumerate(conflicts):
            required = (
                "conflict_id", "requirement_ids", "decision",
                "user_approval_evidence", "reported_at",
            )
            if not isinstance(conflict, dict) or any(
                not conflict.get(field) for field in required
            ):
                errors.append(f"approved_conflicts[{index}] lacks user-visible evidence")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args()
    errors = validate(args.baseline, args.registry)
    if errors:
        print("quality contract retention: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "quality contract retention: PASS "
        f"metrics={len(json.loads(args.registry.read_text(encoding='utf-8-sig'))['metrics'])} "
        f"requirements={len(json.loads(args.baseline.read_text(encoding='utf-8-sig'))['contracts'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
