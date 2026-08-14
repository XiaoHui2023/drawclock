from __future__ import annotations

import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path


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
    (project / "drawio-lib").mkdir()
    (project / "example").mkdir()
    (project / ".runtime" / "node").mkdir(parents=True)
    (project / ".runtime" / "runtime-manifest.json").write_text("{}\n", encoding="utf-8")
    (project / ".runtime" / "node" / "node.exe").touch()
    (project / "dist" / "drawclock.exe").write_text("", encoding="utf-8")
    (project / "README.md").write_text("", encoding="utf-8")
    (project / "draw.md").write_text("", encoding="utf-8")
    (project / "example" / "draw.json").write_text("{}", encoding="utf-8")
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
    assert prefix + "runtime/runtime-manifest.json" in names
    assert prefix + "source/__main__.py" in names
    assert prefix + "json.md" not in names
    assert prefix + "rule.md" not in names
    assert not any("reload" in name or "extract" in name for name in names)
