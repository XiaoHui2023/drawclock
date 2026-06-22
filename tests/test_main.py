from __future__ import annotations

import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"


def test_src_dir_help_exits_zero() -> None:
    proc = subprocess.run(
        [sys.executable, str(SRC_DIR), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "clock-tree" in proc.stdout.lower() or "draw.io" in proc.stdout


def test_reload_help_exits_zero() -> None:
    proc = subprocess.run(
        [sys.executable, str(SRC_DIR), "reload", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "--library FILE" in proc.stdout


def test_reload_requires_library() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(SRC_DIR),
            "reload",
            "-i",
            str(ROOT / "tests" / "fixtures" / "mini-tree.drawio"),
            "-o",
            str(ROOT / "tests" / "_tmp_reload_out.drawio"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "library" in (proc.stderr + proc.stdout).lower()


def test_reload_batch_directory_cli(tmp_path: Path) -> None:
    source = ROOT / "test.drawio.svg"
    if not source.is_file():
        pytest.skip("需要仓库根目录 test.drawio.svg")
    inp_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    inp_dir.mkdir()
    (inp_dir / "one.drawio.svg").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(SRC_DIR),
            "reload",
            "-i",
            str(inp_dir),
            "-l",
            str(ROOT / "drawio-lib" / "drawclock.xml"),
            "-o",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert (out_dir / "one.drawio.svg").is_file()
    assert "已写入" in proc.stderr


def test_release_archive_source_layout(tmp_path: Path, monkeypatch) -> None:
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
    (project / "dist" / "drawclock.exe").write_text("", encoding="utf-8")
    (project / "README.md").write_text("", encoding="utf-8")
    (project / "json.md").write_text("", encoding="utf-8")
    (project / "rule.md").write_text("", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        "[project]\nname = \"drawclock\"\nversion = \"1.2.3\"\n",
        encoding="utf-8",
    )
    (project / "src" / "__main__.py").write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr(bundle_release, "ROOT", project)
    monkeypatch.setattr(bundle_release.platform, "system", lambda: "Windows")
    assert bundle_release.main() == 0

    archive = project / "dist" / "drawclock-1.2.3-windows.zip"
    assert archive.is_file()
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
    prefix = "drawclock-1.2.3-windows/"
    assert prefix + "pyproject.toml" in names
    assert prefix + "source/__main__.py" in names
    assert prefix + "source/pyproject.toml" not in names
    assert prefix + "source/src/__main__.py" not in names
    assert prefix + "drawclock-reload.exe" not in names
