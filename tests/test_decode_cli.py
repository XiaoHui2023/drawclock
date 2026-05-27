from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_src_writes_clock_tree_only() -> None:
    out = ROOT / "tests" / "_tmp_cli_src" / "clock-tree.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "src"),
            "-i",
            str(ROOT / "tests" / "fixtures" / "mini-tree.drawio"),
            "-l",
            str(ROOT / "drawio-lib" / "drawclock.xml"),
            "-o",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.is_file()
    config = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(config, dict)
    assert "pll0" in config
    assert config["pll0"]["kind"] == "pll"
