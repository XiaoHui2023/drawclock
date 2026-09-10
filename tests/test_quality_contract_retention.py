from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_quality_contract_retention as retention
import check_all_svg_quality as all_svg
import check_feedback_reproduction_gate as feedback_gate


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_current_quality_contract_is_retained() -> None:
    assert retention.validate() == []


def test_retention_rejects_removed_or_redefined_metric(tmp_path: Path) -> None:
    registry = json.loads(retention.DEFAULT_REGISTRY.read_text(encoding="utf-8"))
    removed = copy.deepcopy(registry)
    removed["metrics"].pop()
    removed_path = tmp_path / "removed.json"
    _write(removed_path, removed)
    assert any("exact-set" in error for error in retention.validate(
        retention.DEFAULT_BASELINE, removed_path
    ))

    changed = copy.deepcopy(registry)
    changed["metrics"][0]["applicability"] = "has_edges"
    changed_path = tmp_path / "changed.json"
    _write(changed_path, changed)
    assert any("changed applicability" in error for error in retention.validate(
        retention.DEFAULT_BASELINE, changed_path
    ))


def test_retention_rejects_duplicate_and_tampered_baseline(tmp_path: Path) -> None:
    registry = json.loads(retention.DEFAULT_REGISTRY.read_text(encoding="utf-8"))
    duplicate = copy.deepcopy(registry)
    duplicate["metrics"].append(copy.deepcopy(duplicate["metrics"][0]))
    duplicate_path = tmp_path / "duplicate.json"
    _write(duplicate_path, duplicate)
    assert any("duplicated" in error for error in retention.validate(
        retention.DEFAULT_BASELINE, duplicate_path
    ))

    baseline = json.loads(retention.DEFAULT_BASELINE.read_text(encoding="utf-8"))
    baseline["contracts"].pop()
    baseline_path = tmp_path / "tampered-baseline.json"
    _write(baseline_path, baseline)
    assert any("baseline changed" in error for error in retention.validate(
        baseline_path, retention.DEFAULT_REGISTRY
    ))


def test_all_svg_gate_cannot_bypass_contract_failure(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setattr(
        all_svg.quality_contract, "validate", lambda: ["mutant metric removed"]
    )
    assert all_svg.main(["--input-dir", str(tmp_path)]) == 2
    assert "quality contract retention failed" in capsys.readouterr().err


def test_release_gate_cannot_bypass_contract_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        feedback_gate.quality_contract,
        "validate",
        lambda: ["mutant applicability narrowed"],
    )
    assert feedback_gate._release_gate() != 0
    assert "quality-contract: mutant applicability narrowed" in capsys.readouterr().err
