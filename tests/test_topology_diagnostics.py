from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import quoteattr

import pytest

ROOT = Path(__file__).resolve().parents[1]

from drawio_library import DEFAULT_LIBRARY_PATH, load_library_shapes
from drawio_ports import port_anchors
from pipeline import parse_drawio_paths


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


def _edge_raw(
    cell_id: int,
    source_id: int,
    target_id: int,
  *,
    exit_x: float,
    exit_y: float,
    entry_x: float,
    entry_y: float,
) -> str:
    style = (
        "edgeStyle=none;rounded=0;html=1;endArrow=none;startArrow=none;"
        f"exitX={exit_x};exitY={exit_y};entryX={entry_x};entryY={entry_y};"
        "exitDx=0;exitDy=0;entryDx=0;entryDy=0;exitPerimeter=0;entryPerimeter=0;"
    )
    return (
        f"<mxCell id=\"{cell_id}\" style={quoteattr(style)} edge=\"1\" parent=\"1\" "
        f"source=\"{source_id}\" target=\"{target_id}\">"
        "<mxGeometry relative=\"1\" as=\"geometry\"/>"
        "</mxCell>"
    )


def _write_model(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(
        f"<mxfile><diagram><mxGraphModel><root>"
        f"<mxCell id=\"0\"/><mxCell id=\"1\" parent=\"0\"/>"
        f"{body}"
        f"</root></mxGraphModel></diagram></mxfile>",
        encoding="utf-8",
    )
    return path


def test_reversed_undirected_edge_auto_orients(tmp_path: Path) -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    source = shapes["source"]
    gate = shapes["gate"]
    src_out = port_anchors(source.style, "source")["right"]
    gate_in = port_anchors(gate.style, "gate")["left"]
    body = (
        f"{_library_object(10, 'src0', source)}"
        f"{_library_object(11, 'gate0', gate)}"
        f"{_edge_raw(20, 11, 10, exit_x=gate_in[0], exit_y=gate_in[1], entry_x=src_out[0], entry_y=src_out[1])}"
    )
    path = _write_model(tmp_path, "reversed-gate.drawio", body)

    config = parse_drawio_paths([path], library_path=DEFAULT_LIBRARY_PATH)
    assert config["gate0"]["kind"] == "gate"
    assert config["gate0"]["source"] == "src0"


def test_mux_missing_in0_reports_reversed_edge_when_directed(tmp_path: Path) -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    pll = shapes["pll"]
    mux2 = shapes["mux2"]
    in0 = port_anchors(mux2.style, "mux2")["in0"]
    right = port_anchors(pll.style, "pll")["right"]
    style = (
        "edgeStyle=none;rounded=0;html=1;endArrow=classic;startArrow=none;"
        f"exitX={in0[0]};exitY={in0[1]};entryX={right[0]};entryY={right[1]};"
        "exitDx=0;exitDy=0;entryDx=0;entryDy=0;exitPerimeter=0;entryPerimeter=0;"
    )
    body = (
        f"{_library_object(10, 'pll0', pll)}"
        f"{_library_object(11, 'mux0', mux2)}"
        f"<mxCell id=\"20\" style={quoteattr(style)} edge=\"1\" parent=\"1\" "
        f"source=\"11\" target=\"10\">"
        "<mxGeometry relative=\"1\" as=\"geometry\"/>"
        "</mxCell>"
    )
    path = _write_model(tmp_path, "directed-reversed-mux.drawio", body)

    with pytest.raises(ValueError) as exc:
        parse_drawio_paths([path], library_path=DEFAULT_LIBRARY_PATH)

    msg = str(exc.value)
    assert "未连接的输入端口" in msg
    assert "in0" in msg
    assert "方向反了" in msg


def test_mux_missing_in0_reports_entry_on_output(tmp_path: Path) -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    pll = shapes["pll"]
    mux2 = shapes["mux2"]
    out = port_anchors(mux2.style, "mux2")["out"]
    right = port_anchors(pll.style, "pll")["right"]
    body = (
        f"{_library_object(10, 'pll0', pll)}"
        f"{_library_object(11, 'mux0', mux2)}"
        f"{_edge_raw(20, 10, 11, exit_x=right[0], exit_y=right[1], entry_x=out[0], entry_y=out[1])}"
    )
    path = _write_model(tmp_path, "mux-entry-out.drawio", body)

    with pytest.raises(ValueError) as exc:
        parse_drawio_paths([path], library_path=DEFAULT_LIBRARY_PATH)

    msg = str(exc.value)
    assert "entry 误接输出口 out" in msg
    assert "in0" in msg


def test_mux_missing_in0_reports_wrong_input_port(tmp_path: Path) -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    pll = shapes["pll"]
    mux2 = shapes["mux2"]
    in1 = port_anchors(mux2.style, "mux2")["in1"]
    right = port_anchors(pll.style, "pll")["right"]
    body = (
        f"{_library_object(10, 'pll0', pll)}"
        f"{_library_object(11, 'mux0', mux2)}"
        f"{_edge_raw(20, 10, 11, exit_x=right[0], exit_y=right[1], entry_x=in1[0], entry_y=in1[1])}"
    )
    path = _write_model(tmp_path, "mux-wrong-input.drawio", body)

    with pytest.raises(ValueError) as exc:
        parse_drawio_paths([path], library_path=DEFAULT_LIBRARY_PATH)

    msg = str(exc.value)
    assert "in1 已接入" in msg
    assert "尚缺 in0" in msg


def test_mux_in0_reversed_in1_missing_reports_open_in1_only(tmp_path: Path) -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    pll = shapes["pll"]
    mux2 = shapes["mux2"]
    in0 = port_anchors(mux2.style, "mux2")["in0"]
    right = port_anchors(pll.style, "pll")["right"]
    body = (
        f"{_library_object(10, 'pll0', pll)}"
        f"{_library_object(11, 'mux0', mux2)}"
        f"{_edge_raw(20, 11, 10, exit_x=in0[0], exit_y=in0[1], entry_x=right[0], entry_y=right[1])}"
    )
    path = _write_model(tmp_path, "mux-reversed-and-open.drawio", body)

    with pytest.raises(ValueError) as exc:
        parse_drawio_paths([path], library_path=DEFAULT_LIBRARY_PATH)

    msg = str(exc.value)
    assert "in1" in msg
    assert "方向反了" not in msg
    assert "in1：无入线指向 mux0" in msg


def test_mux_missing_in0_reports_no_incoming_edge(tmp_path: Path) -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    mux2 = shapes["mux2"]
    clock = shapes["clock"]
    out = port_anchors(mux2.style, "mux2")["out"]
    left = port_anchors(clock.style, "clock")["left"]
    body = (
        f"{_library_object(11, 'mux0', mux2)}"
        f"{_library_object(12, 'clk0', clock)}"
        f"{_edge_raw(20, 11, 12, exit_x=out[0], exit_y=out[1], entry_x=left[0], entry_y=left[1])}"
    )
    path = _write_model(tmp_path, "mux-no-input.drawio", body)

    with pytest.raises(ValueError) as exc:
        parse_drawio_paths([path], library_path=DEFAULT_LIBRARY_PATH)

    msg = str(exc.value)
    assert "in0：无入线指向 mux0" in msg


def test_multi_port_device_allows_unconnected_output(tmp_path: Path) -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    source = shapes["source"]
    pll = shapes["pll"]
    src_out = port_anchors(source.style, "source")["right"]
    pll_in = port_anchors(pll.style, "pll")["left"]
    body = (
        f"{_library_object(10, 'src0', source)}"
        f"{_library_object(11, 'pll0', pll)}"
        f"{_edge_raw(20, 10, 11, exit_x=src_out[0], exit_y=src_out[1], entry_x=pll_in[0], entry_y=pll_in[1])}"
    )
    path = _write_model(tmp_path, "pll-open-out.drawio", body)

    config = parse_drawio_paths([path], library_path=DEFAULT_LIBRARY_PATH)
    assert config["pll0"]["kind"] == "pll"
    assert config["pll0"]["source"] == "src0"


def test_single_port_output_device_requires_connection(tmp_path: Path) -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    source = shapes["source"]
    body = f"{_library_object(10, 'src0', source)}"
    path = _write_model(tmp_path, "source-open.drawio", body)

    with pytest.raises(ValueError, match="输出端口未连接") as exc:
        parse_drawio_paths([path], library_path=DEFAULT_LIBRARY_PATH)

    assert "src0" in str(exc.value)
    assert "right" not in str(exc.value)


def test_single_input_device_reports_generic_message(tmp_path: Path) -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    gate = shapes["gate"]
    body = f"{_library_object(10, 'gate0', gate)}"
    path = _write_model(tmp_path, "gate-open-in.drawio", body)

    with pytest.raises(ValueError, match="输入端口未连接") as exc:
        parse_drawio_paths([path], library_path=DEFAULT_LIBRARY_PATH)

    msg = str(exc.value)
    assert "gate0" in msg
    assert "left" not in msg
