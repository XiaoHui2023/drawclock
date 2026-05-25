from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_src_writes_clock_tree_only() -> None:
    out = ROOT / "tests" / "_tmp_cli_src"
    out.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "src"),
            "-i",
            str(ROOT / "tests" / "fixtures" / "mini-tree.drawio"),
            "-o",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert (out / "clock-tree.json").is_file()
    assert not (out / "drawio-layout.json").exists()
    config = json.loads((out / "clock-tree.json").read_text(encoding="utf-8"))
    assert any(item["name"] == "pll0" for item in config)
