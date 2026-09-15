from __future__ import annotations

import ast
import importlib.util
import itertools
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "search_structural_trunk_recurrence.py"
SPEC = importlib.util.spec_from_file_location("structural_trunk_search", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_factor_cases_are_deterministic_pairwise_covering_array():
    first = MODULE.factor_cases()
    second = MODULE.factor_cases()
    assert first == second
    exhaustive_size = 1
    for values in MODULE.FACTORS.values():
        exhaustive_size *= len(values)
    assert len(first) < exhaustive_size

    for name, values in MODULE.FACTORS.items():
        assert {case[name] for case in first} == set(values)
    for left, right in itertools.combinations(MODULE.FACTORS, 2):
        covered = {(case[left], case[right]) for case in first}
        expected = set(itertools.product(MODULE.FACTORS[left], MODULE.FACTORS[right]))
        assert covered == expected


def test_partial_execution_cannot_claim_pairwise_coverage():
    cases = MODULE.factor_cases()
    with pytest.raises(RuntimeError, match="coverage completeness"):
        MODULE.coverage_summary(cases[:2])


def test_receipt_status_prioritizes_any_non_target_quality_failure():
    rows = [{
        "case_id": "case-000",
        "witnesses": [],
        "failed_metric_ids": ["avoidable_bends"],
    }]
    status, _quality, unexpected, inconsistencies = MODULE.classify_results(rows)
    assert status == "quality_failed"
    assert unexpected == [{
        "case_id": "case-000",
        "failed_metric_ids": ["avoidable_bends"],
    }]
    assert inconsistencies == []


def test_receipt_status_rejects_metric_witness_disagreement():
    rows = [
        {
            "case_id": "metric-only",
            "witnesses": [],
            "failed_metric_ids": ["premature_interior_trunk_entry"],
        },
        {
            "case_id": "witness-only",
            "witnesses": [{"edge_id": "e1"}],
            "failed_metric_ids": [],
        },
    ]
    status, _quality, _unexpected, inconsistencies = MODULE.classify_results(rows)
    assert status == "quality_failed"
    assert [item["case_id"] for item in inconsistencies] == [
        "metric-only", "witness-only",
    ]


def test_receipt_identity_binds_the_executed_search_runner():
    identity = MODULE.evidence_identity(ROOT)
    assert identity["runner_sha256"] == MODULE._sha256(SCRIPT)
    assert identity["producer_tree_sha256"]
    assert identity["oracle_sha256"]
    assert identity["quality_registry_sha256"]


@pytest.mark.parametrize(
    ("status", "expected", "exit_code"),
    [
        ("clean_verified", "clean_verified", 0),
        ("reproduced", "reproduced", 0),
        ("reproduced", "clean_verified", 5),
        ("clean_verified", "reproduced", 5),
        ("quality_failed", "clean_verified", 4),
    ],
)
def test_expected_status_controls_process_exit(status, expected, exit_code):
    assert MODULE.expected_status_exit_code(status, expected) == exit_code


def test_detached_backbone_oracle_does_not_cap_ranked_candidates():
    oracle_path = ROOT / "tools" / "feedback_layout_reproduction_oracle.py"
    module = ast.parse(oracle_path.read_text(encoding="utf-8"))
    function = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_detached_backbone_descent_witnesses"
    )
    capped_slices = [
        node for node in ast.walk(function)
        if isinstance(node, ast.Subscript)
        and isinstance(node.slice, ast.Slice)
        and isinstance(node.slice.upper, ast.Constant)
        and isinstance(node.slice.upper.value, int)
    ]
    assert capped_slices == []
