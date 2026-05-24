from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_encode_subcommand_writes_layout() -> None:
    out = ROOT / "tests" / "_tmp_cli"
    out.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "src"),
            "encode",
            "-i",
            str(ROOT / "tests" / "fixtures" / "mini-tree.drawio"),
            "-o",
            str(out),
            "--layout",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert (out / "clock-tree.json").is_file()
    assert (out / "drawio-layout.json").is_file()
    config = json.loads((out / "clock-tree.json").read_text(encoding="utf-8"))
    assert any(item["name"] == "pll0" for item in config)
