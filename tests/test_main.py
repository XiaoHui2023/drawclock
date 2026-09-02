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


def test_frozen_single_source_gate_identifies_zero_indegree_root(
    tmp_path: Path,
) -> None:
    spec = importlib.util.spec_from_file_location(
        "run_frozen_example", ROOT / "tools" / "run_frozen_example.py"
    )
    assert spec is not None and spec.loader is not None
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)

    config = tmp_path / "single-source.json"
    config.write_text(
        json.dumps({
            "shared_source": {"kind": "from"},
            "terminal": {"kind": "clock", "source": "shared_source"},
        }),
        encoding="utf-8",
    )
    svg = tmp_path / "single-source.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<g class="component" data-node-id="shared_source"/>'
        '<g class="component" data-node-id="shared_source"/>'
        '</svg>',
        encoding="utf-8",
    )
    gate._assert_single_logical_source_has_rendering_anchors(
        svg, config, "shared_source"
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
    (project / ".runtime" / "node").mkdir(parents=True)
    (project / ".runtime" / "runtime-manifest.json").write_text("{}\n", encoding="utf-8")
    (project / ".runtime" / "node" / "node.exe").touch()
    (project / "dist" / "drawclock.exe").write_text("", encoding="utf-8")
    (project / "README.md").write_text("", encoding="utf-8")
    (project / "draw.md").write_text("", encoding="utf-8")
    (project / "source-deploy.md").write_text("", encoding="utf-8")
    (project / "licenses").mkdir()
    (project / "licenses" / "NotoSansCJK-OFL-1.1.txt").write_text(
        "SIL Open Font License 1.1\n", encoding="utf-8"
    )
    shutil.copytree(ROOT / "skills", project / "skills")
    (project / "example" / "draw.json").write_text("{}", encoding="utf-8")
    packaged_layout_examples = (
        "01-linear.json",
        "05-dense-cross-root.json",
            "08-stress-512-clocks.json",
            "19-dispersed-root-fanout.json",
            "20-asymmetric-merge-route-bulge.json",
            "21-layout-column-preference.json",
            "22-terminal-frequency-table.json",
            "23-middle-column-low-use-sources.json",
            "24-single-source-rendering-alias.json",
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
        names = set(zf.namelist())
    prefix = "drawclock-1.2.3-windows/"
    assert prefix + "draw.md" in names
    assert prefix + "example/draw.json" in names
    for name in packaged_layout_examples:
        assert prefix + "example/auto-layout/" + name in names
    assert prefix + "runtime/runtime-manifest.json" in names
    assert prefix + "src/__main__.py" in names
    assert prefix + "source/__main__.py" not in names
    assert prefix + "source-deploy.md" in names
    assert prefix + "licenses/NotoSansCJK-OFL-1.1.txt" in names
    assert prefix + "drawio-lib/drawclock/source.xml" in names
    assert prefix + "drawio-lib/drawclock.xml" not in names
    for skill in (
        "clock-diagram-design",
        "clock-json-schema",
        "clock-layout-algorithms",
        "component-library-design",
        "drawclock-project-navigation",
    ):
        assert prefix + f"skills/{skill}/SKILL.md" in names
    assert (
        prefix
        + "skills/drawclock-project-navigation/scripts/validate_skills.py"
        in names
    )
    assert prefix + "requirements-offline.txt" not in names
    assert not any("vendor/wheels/" in name for name in names)
    assert prefix + "source-manifest.json" in names
    assert not any(".egg-info/" in name for name in names)
    assert prefix + "json.md" not in names
    assert prefix + "rule.md" not in names
    assert not any("reload" in name or "extract" in name for name in names)


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
        "runtime/runtime-manifest.json": b"{}\n",
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
    with pytest.raises(ValueError, match="legacy Python runtime dependencies"):
        gate.validate_source_manifest(root)

    (root / "vendor" / "wheels").rmdir()
    (root / "runtime" / "runtime-manifest.json").unlink()
    with pytest.raises(ValueError, match="paths differ"):
        gate.validate_source_manifest(root)
