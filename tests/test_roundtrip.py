from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from drawio_layout import layout_to_dict  # noqa: E402
from pipeline import decode_to_drawio, encode_drawio_paths, parse_drawio_paths  # noqa: E402

LIBRARY = ROOT / "drawio-lib" / "drawclock.xml"

DRAWIO_FIXTURES = [
    "tests/fixtures/mini-tree.drawio",
    "tests/fixtures/wire-bridge.drawio",
    "example/demo.drawio",
]


def _roundtrip_once(source: Path, work: Path) -> tuple[object, object]:
    work.mkdir(parents=True, exist_ok=True)
    rebuilt = work / f"{source.stem}-rebuilt.drawio"
    first = parse_drawio_paths([source], include_layout=True)
    decode_to_drawio(
        _write(work / "clock-tree.json", first.config),
        _write(work / "drawio-layout.json", layout_to_dict(first.layout)),
        LIBRARY,
        rebuilt,
    )
    second = parse_drawio_paths([rebuilt], include_layout=True)
    return first, second


@pytest.mark.parametrize("fixture", DRAWIO_FIXTURES)
def test_drawio_encode_decode_roundtrip(fixture: str) -> None:
    source = ROOT / fixture
    if not source.is_file():
        pytest.skip(f"缺少 {fixture}")
    tmp = ROOT / "tests" / "_tmp_roundtrip"
    first, second = _roundtrip_once(source, tmp)
    assert second.config == first.config
    assert layout_to_dict(second.layout) == layout_to_dict(first.layout)


@pytest.mark.parametrize("fixture", DRAWIO_FIXTURES)
def test_json_encode_decode_roundtrip(fixture: str) -> None:
    """图 → JSON → 图 → JSON 两次配置与布局一致。"""
    source = ROOT / fixture
    if not source.is_file():
        pytest.skip(f"缺少 {fixture}")
    tmp = ROOT / "tests" / "_tmp_roundtrip" / f"{source.stem}-json"
    first, second = _roundtrip_once(source, tmp)
    config_path, layout_path = encode_drawio_paths(
        [tmp / f"{source.stem}-rebuilt.drawio"],
        tmp / "re-encode",
        include_layout=True,
    )
    assert config_path is not None and layout_path is not None
    third_config = json.loads(config_path.read_text(encoding="utf-8"))
    third_layout = json.loads(layout_path.read_text(encoding="utf-8"))
    assert third_config == first.config
    assert third_layout == layout_to_dict(first.layout)


def _write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
