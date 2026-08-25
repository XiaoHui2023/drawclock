from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = (
    ROOT / "skills" / "drawclock-project-navigation" / "scripts" / "validate_skills.py"
)


def _validator_module():
    spec = importlib.util.spec_from_file_location("release_skill_validator", VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_project_skills_are_complete_linked_and_private_free() -> None:
    validator = _validator_module()
    assert validator.validate(ROOT / "skills") == []


def test_project_skill_gate_rejects_private_path(tmp_path: Path) -> None:
    validator = _validator_module()
    target = tmp_path / "skills"
    shutil.copytree(ROOT / "skills", target)
    path = target / "clock-json-schema" / "references" / "examples.md"
    path.write_text(
        path.read_text(encoding="utf-8") + "\nC:\\Users\\person\\private\n",
        encoding="utf-8",
    )
    errors = validator.validate(target)
    assert any("Windows user path" in error for error in errors)


def test_project_skill_gate_rejects_broken_or_unlinked_reference(
    tmp_path: Path,
) -> None:
    validator = _validator_module()
    target = tmp_path / "skills"
    shutil.copytree(ROOT / "skills", target)
    skill = target / "clock-diagram-design" / "SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8") + "\n[missing](references/missing.md)\n",
        encoding="utf-8",
    )
    extra = target / "clock-json-schema" / "references" / "unlinked.md"
    extra.write_text("# unlinked\n", encoding="utf-8")
    errors = validator.validate(target)
    assert any("broken reference links" in error for error in errors)
    assert any("unlinked reference files" in error for error in errors)
