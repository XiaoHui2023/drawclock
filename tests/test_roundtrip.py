from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from pipeline import drawio_to_clock_tree

DRAWIO_FIXTURES = [
    "tests/fixtures/mini-tree.drawio",
    "tests/fixtures/wire-bridge.drawio",
    "tests/fixtures/wire-fanout.drawio",
]


@pytest.mark.parametrize("fixture", DRAWIO_FIXTURES)
def test_clock_tree_stable_on_reencode(fixture: str) -> None:
    source = ROOT / fixture
    if not source.is_file():
        pytest.skip(f"缺少 {fixture}")
    library = ROOT / "drawio-lib" / "drawclock.xml"
    first = drawio_to_clock_tree([source], library_path=library)
    tmp = ROOT / "tests" / "_tmp_roundtrip" / f"{source.stem}-reencode"
    tmp.mkdir(parents=True, exist_ok=True)
    out_path = tmp / "clock-tree.json"
    out_path.write_text(json.dumps(first, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    second = drawio_to_clock_tree([source], library_path=library)
    assert second == first
