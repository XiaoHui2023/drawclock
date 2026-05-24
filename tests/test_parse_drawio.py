from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from drawio_graph import _parse_points  # noqa: E402
from drawio_library import (  # noqa: E402
    DEFAULT_LIBRARY_PATH,
    load_library_cell_styles,
    load_library_shapes,
)
from pipeline import decode_to_drawio, parse_drawio_paths  # noqa: E402


def test_parse_points_reads_all_mux_ports() -> None:
    style = (
        "drawclockType=mux3;points=[[0.3500,0.2075,0,0,0],"
        "[0.3500,0.3585,0,0,0],[0.3500,0.5094,0,0,0],[0.6500,0.3585,0,0,0]];"
    )
    pts = _parse_points(style)
    assert len(pts) == 4
    assert pts[0] == (0.35, 0.2075)
    assert pts[-1] == (0.65, 0.3585)


def test_mini_tree_drawio() -> None:
    path = ROOT / "tests" / "fixtures" / "mini-tree.drawio"
    config = parse_drawio_paths([path]).config
    by_name = {item["name"]: item for item in config}

    assert by_name["pll0"]["target"] == "gate0"
    assert by_name["gate0"]["source"] == "pll0"
    assert by_name["gate0"]["target"] == "clk0"
    assert by_name["clk0"]["source"] == "gate0"
    assert by_name["clk0"]["freq"] == "100"
    for item in config:
        assert "kind" in item


def test_mux_kind_exported_as_mux() -> None:
    from config_export import export_kind

    assert export_kind("mux2") == "mux"
    assert export_kind("mux6") == "mux"
    assert export_kind("gate") == "gate"


def test_wire_in_json_with_connections() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-bridge.drawio"
    config = parse_drawio_paths([path]).config
    by_name = {item["name"]: item for item in config}
    assert by_name["bus"] == {
        "name": "bus",
        "kind": "wire",
        "connections": ["pll0", "clk0"],
    }
    assert by_name["pll0"]["kind"] == "pll"
    assert by_name["pll0"]["target"] == "bus"
    assert by_name["clk0"]["kind"] == "clock"
    assert by_name["clk0"]["source"] == "bus"


def test_wire_more_than_two_devices_fails() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-too-many.drawio"
    with pytest.raises(ValueError, match="1 或 2"):
        parse_drawio_paths([path])


def test_duplicate_device_name_fails() -> None:
    path = ROOT / "tests" / "fixtures" / "duplicate-name.drawio"
    with pytest.raises(ValueError, match="重复"):
        parse_drawio_paths([path])


def test_library_styles_load() -> None:
    styles = load_library_cell_styles(DEFAULT_LIBRARY_PATH)
    assert "pll" in styles and "html=1" in styles["pll"]
    assert "mux2" in styles
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    assert "pll" in shapes and "<svg" in shapes["pll"].label


def test_demo_drawio_embeds_library_labels() -> None:
    demo = ROOT / "example" / "demo.drawio"
    if not demo.is_file():
        pytest.skip("先运行 scripts/build_example_demo.py")
    text = demo.read_text(encoding="utf-8")
    assert 'label="' in text and ("&lt;svg" in text or "<svg" in text)
    assert "%name%" not in text
    assert "exitX=0.7" in text or "exitX=1;" not in text[:5000]


def test_decode_restores_drawable_html_style(tmp_path: Path) -> None:
    fixture = ROOT / "tests" / "fixtures" / "mini-tree.drawio"
    out = tmp_path / "drawable.drawio"
    first = parse_drawio_paths([fixture], include_layout=True)
    from drawio_layout import layout_to_dict  # noqa: E402

    config_path = tmp_path / "clock-tree.json"
    layout_path = tmp_path / "drawio-layout.json"
    config_path.write_text(
        json.dumps(first.config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    layout_path.write_text(
        json.dumps(layout_to_dict(first.layout), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    decode_to_drawio(config_path, layout_path, DEFAULT_LIBRARY_PATH, out)
    text = out.read_text(encoding="utf-8")
    assert "html=1" in text
    assert "drawclockType=pll" in text
    assert 'label="' in text


def test_wire_only_fixture_fails() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-only.drawio"
    with pytest.raises(ValueError, match="连线|未连接"):
        parse_drawio_paths([path])
