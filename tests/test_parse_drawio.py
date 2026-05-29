from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
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

    assert config["pll0"]["targets"] == ["gate0"]
    assert config["pll0"]["pll_kind"] == "sc"
    assert config["gate0"]["source"] == "pll0"
    assert config["gate0"]["target"] == "clk0"
    assert config["clk0"]["source"] == "gate0"
    assert config["clk0"]["freq"] == 100
    for item in config.values():
        assert "kind" in item
        assert "name" not in item


def test_mux_kind_exported_as_mux() -> None:
    from config_export import export_kind

    assert export_kind("mux2") == "mux"
    assert export_kind("mux6") == "mux"
    assert export_kind("gate") == "gate"


def test_wire_folded_not_in_json() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-bridge.drawio"
    config = parse_drawio_paths([path])
    assert "bus" not in config
    assert config["pll0"]["targets"] == ["clk0"]
    assert config["clk0"]["source"] == "pll0"


def test_wire_fanout_folded_to_pll_targets() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-fanout.drawio"
    config = parse_drawio_paths([path])
    assert "bus" not in config
    assert config["pll0"]["targets"] == ["clk_a", "clk_b"]


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
    from drawio_decode import extract_mxfile_xml, iter_diagram_models  # noqa: E402

    fig1 = ROOT / "example" / "fig1.drawio"
    if not fig1.is_file():
        pytest.skip("先运行 scripts/build_example_demo.py")
    text = fig1.read_text(encoding="utf-8")
    assert "<mxGraphModel" not in text
    model_xml = ET.tostring(iter_diagram_models(extract_mxfile_xml(str(fig1)))[0], encoding="unicode")
    assert 'label="' in model_xml and ("&lt;svg" in model_xml or "<svg" in model_xml)
    assert "%name%" not in model_xml
    assert "exitPerimeter=0" in model_xml
    assert "drawclockType=source" in model_xml


def test_example_two_figs_cross_wire_no_wire_in_json() -> None:
    fig1 = ROOT / "example" / "fig1.drawio"
    fig2 = ROOT / "example" / "fig2.drawio"
    if not fig1.is_file() or not fig2.is_file():
        pytest.skip("先运行 scripts/build_example_demo.py")
    config = parse_drawio_paths([fig1, fig2])
    kinds = {item["kind"] for item in config.values()}
    assert "wire" not in kinds
    assert set(config["xtal"]["targets"]) == {"gate0", "div0"}
    assert set(config["pll_main"]["targets"]) == {"gate0", "div0"}
    assert config["mux2"]["source"] == {"0": "pll_m2a", "1": "pll_m2b"}
    assert config["clk_a"]["freq"] == 100_000
    assert config["clk_b"]["freq"] == 50_000_000
    assert config["clk_mux"]["freq"] == 200_000_000


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
    with pytest.raises(ValueError, match="两端均未连接器件"):
        parse_drawio_paths([path])


def test_wire_open_left_reports_wire_not_device_input() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-open-left.drawio"
    with pytest.raises(ValueError, match="连线 bus 左端未接上游器件") as exc:
        parse_drawio_paths([path])
    msg = str(exc.value)
    assert "gate0" in msg
    assert "输入端口未连接" not in msg


def test_wire_open_right_reports_wire_not_pll_output() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-open-right.drawio"
    with pytest.raises(ValueError, match="连线 bus 左端接了器件 pll0，右端未连接") as exc:
        parse_drawio_paths([path])
    assert "输出端口未连接" not in str(exc.value)
