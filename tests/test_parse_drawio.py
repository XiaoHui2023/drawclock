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
from pipeline import parse_drawio_paths  # noqa: E402


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
    config = parse_drawio_paths([path])
    by_name = {item["name"]: item for item in config}

    assert by_name["pll0"]["targets"] == ["gate0"]
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


def test_wire_folded_not_in_json() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-bridge.drawio"
    config = parse_drawio_paths([path])
    by_name = {item["name"]: item for item in config}
    assert "bus" not in by_name
    assert by_name["pll0"]["targets"] == ["clk0"]
    assert by_name["clk0"]["source"] == "pll0"


def test_wire_fanout_folded_to_pll_targets() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-fanout.drawio"
    config = parse_drawio_paths([path])
    by_name = {item["name"]: item for item in config}
    assert "bus" not in by_name
    assert by_name["pll0"]["targets"] == ["clk_a", "clk_b"]


def test_wire_left_port_duplicate_fails() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-too-many.drawio"
    with pytest.raises(ValueError, match="左端已有连接"):
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


def test_example_fig1_embeds_library_labels() -> None:
    fig1 = ROOT / "example" / "fig1.drawio"
    if not fig1.is_file():
        pytest.skip("先运行 scripts/build_example_demo.py")
    text = fig1.read_text(encoding="utf-8")
    assert 'label="' in text and ("&lt;svg" in text or "<svg" in text)
    assert "%name%" not in text
    assert "exitPerimeter=0" in text
    assert "drawclockType=source" in text


def test_example_two_figs_cross_wire_no_wire_in_json() -> None:
    fig1 = ROOT / "example" / "fig1.drawio"
    fig2 = ROOT / "example" / "fig2.drawio"
    if not fig1.is_file() or not fig2.is_file():
        pytest.skip("先运行 scripts/build_example_demo.py")
    config = parse_drawio_paths([fig1, fig2])
    kinds = {item["kind"] for item in config}
    assert "wire" not in kinds
    by_name = {item["name"]: item for item in config}
    assert set(by_name["xtal"]["targets"]) == {"gate0", "div0"}
    assert set(by_name["pll_main"]["targets"]) == {"gate0", "div0"}
    assert by_name["mux2"]["source"] == {"0": "pll_m2a", "1": "pll_m2b"}


def test_reload_restores_drawable_html_style(tmp_path: Path) -> None:
    reload_dir = ROOT / "reload"
    if str(reload_dir) not in sys.path:
        sys.path.insert(0, str(reload_dir))
    from migrate import reload_drawio_file  # noqa: E402

    fixture = ROOT / "tests" / "fixtures" / "mini-tree.drawio"
    out = tmp_path / "drawable.drawio"
    reload_drawio_file(fixture, DEFAULT_LIBRARY_PATH, out)
    text = out.read_text(encoding="utf-8")
    assert "html=1" in text
    assert "drawclockType=pll" in text
    assert 'label="' in text


def test_wire_only_fixture_fails() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-only.drawio"
    with pytest.raises(ValueError, match="未连接任何器件"):
        parse_drawio_paths([path])
