from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tools/check_feedback_reproduction_corpus.py"
SPEC = importlib.util.spec_from_file_location("feedback_corpus_gate", CHECKER)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)

BUILDER_PATH = ROOT / "scripts/build_stress_examples.py"
BUILDER_SPEC = importlib.util.spec_from_file_location("drawclock_stress_examples", BUILDER_PATH)
assert BUILDER_SPEC is not None and BUILDER_SPEC.loader is not None
builder = importlib.util.module_from_spec(BUILDER_SPEC)
sys.modules[BUILDER_SPEC.name] = builder
BUILDER_SPEC.loader.exec_module(builder)


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_checked_in_corpus_covers_full_declared_product() -> None:
    errors = gate.validate(
        ROOT / "tests/reproduction-corpus/corpus.json",
        ROOT / "tests/reproduction-corpus/evidence-corpus.json",
    )
    assert errors == []


def test_combined_example_is_reproducible_and_crosses_general_root_kinds() -> None:
    path = ROOT / "example/auto-layout/26-feedback-reproduction-combined.json"
    checked_in = json.loads(path.read_text(encoding="utf-8"))
    generated = builder.build_feedback_reproduction_combined()
    assert checked_in == generated
    assert len(generated) == 121
    assert sum(node.get("kind") == "clock" for node in generated.values()) == 22
    indegree = {name: 0 for name in generated}
    for target, node in generated.items():
        indegree[target] += len(gate._source_names(node.get("source")))
    root_kinds = {generated[name]["kind"] for name, degree in indegree.items() if degree == 0}
    assert {"source", "from", "gate"}.issubset(root_kinds)


def test_gate_rejects_a_missing_issue_mapping(tmp_path: Path) -> None:
    search_path = ROOT / "tests/reproduction-corpus/corpus.json"
    evidence = json.loads((ROOT / "tests/reproduction-corpus/evidence-corpus.json").read_text(encoding="utf-8"))
    for case in evidence["cases"]:
        case["issues"] = [item for item in case["issues"] if item != "FB-BEND-005"]
    evidence_path = tmp_path / "evidence.json"
    _write(evidence_path, evidence)
    errors = gate.validate(search_path, evidence_path)
    assert any("misses issues: FB-BEND-005" in error for error in errors)


def test_gate_rejects_one_to_one_downgrade(tmp_path: Path) -> None:
    evidence = json.loads((ROOT / "tests/reproduction-corpus/evidence-corpus.json").read_text(encoding="utf-8"))
    evidence["coverage_model"] = "one_to_one"
    evidence_path = tmp_path / "evidence.json"
    _write(evidence_path, evidence)
    errors = gate.validate(ROOT / "tests/reproduction-corpus/corpus.json", evidence_path)
    assert any("coverage_model=many_to_many" in error for error in errors)
