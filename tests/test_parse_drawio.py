from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import quoteattr

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
from drawio_ports import port_anchors  # noqa: E402
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

    assert config["pll0"]["pll_kind"] == "sc"
    assert "output_count" not in config["pll0"]
    assert config["pll0"]["source"] == "xtal0"
    assert config["gate0"]["source"] == "pll0"
    assert config["clk0"]["source"] == "gate0"
    assert "target" not in config["gate0"]
    assert "targets" not in config["pll0"]
    assert config["clk0"]["freq"] == 100
    for item in config.values():
        assert "kind" in item
        assert "name" not in item


def test_mux_kind_exported_as_mux() -> None:
    from config_export import export_kind

    assert export_kind("mux2") == "mux"
    assert export_kind("mux6") == "mux"
    assert export_kind("pll2") == "pll"
    assert export_kind("gate") == "gate"


def test_wire_folded_not_in_json() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-bridge.drawio"
    config = parse_drawio_paths([path])
    assert "bus" not in config
    assert config["clk0"]["source"] == "pll0"
    assert "targets" not in config["pll0"]


def test_wire_fanout_downstream_sources_only() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-fanout.drawio"
    config = parse_drawio_paths([path])
    assert "bus" not in config
    assert config["clk_a"]["source"] == "pll0"
    assert config["clk_b"]["source"] == "pll0"
    assert "targets" not in config["pll0"]


def test_gate_right_port_fanout() -> None:
    path = ROOT / "tests" / "fixtures" / "gate-fanout.drawio"
    config = parse_drawio_paths([path])
    assert config["gate0"]["source"] == "src0"
    assert config["clk_a"]["source"] == "gate0"
    assert config["clk_b"]["source"] == "gate0"
    assert "target" not in config["gate0"]


def _attr(name: str, value: str) -> str:
    return f"{name}={quoteattr(value)}"


def _library_object(
    cell_id: int,
    name: str,
    shape,
    *,
    extra: dict[str, str] | None = None,
) -> str:
    attrs = {"id": str(cell_id), "name": name, "label": "", "placeholders": "0"}
    if extra:
        attrs.update(extra)
    attr_s = " ".join(_attr(key, value) for key, value in attrs.items())
    return (
        f"<object {attr_s}>"
        f"<mxCell style={quoteattr(shape.style)} vertex=\"1\" parent=\"1\">"
        f"<mxGeometry x=\"{cell_id * 120}\" y=\"40\" width=\"{shape.w}\" "
        f"height=\"{shape.h}\" as=\"geometry\"/>"
        f"</mxCell>"
        f"</object>"
    )


def _edge(
    cell_id: int,
    source_id: int,
    target_id: int,
    source_shape,
    source_kind: str,
    source_port: str,
    target_shape,
    target_kind: str,
    target_port: str,
) -> str:
    sx, sy = port_anchors(source_shape.style, source_kind)[source_port]
    tx, ty = port_anchors(target_shape.style, target_kind)[target_port]
    style = (
        "edgeStyle=none;rounded=0;html=1;endArrow=none;startArrow=none;"
        f"exitX={sx};exitY={sy};entryX={tx};entryY={ty};"
        "exitDx=0;exitDy=0;entryDx=0;entryDy=0;exitPerimeter=0;entryPerimeter=0;"
    )
    return (
        f"<mxCell id=\"{cell_id}\" style={quoteattr(style)} edge=\"1\" parent=\"1\" "
        f"source=\"{source_id}\" target=\"{target_id}\">"
        "<mxGeometry relative=\"1\" as=\"geometry\"/>"
        "</mxCell>"
    )


def test_cell_drawio_exports_as_single_input_device(tmp_path: Path) -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    source = shapes["source"]
    cell = shapes["cell"]
    clock = shapes["clock"]
    model = (
        "<mxGraphModel><root>"
        "<mxCell id=\"0\"/><mxCell id=\"1\" parent=\"0\"/>"
        f"{_library_object(10, 'src0', source)}"
        f"{_library_object(11, 'cell0', cell)}"
        f"{_library_object(12, 'clk0', clock, extra={'freq': '25M'})}"
        f"{_edge(20, 10, 11, source, 'source', 'right', cell, 'cell', 'left')}"
        f"{_edge(21, 11, 12, cell, 'cell', 'right', clock, 'clock', 'left')}"
        "</root></mxGraphModel>"
    )
    path = tmp_path / "cell-tree.drawio"
    path.write_text(f"<mxfile><diagram>{model}</diagram></mxfile>", encoding="utf-8")

    config = parse_drawio_paths([path], library_path=DEFAULT_LIBRARY_PATH)

    assert config["cell0"] == {"kind": "cell", "source": "src0"}
    assert config["clk0"]["source"] == "cell0"
    assert config["clk0"]["freq"] == 25_000_000


def test_pll2_dual_output_source_suffix() -> None:
    path = ROOT / "tests" / "fixtures" / "pll2-tree.drawio"
    config = parse_drawio_paths([path])
    assert config["pll2_0"]["kind"] == "pll"
    assert config["pll2_0"]["output_count"] == 2
    assert config["pll2_0"]["pll_kind"] == "sc"
    assert config["pll2_0"]["source"] == "xtal0"
    assert config["gate0"]["source"] == "pll2_0[0]"
    assert config["div0"]["source"] == "pll2_0[1]"


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
    assert "pll2" in styles
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
    assert config["pll_main"]["source"] == "xtal"
    assert config["gate0"]["source"] == "pll_main"
    assert config["div0"]["source"] == "pll_main"
    assert "targets" not in config["pll_main"]
    assert "target" not in config["mux2"]
    assert config["mux2"]["source"] == {"0": "pll_m2a", "1": "pll_m2b"}
    assert config["pll_m2a"]["source"] == "osc_mux"
    assert config["pll_m2b"]["source"] == "osc_mux"
    assert config["clk_a"]["freq"] == 100_000
    assert config["clk_b"]["freq"] == 50_000_000
    assert config["clk_mux"]["freq"] == 200_000_000


def test_reload_restores_drawable_html_style(tmp_path: Path) -> None:
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
