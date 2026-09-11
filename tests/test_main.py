from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"


def test_direct_draw_help_exits_zero() -> None:
    proc = subprocess.run(
        [sys.executable, str(SRC_DIR), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert all(option in proc.stdout for option in (
        "--input", "--library", "--output", "--crossing-style"
    ))
    assert all(command not in proc.stdout for command in (
        "extract", "reload", "drawio-to-json", "json-to-drawio"
    ))


def test_direct_draw_requires_input_library_and_output() -> None:
    proc = subprocess.run(
        [sys.executable, str(SRC_DIR)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = (proc.stdout + proc.stderr).lower()
    assert "input" in combined
    assert "library" in combined
    assert "output" in combined


def _load_frozen_example_gate():
    spec = importlib.util.spec_from_file_location(
        "run_frozen_example", ROOT / "tools" / "run_frozen_example.py"
    )
    assert spec is not None and spec.loader is not None
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    return gate


def _quality_receipt(
    *, required: list[str] | None = None,
    executed: list[str] | None = None,
    receipted: list[str] | None = None,
    failed: list[str] | None = None,
) -> dict[str, object]:
    required = required or ["identity", "routing"]
    executed = executed or list(required)
    receipted = receipted or list(required)
    failed = failed or []
    return {
        "required_metric_ids": required,
        "executed_metric_ids": executed,
        "metric_results": [
            {"metric_id": metric_id, "status": "fail" if metric_id in failed else "pass"}
            for metric_id in receipted
        ],
        "failed_metric_ids": failed,
        "passed": not failed,
    }


def test_frozen_draw_runs_complete_quality_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = _load_frozen_example_gate()
    source = tmp_path / "input.json"
    output = tmp_path / "output.svg"
    source.write_text("{}", encoding="utf-8")
    observed: list[tuple[Path, Path]] = []
    monkeypatch.setattr(gate, "_run", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(gate, "_assert_svg", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        gate.quality,
        "evaluate",
        lambda input_path, svg_path: (
            observed.append((input_path, svg_path)) or _quality_receipt()
        ),
    )
    gate._draw(tmp_path / "binary", source, output)
    assert observed == [(source, output)]


@pytest.mark.parametrize("mutation", ["missing", "reordered", "unreceipted", "failed"])
def test_frozen_complete_quality_gate_rejects_registry_escape(
    mutation: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = _load_frozen_example_gate()
    receipt = _quality_receipt()
    if mutation == "missing":
        receipt["executed_metric_ids"] = ["identity"]
    elif mutation == "reordered":
        receipt["executed_metric_ids"] = ["routing", "identity"]
    elif mutation == "unreceipted":
        receipt["metric_results"] = [{"metric_id": "identity", "status": "pass"}]
    else:
        receipt = _quality_receipt(failed=["routing"])
    monkeypatch.setattr(gate.quality, "evaluate", lambda *_args: receipt)
    with pytest.raises(SystemExit):
        gate._assert_complete_quality(tmp_path / "input.json", tmp_path / "output.svg")


def test_frozen_complete_quality_gate_accepts_exact_negative_witness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = _load_frozen_example_gate()
    receipt = _quality_receipt(failed=["crossing_treatment"])
    monkeypatch.setattr(gate.quality, "evaluate", lambda *_args: receipt)
    gate._assert_complete_quality(
        tmp_path / "input.json",
        tmp_path / "negative.svg",
        expected_failures=("crossing_treatment",),
    )


def _write_conditional_root_fixture(
    config: Path,
    svg: Path,
    *,
    protected_root_x: int = 40,
    crossing: bool = False,
) -> None:
    config.write_text(json.dumps({
        "safe_root": {"kind": "source"},
        "protected_root": {"kind": "from"},
        "target_a": {"kind": "clock", "source": "safe_root"},
        "target_b": {"kind": "clock", "source": "protected_root"},
    }), encoding="utf-8")
    routes = (
        '<polyline class="edge" points="10,30 80,30"/>'
        '<polyline class="edge" points="40,0 40,60"/>'
        if crossing else
        '<polyline class="edge" points="30,20 80,20"/>'
        '<polyline class="edge" points="60,60 80,60"/>'
    )
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<g class="component" data-node-id="safe_root"><rect class="component-graphic" x="10" y="10" width="20" height="20"/></g>'
        f'<g class="component" data-node-id="protected_root"><rect class="component-graphic" x="{protected_root_x}" y="50" width="20" height="20"/></g>'
        '<g class="component" data-node-id="target_a"><rect class="component-graphic" x="80" y="10" width="20" height="20"/></g>'
        '<g class="component" data-node-id="target_b"><rect class="component-graphic" x="80" y="50" width="20" height="20"/></g>'
        f'{routes}</svg>',
        encoding="utf-8",
    )


def test_frozen_conditional_root_gate_accepts_safe_first_and_protected_later(
    tmp_path: Path,
) -> None:
    gate = _load_frozen_example_gate()
    config = tmp_path / "conditional-root.json"
    svg = tmp_path / "conditional-root.svg"
    _write_conditional_root_fixture(config, svg)
    assert gate._assert_conditional_root_columns(
        svg,
        config,
        first_column=("safe_root",),
        later=("protected_root",),
    ) == 10


@pytest.mark.parametrize("protected_root_x,crossing", ((10, False), (40, True)))
def test_frozen_conditional_root_gate_rejects_policy_or_crossing_regression(
    tmp_path: Path,
    protected_root_x: int,
    crossing: bool,
) -> None:
    gate = _load_frozen_example_gate()
    config = tmp_path / "conditional-root.json"
    svg = tmp_path / "conditional-root.svg"
    _write_conditional_root_fixture(
        config,
        svg,
        protected_root_x=protected_root_x,
        crossing=crossing,
    )
    with pytest.raises(SystemExit):
        gate._assert_conditional_root_columns(
            svg,
            config,
            first_column=("safe_root",),
            later=("protected_root",),
        )


def test_removed_subcommands_are_rejected() -> None:
    for command in ("draw", "extract", "reload", "run", "drawio-to-json"):
        proc = subprocess.run(
            [sys.executable, str(SRC_DIR), command],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode != 0, command


def test_release_archive_contains_only_draw_surface(tmp_path: Path, monkeypatch) -> None:
    spec = importlib.util.spec_from_file_location(
        "bundle_release", ROOT / "tools" / "bundle_release.py"
    )
    assert spec is not None and spec.loader is not None
    bundle_release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bundle_release)

    project = tmp_path / "project"
    (project / "dist").mkdir(parents=True)
    (project / "src").mkdir()
    (project / "src" / "drawclock.egg-info").mkdir()
    (project / "src" / "drawclock.egg-info" / "PKG-INFO").write_text(
        "generated\n", encoding="utf-8"
    )
    (project / "drawio-lib" / "drawclock").mkdir(parents=True)
    (project / "drawio-lib" / "drawclock" / "source.xml").write_text(
        "<mxlibrary/>\n", encoding="utf-8"
    )
    (project / "example").mkdir()
    (project / "example" / "auto-layout").mkdir()
    (project / "dist" / "drawclock.exe").write_text("", encoding="utf-8")
    (project / "README.md").write_text("", encoding="utf-8")
    (project / "draw.md").write_text("", encoding="utf-8")
    (project / "source-deploy.md").write_text("", encoding="utf-8")
    (project / "licenses").mkdir()
    (project / "licenses" / "NotoSansCJK-OFL-1.1.txt").write_text(
        "SIL Open Font License 1.1\n", encoding="utf-8"
    )
    shutil.copytree(ROOT / "skills", project / "skills")
    (project / "example" / "README.md").write_text(
        "# Examples\n", encoding="utf-8"
    )
    (project / "example" / "auto-layout" / "README.md").write_text(
        "# Automatic layout examples\n", encoding="utf-8"
    )
    (project / "example" / "draw.json").write_text("{}", encoding="utf-8")
    packaged_layout_examples = tuple(
        path.name for path in sorted((ROOT / "example" / "auto-layout").glob("*.json"))
    )
    for name in packaged_layout_examples:
        (project / "example" / "auto-layout" / name).write_text("{}", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        '[project]\nname = "drawclock"\nversion = "1.2.3"\n', encoding="utf-8"
    )
    (project / "src" / "__main__.py").write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr(bundle_release, "ROOT", project)
    monkeypatch.setattr(bundle_release.platform, "system", lambda: "Windows")
    assert bundle_release.main() == 0

    archive = project / "dist" / "drawclock-1.2.3-windows.zip"
    with zipfile.ZipFile(archive) as zf:
        names = {item.filename for item in zf.infolist() if not item.is_dir()}
    prefix = "drawclock-1.2.3-windows/"
    expected = {
        prefix + "drawclock.exe",
        prefix + "README.md",
        prefix + "draw.md",
        prefix + "example/draw.json",
        prefix + "example/auto-layout/33-description-colors.json",
        prefix + "licenses/NotoSansCJK-OFL-1.1.txt",
        prefix + "drawio-lib/drawclock/source.xml",
    }
    assert names == expected

    checker_spec = importlib.util.spec_from_file_location(
        "check_release_archive", ROOT / "tools" / "check_release_archive.py"
    )
    assert checker_spec is not None and checker_spec.loader is not None
    checker = importlib.util.module_from_spec(checker_spec)
    checker_spec.loader.exec_module(checker)
    assert checker.validate(archive) == []
    with zipfile.ZipFile(archive, "a") as zf:
        zf.writestr(prefix + "pyproject.toml", "[project]\n")
    assert checker.validate(archive) == ["unexpected files: pyproject.toml"]


def test_source_manifest_rejects_missing_or_modified_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = importlib.util.spec_from_file_location(
        "run_source_release", ROOT / "tools" / "run_source_release.py"
    )
    assert spec is not None and spec.loader is not None
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)

    monkeypatch.setattr(gate.sys, "platform", "win32")
    assert gate._venv_python(tmp_path / "venv") == tmp_path / "venv/Scripts/python.exe"
    monkeypatch.setattr(gate.sys, "platform", "linux")
    assert gate._venv_python(tmp_path / "venv") == tmp_path / "venv/bin/python"
    assert gate._edge_count({
        "root": {"kind": "from"},
        "gate": {"kind": "gate", "source": "root"},
        "mux": {"kind": "mux2", "source": {"0": "root", "1": "gate"}},
    }) == 3

    root = tmp_path / "release"
    files = {
        "src/__main__.py": b"print('ok')\n",
        "drawio-lib/drawclock/source.xml": b"<mxlibrary/>\n",
        "example/draw.json": b"{}\n",
        "example/auto-layout/22-terminal-frequency-table.json": b"{}\n",
        "licenses/NotoSansCJK-OFL-1.1.txt": b"SIL Open Font License 1.1\n",
        "skills/clock-diagram-design/SKILL.md": b"---\nname: clock-diagram-design\ndescription: test\n---\n",
        "skills/clock-json-schema/SKILL.md": b"---\nname: clock-json-schema\ndescription: test\n---\n",
        "skills/clock-layout-algorithms/SKILL.md": b"---\nname: clock-layout-algorithms\ndescription: test\n---\n",
        "skills/component-library-design/SKILL.md": b"---\nname: component-library-design\ndescription: test\n---\n",
        "skills/drawclock-project-navigation/SKILL.md": b"---\nname: drawclock-project-navigation\ndescription: test\n---\n",
        "skills/svg-artifact-design/SKILL.md": b"---\nname: svg-artifact-design\ndescription: test\n---\n",
        "skills/svg-portability/SKILL.md": b"---\nname: svg-portability\ndescription: test\n---\n",
            "skills/drawclock-project-navigation/scripts/validate_skills.py": b"print('ok')\n",
            "skills/clock-layout-algorithms/scripts/layout_statistics.py": b"print('ok')\n",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    manifest = {
        "schema": 1,
        "files": {
            relative: hashlib.sha256(content).hexdigest()
            for relative, content in files.items()
        },
    }
    (root / "source-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    gate.validate_source_manifest(root)

    (root / "example" / "out").mkdir()
    (root / "example" / "out" / "frozen-input.json").write_text(
        "{}\n", encoding="utf-8"
    )
    gate.validate_source_manifest(root)

    (root / "src" / "__main__.py").write_text("changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        gate.validate_source_manifest(root)

    (root / "src" / "__main__.py").write_bytes(files["src/__main__.py"])
    (root / "vendor" / "wheels").mkdir(parents=True)
    with pytest.raises(ValueError, match="unused runtime dependencies"):
        gate.validate_source_manifest(root)

    (root / "vendor" / "wheels").rmdir()
    (root / "runtime").mkdir()
    with pytest.raises(ValueError, match="unused runtime dependencies"):
        gate.validate_source_manifest(root)
