#!/usr/bin/env python3
"""Search structural public-bus variants for a detached remote descent."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import feedback_layout_reproduction_oracle as oracle
from svg_quality_system import evaluate_with_geometry

BASE = ROOT / "tests/reproduction-corpus/premature-interior-trunk-entry.json"
REGISTRY = ROOT / "tests/quality-metrics.json"
FACTORS = {
    "target_band": ("lower", "middle", "last"),
    "public_chain": ("gate", "gate-cell", "gate-div"),
    "outlier_column": (13, 17, 9),
    "outlier_constraint": ("gate-and-descendant", "descendant"),
    "outlier_fanout": ("extra-far", "single", "extra-near"),
    "declaration_order": ("forward", "reverse"),
}


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _producer_tree_sha256(root):
    files = [
        *root.joinpath("src").rglob("*.py"),
        *root.joinpath("drawio-lib").rglob("*.xml"),
    ]
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def evidence_identity(producer_root):
    return {
        "runner_sha256": _sha256(Path(__file__).resolve()),
        "producer_tree_sha256": _producer_tree_sha256(producer_root),
        "oracle_sha256": _sha256(Path(oracle.__file__)),
        "quality_registry_sha256": _sha256(REGISTRY),
    }


def _source_map(item):
    source = item.get("source", {})
    return source if isinstance(source, dict) else {}


def build_case(factors):
    config = json.loads(BASE.read_text(encoding="utf-8"))
    roots = [
        name for name, item in config.items()
        if item.get("kind") == "from" and "source" not in item
    ]
    if len(roots) != 1:
        raise ValueError("expected exactly one public from root")
    root = roots[0]
    targets = sorted(
        name for name, item in config.items()
        if name.startswith("select_reconvergent_")
        and root in _source_map(item).values()
    )
    target_index = {
        "middle": len(targets) // 2,
        "lower": (3 * len(targets)) // 4,
        "last": len(targets) - 1,
    }[factors["target_band"]]
    outlier = targets[target_index]
    additions = []
    for index, target in enumerate(targets):
        source = dict(_source_map(config[target]))
        port = next(port for port, name in source.items() if name == root)
        gate = "public_gate_{:02d}".format(index)
        gate_item = {"kind": "gate", "source": root}
        if (
            target == outlier
            and factors["outlier_constraint"] == "gate-and-descendant"
        ):
            gate_item["layout_column"] = factors["outlier_column"] - 2
        additions.append((gate, gate_item))
        previous = gate
        if factors["public_chain"] != "gate":
            middle = "public_{}_{:02d}".format(
                "cell" if factors["public_chain"] == "gate-cell" else "div",
                index,
            )
            additions.append((middle, {
                "kind": "cell" if factors["public_chain"] == "gate-cell" else "div",
                "source": previous,
            }))
            previous = middle
        source[port] = previous
        config[target]["source"] = source
        config[target]["layout_column"] = (
            5 if target != outlier else factors["outlier_column"]
        )
    outlier_gate = "public_gate_{:02d}".format(target_index)
    if factors["outlier_fanout"] != "single":
        anchor = targets[
            0 if factors["outlier_fanout"] == "extra-near" else len(targets) - 1
        ]
        probe = "public_outlier_probe"
        additions.append((probe, {
            "kind": "mux2",
            "layout_column": factors["outlier_column"] - 1,
            "source": {"0": outlier_gate, "1": anchor},
        }))
        additions.append(("public_outlier_probe_clock", {
            "kind": "clock", "source": probe,
        }))
    items = list(config.items()) + additions
    if factors["declaration_order"] == "reverse":
        items.reverse()
    return dict(items), root, outlier


def factor_cases():
    names = tuple(FACTORS)
    candidates = [
        dict(zip(names, values))
        for values in itertools.product(*(FACTORS[name] for name in names))
    ]
    preferred = {
        "target_band": {"last": 0, "lower": 1, "middle": 2},
        "public_chain": {"gate": 0, "gate-cell": 1, "gate-div": 2},
        "outlier_column": {17: 0, 13: 1, 9: 2},
        "outlier_constraint": {"gate-and-descendant": 0, "descendant": 1},
        "outlier_fanout": {"extra-far": 0, "extra-near": 1, "single": 2},
        "declaration_order": {"reverse": 0, "forward": 1},
    }
    candidates.sort(key=lambda case: tuple(
        preferred[name][case[name]] for name in names
    ))

    def pairs(case):
        return {
            (left, case[left], right, case[right])
            for left, right in itertools.combinations(names, 2)
        }

    uncovered = set().union(*(pairs(case) for case in candidates))
    selected = []
    remaining = list(candidates)
    while uncovered:
        best_index, best = max(
            enumerate(remaining),
            key=lambda item: (len(pairs(item[1]) & uncovered), -item[0]),
        )
        gain = pairs(best) & uncovered
        if not gain:
            raise RuntimeError("pairwise covering array construction stalled")
        selected.append(best)
        uncovered -= gain
        remaining.pop(best_index)
    return selected


def coverage_summary(cases):
    names = tuple(FACTORS)
    required_pairs = {
        (left, left_value, right, right_value)
        for left, right in itertools.combinations(names, 2)
        for left_value in FACTORS[left]
        for right_value in FACTORS[right]
    }
    covered_pairs = {
        (left, case[left], right, case[right])
        for case in cases
        for left, right in itertools.combinations(names, 2)
    }
    if covered_pairs != required_pairs:
        raise RuntimeError("pairwise coverage completeness gate failed")
    return {
        "strength": 2,
        "required_pairs": len(required_pairs),
        "covered_pairs": len(covered_pairs),
    }


def classify_results(results):
    quality_failures = [
        {
            "case_id": row["case_id"],
            "failed_metric_ids": row["failed_metric_ids"],
        }
        for row in results if row["failed_metric_ids"]
    ]
    unexpected_quality_failures = [
        {
            "case_id": row["case_id"],
            "failed_metric_ids": [
                metric_id for metric_id in row["failed_metric_ids"]
                if metric_id != "premature_interior_trunk_entry"
            ],
        }
        for row in results
        if any(
            metric_id != "premature_interior_trunk_entry"
            for metric_id in row["failed_metric_ids"]
        )
    ]
    reproductions = [row for row in results if row["witnesses"]]
    evidence_inconsistencies = [
        {
            "case_id": row["case_id"],
            "metric_failed": (
                "premature_interior_trunk_entry" in row["failed_metric_ids"]
            ),
            "witness_present": bool(row["witnesses"]),
        }
        for row in results
        if (
            "premature_interior_trunk_entry" in row["failed_metric_ids"]
        ) != bool(row["witnesses"])
    ]
    status = (
        "quality_failed" if (
            unexpected_quality_failures or evidence_inconsistencies
        )
        else "reproduced" if reproductions
        else "clean_verified"
    )
    return (
        status,
        quality_failures,
        unexpected_quality_failures,
        evidence_inconsistencies,
    )


def expected_status_exit_code(status, expected):
    if status == "quality_failed":
        return 4
    return 0 if status == expected else 5


def direct_witness(input_path, svg_path):
    config, logical = oracle.parse_topology(input_path)
    indegree = Counter(edge.target for edge in logical)
    outdegree = Counter(edge.source for edge in logical)
    roots = {name for name in config if indegree[name] == 0 and outdegree[name]}
    boxes, routes = oracle.parse_svg(svg_path, set(config))
    oracle.bind_routes(routes, boxes, logical)
    if any(
        not route.source or not route.target or not route.edge_id
        for route in routes
    ):
        raise ValueError("route binding completeness gate failed")
    return [
        *oracle._premature_interior_trunk_entry_witnesses(roots, routes, boxes),
        *oracle._premature_lateral_departure_witnesses(roots, routes, boxes),
        *oracle._detached_backbone_descent_witnesses(roots, routes, boxes),
    ]


def run_cli(producer_root, input_path, svg_path):
    return subprocess.run(
        [
            sys.executable, str(producer_root / "src"),
            "-i", str(input_path),
            "-l", str(producer_root / "drawio-lib"),
            "-o", str(svg_path),
            "--crossing-style", "arc",
        ],
        cwd=producer_root,
        capture_output=True,
        check=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--expect",
        required=True,
        choices=("clean_verified", "reproduced"),
    )
    args = parser.parse_args()
    producer_root = args.producer_root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    cases = factor_cases()
    planned_pairwise_coverage = coverage_summary(cases)
    identity = evidence_identity(producer_root)
    for index, factors in enumerate(cases):
        case_dir = output / "case-{:03d}".format(index)
        case_dir.mkdir(parents=True, exist_ok=True)
        input_path = case_dir / "input.json"
        svg_path = case_dir / "run-1.svg"
        config, root, outlier = build_case(factors)
        input_path.write_text(
            json.dumps(config, indent=2) + "\n", encoding="utf-8"
        )
        run = run_cli(producer_root, input_path, svg_path)
        if run.returncode or not svg_path.is_file():
            print("operational_error case={}".format(index), file=sys.stderr)
            return 2
        quality, geometry = evaluate_with_geometry(
            input_path, svg_path, REGISTRY
        )
        witnesses = geometry["witnesses"][
            "premature_interior_trunk_entry_witnesses"
        ]
        row = {
            "case_id": "case-{:03d}".format(index),
            "factors": factors,
            "root": root,
            "outlier": outlier,
            "input_sha256": _sha256(input_path),
            "svg_sha256": _sha256(svg_path),
            "witnesses": witnesses,
            "required_metric_ids": quality["required_metric_ids"],
            "executed_metric_ids": quality["executed_metric_ids"],
            "failed_metric_ids": quality["failed_metric_ids"],
        }
        if row["required_metric_ids"] != row["executed_metric_ids"]:
            raise RuntimeError("full quality metric exact-set gate failed")
        results.append(row)
        (case_dir / "result.json").write_text(
            json.dumps(row, indent=2) + "\n", encoding="utf-8"
        )
        print("{} {}".format(row["case_id"], "RED" if witnesses else "clean"), flush=True)
        if not witnesses:
            continue
        second = case_dir / "run-2.svg"
        rerun = run_cli(producer_root, input_path, second)
        if rerun.returncode or _sha256(second) != _sha256(svg_path):
            print("nondeterministic_reproduction case={}".format(index), file=sys.stderr)
            return 3
        row["run_2_sha256"] = _sha256(second)
        row["oracle_witnesses"] = geometry["witnesses"][
            "premature_interior_trunk_entry_witnesses"
        ]
        (case_dir / "result.json").write_text(
            json.dumps(row, indent=2) + "\n", encoding="utf-8"
        )
    executed_pairwise_coverage = coverage_summary([
        row["factors"] for row in results
    ])
    reproductions = [row for row in results if row["witnesses"]]
    (
        status,
        quality_failures,
        unexpected_quality_failures,
        evidence_inconsistencies,
    ) = classify_results(results)
    receipt = {
        **identity,
        "status": status,
        "expected_status": args.expect,
        "planned_cases": len(cases),
        "executed_cases": len(results),
        "covered_factor_values": {
            name: sorted({item["factors"][name] for item in results})
            for name in FACTORS
        },
        "planned_pairwise_coverage": planned_pairwise_coverage,
        "executed_pairwise_coverage": executed_pairwise_coverage,
        "reproductions": reproductions,
        "quality_failures": quality_failures,
        "unexpected_quality_failures": unexpected_quality_failures,
        "evidence_inconsistencies": evidence_inconsistencies,
    }
    (output / "reproduction-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2))
    return expected_status_exit_code(status, args.expect)


if __name__ == "__main__":
    raise SystemExit(main())
