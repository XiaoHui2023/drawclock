from __future__ import annotations

import hashlib
import importlib.util
import json
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
    (project / "drawio-lib").mkdir()
    (project / "drawio-lib" / "drawclock.xml").write_text(
        "<mxlibrary/>\n", encoding="utf-8"
    )
    (project / "example").mkdir()
    (project / "example" / "auto-layout").mkdir()
    (project / ".runtime" / "node").mkdir(parents=True)
    (project / ".runtime" / "runtime-manifest.json").write_text("{}\n", encoding="utf-8")
    (project / ".runtime" / "node" / "node.exe").touch()
    (project / ".source-wheelhouse").mkdir()
    (project / ".source-wheelhouse" / "wheelhouse-manifest.json").write_text(
        '{}\n', encoding="utf-8"
    )
    (project / ".source-wheelhouse" / "dependency-1-py3-none-any.whl").touch()
    (project / "dist" / "drawclock.exe").write_text("", encoding="utf-8")
    (project / "README.md").write_text("", encoding="utf-8")
    (project / "draw.md").write_text("", encoding="utf-8")
    (project / "source-deploy.md").write_text("", encoding="utf-8")
    (project / "requirements-offline.txt").write_text(
        "dependency==1\n", encoding="utf-8"
    )
    (project / "example" / "draw.json").write_text("{}", encoding="utf-8")
    packaged_layout_examples = (
        "01-linear.json",
        "05-dense-cross-root.json",
        "08-stress-512-clocks.json",
        "20-asymmetric-merge-route-bulge.json",
        "21-layout-column-preference.json",
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
    assert prefix + "requirements-offline.txt" in names
    assert prefix + "vendor/wheels/wheelhouse-manifest.json" in names
    assert prefix + "vendor/wheels/dependency-1-py3-none-any.whl" in names
    assert prefix + "source-manifest.json" in names
    assert not any(".egg-info/" in name for name in names)
    assert prefix + "json.md" not in names
    assert prefix + "rule.md" not in names
    assert not any("reload" in name or "extract" in name for name in names)


def test_source_manifest_rejects_missing_or_modified_source(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "run_source_release", ROOT / "tools" / "run_source_release.py"
    )
    assert spec is not None and spec.loader is not None
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)

    root = tmp_path / "release"
    files = {
        "src/__main__.py": b"print('ok')\n",
        "vendor/wheels/wheelhouse-manifest.json": b"{}\n",
        "requirements-offline.txt": b"dependency==1\n",
        "runtime/runtime-manifest.json": b"{}\n",
        "drawio-lib/drawclock.xml": b"<mxlibrary/>\n",
        "example/draw.json": b"{}\n",
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

    (root / "src" / "__main__.py").write_text("changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        gate.validate_source_manifest(root)

    (root / "src" / "__main__.py").write_bytes(files["src/__main__.py"])
    (root / "vendor" / "wheels" / "wheelhouse-manifest.json").unlink()
    with pytest.raises(ValueError, match="paths differ"):
        gate.validate_source_manifest(root)
