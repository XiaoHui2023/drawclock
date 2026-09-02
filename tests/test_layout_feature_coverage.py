from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "skills" / "clock-layout-algorithms" / "references" / "layout-feature-coverage.json"
VALIDATOR = ROOT / "skills" / "drawclock-project-navigation" / "scripts" / "validate_test_coverage_manifest.py"


def _validator_module():
    spec = importlib.util.spec_from_file_location("coverage_manifest_validator", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_layout_feature_coverage_manifest_is_closed() -> None:
    assert _validator_module().validate(_manifest(), ROOT) == []


def test_layout_feature_coverage_validator_kills_missing_role_interaction_and_test_mutants() -> None:
    validator = _validator_module()
    baseline = _manifest()

    missing_role = copy.deepcopy(baseline)
    missing_role["scenarios"] = [
        scenario for scenario in missing_role["scenarios"]
        if scenario["id"] != "middle-source-fault"
    ]
    assert any(
        "feature free-source-layer missing roles" in error
        for error in validator.validate(missing_role, ROOT)
    )

    missing_interaction = copy.deepcopy(baseline)
    for scenario in missing_interaction["scenarios"]:
        scenario["covers_interactions"] = [
            item for item in scenario["covers_interactions"]
            if item != "terminal-fanout"
        ]
    assert any(
        "interaction terminal-fanout missing roles" in error
        for error in validator.validate(missing_interaction, ROOT)
    )

    fake_test = copy.deepcopy(baseline)
    fake_test["scenarios"][0]["tests"] = ["tests/test_auto_layout.py::test_does_not_exist"]
    assert any(
        "missing test function" in error
        for error in validator.validate(fake_test, ROOT)
    )
