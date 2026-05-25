from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_main_help_exits_zero() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "src"), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "clock-tree" in proc.stdout.lower() or "draw.io" in proc.stdout


def test_reload_help_exits_zero() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "reload"), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "library" in proc.stdout.lower()
