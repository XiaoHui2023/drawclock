from __future__ import annotations

import importlib
import sys
from math import isclose
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.mark.parametrize(
    "name,port_count",
    [
        ("gate", 2),
        ("div", 2),
        ("div_r", 2),
        ("div_n", 2),
        ("cpu_gate", 4),
        ("dto", 2),
        ("dto_n", 2),
        ("inv", 2),
        ("inv_cell", 2),
        ("inv_mux", 2),
        ("clk_phase_sel", 4),
        ("cell", 2),
        ("occ_clk_cell", 2),
        ("gen_cell", 2),
        ("bist_clk_cell", 2),
        ("occ_bist_clk_cell", 1),
        ("async_marker", 2),
        ("and_gate", 3),
        ("nand", 3),
        ("buffer", 2),
        ("or_gate", 3),
        ("nor", 3),
        ("xor_gate", 3),
        ("xnor", 3),
        ("pll", 2),
        ("pll2", 3),
        ("source", 1),
        ("vdd", 1),
        ("gnd", 1),
        ("pad", 1),
        ("clock", 1),
        ("from", 1),
    ],
)
def test_simple_verify_geometry(name: str, port_count: int) -> None:
    mod = importlib.import_module(f"drawio_lib.components.{name}")
    mod.verify_geometry()
    pts = mod._parse_points(mod.cell_style())
    assert len(pts) == port_count


def test_pll_left_right_points() -> None:
    pll = importlib.import_module("drawio_lib.components.pll")
    pts = pll._parse_points(pll.cell_style())
    assert len(pts) == 2
    assert pll.G.left is not None
    assert pll.G.right is not None
    assert isclose(pts[0][0], pll.G.left.anchor.x_rel, abs_tol=0.001)
    assert isclose(pts[1][0], pll.G.right.anchor.x_rel, abs_tol=0.001)


def test_pll_preview_shows_input_and_output() -> None:
    pll = importlib.import_module("drawio_lib.components.pll")
    svg = pll.preview_svg()
    assert 'stroke="#c00"' in svg
    assert 'stroke="#090"' in svg


def test_pll2_outputs_follow_right_chevron() -> None:
    pll2 = importlib.import_module("drawio_lib.components.pll2")
    pts = pll2._parse_points(pll2.cell_style())
    assert len(pts) == 3

    from drawio_lib.components import simple_geometry as sgeom
    from drawio_lib.components.pll2_geometry import PLL2_SHOULDER_X
    from drawio_lib.components.simple_shapes import PLL_BODY_HALF_H, PLL_TIP_X

    pad = sgeom.side_pad_x(pll2.W)
    shoulder_x = pad + PLL2_SHOULDER_X
    tip_x = pad + PLL_TIP_X
    mid_y = pll2.G.body_mid_y
    top_y = mid_y - PLL_BODY_HALF_H
    bottom_y = mid_y + PLL_BODY_HALF_H
    expected = (
        pll2.G.outputs[0].anchor,
        pll2.G.outputs[1].anchor,
    )
    for pt, anchor in zip(pts[1:], expected):
        assert isclose(pt[0], anchor.x_rel, abs_tol=0.001)
        assert isclose(pt[1], anchor.y_rel, abs_tol=0.001)

    assert shoulder_x < expected[0].cell_x < tip_x
    assert shoulder_x < expected[1].cell_x < tip_x
    assert mid_y - PLL_BODY_HALF_H < expected[0].cell_y < mid_y
    assert mid_y < expected[1].cell_y < mid_y + PLL_BODY_HALF_H
    assert isclose(
        (expected[0].cell_y - top_y) / (mid_y - top_y),
        (expected[0].cell_x - shoulder_x) / (tip_x - shoulder_x),
    )
    assert isclose(
        (expected[1].cell_y - mid_y) / (bottom_y - mid_y),
        (tip_x - expected[1].cell_x) / (tip_x - shoulder_x),
    )


def test_pll2_label_keeps_kind_left() -> None:
    pll2 = importlib.import_module("drawio_lib.components.pll2")
    from drawio_lib.components import simple_geometry as sgeom
    from drawio_lib.components.simple_shapes import PLL_LABEL_CX

    cx = sgeom.side_pad_x(pll2.W) + PLL_LABEL_CX
    html = pll2.label_html()
    assert f"left:{cx / pll2.W * 100}%" in html
    assert "%pll_kind%" in html
    assert ">0</span>" not in html
    assert ">1</span>" not in html


def test_source_only_right_point() -> None:
    source = importlib.import_module("drawio_lib.components.source")
    pts = source._parse_points(source.cell_style())
    assert len(pts) == 1
    assert source.G.right is not None
    assert isclose(pts[0][0], source.G.right.anchor.x_rel, abs_tol=0.001)


def test_source_no_center_src_label() -> None:
    source = importlib.import_module("drawio_lib.components.source")
    html = source.label_html()
    assert ">SRC</span>" not in html
    assert ">SRC<" not in html


def test_pad_is_hollow_and_output_labeled_c() -> None:
    pad = importlib.import_module("drawio_lib.components.pad")
    html = pad.label_html()
    assert 'fill="none"' in html
    assert ">C</span>" in html
    svg = pad.preview_svg()
    assert ">C</text>" in svg


def test_inv_has_output_bubble() -> None:
    inv = importlib.import_module("drawio_lib.components.inv")
    html = inv.label_html()
    assert "<circle " in html
    assert 'fill="#ffffff"' in html


def test_inv_cell_has_output_triangle() -> None:
    inv_cell = importlib.import_module("drawio_lib.components.inv_cell")
    html = inv_cell.label_html()
    assert html.count("<polygon ") == 2
    assert "<circle " not in html
    assert 'fill="#ffffff"' in html


def test_cell_is_unfilled_triangle() -> None:
    cell_mod = importlib.import_module("drawio_lib.components.cell")
    html = cell_mod.label_html()
    assert "<polygon " in html
    assert 'fill="none"' in html
    assert "<circle " not in html


def test_occ_clk_cell_is_cyan_triangle() -> None:
    occ = importlib.import_module("drawio_lib.components.occ_clk_cell")
    html = occ.label_html()
    assert "<polygon " in html
    assert 'fill="#b3ffff"' in html
    assert "<circle " not in html


def test_gen_cell_is_red_triangle() -> None:
    gen = importlib.import_module("drawio_lib.components.gen_cell")
    html = gen.label_html()
    assert 'fill="#ffb3b3"' in html


def test_async_has_red_cross() -> None:
    async_mod = importlib.import_module("drawio_lib.components.async_marker")
    html = async_mod.label_html()
    assert 'stroke="#cc0000"' in html


def test_or_body_is_d_with_right_bulging_left_arc() -> None:
    or_gate = importlib.import_module("drawio_lib.components.or_gate")
    and_gate = importlib.import_module("drawio_lib.components.and_gate")
    nor = importlib.import_module("drawio_lib.components.nor")
    xor_gate = importlib.import_module("drawio_lib.components.xor_gate")
    xnor = importlib.import_module("drawio_lib.components.xnor")
    from drawio_lib.components.simple_shapes import (
        LOGIC_GATE_ARC_X,
        LOGIC_GATE_BODY_R,
        LOGIC_GATE_LEFT_X,
        LOGIC_OR_LEFT_ARC_RX,
        LOGIC_OR_LEFT_ARC_RY,
        LOGIC_XOR_EXTRA_X,
    )
    from drawio_lib.xml_io import decompress_drawio_xml

    or_body = or_gate.label_html().split('fill="#d9d9d9"')[0]
    and_body = and_gate.label_html().split('fill="#d9d9d9"')[0]
    nor_body = nor.label_html().split('fill="#d9d9d9"')[0]
    xor_html = xor_gate.label_html()
    xnor_html = xnor.label_html()

    assert LOGIC_OR_LEFT_ARC_RX == LOGIC_GATE_ARC_X - LOGIC_GATE_LEFT_X
    assert LOGIC_OR_LEFT_ARC_RY == LOGIC_GATE_BODY_R
    left = _logic_left_cell(or_gate)
    arc = _logic_arc_cell(or_gate)
    extra = _logic_left_cell(or_gate) - (LOGIC_GATE_LEFT_X - LOGIC_XOR_EXTRA_X)
    top = or_gate.G.body_mid_y - LOGIC_GATE_BODY_R
    arc_snippet = f"A {LOGIC_OR_LEFT_ARC_RX} {LOGIC_OR_LEFT_ARC_RY}"
    and_top = f"M {left} {top} L {arc} {top}"
    for body in (or_body, nor_body):
        assert arc_snippet in body
        assert " Q " not in body
        assert and_top in body
        assert f"A {LOGIC_OR_LEFT_ARC_RX} {LOGIC_OR_LEFT_ARC_RY} 0 0 0 {left} {top}" in body
    for html in (xor_html, xnor_html):
        assert html.count(arc_snippet) == 2
        assert and_top in html
        assert f"M {extra} {top} A" not in html
    assert and_top in and_body
    assert arc_snippet not in and_body

    for mod in (or_gate, nor, xor_gate, xnor):
        library_xml = decompress_drawio_xml(mod.library_entry()["xml"])
        assert arc_snippet in library_xml
        assert f"M {left} {top}" in library_xml
        expected_arcs = 2 if mod in (xor_gate, xnor) else 1
        assert library_xml.count(arc_snippet) == expected_arcs


def test_xor_input_leads_meet_extra_arc() -> None:
    """XOR/XNOR input stubs must end on the extra arc (same at_y rule as OR on main arc)."""
    import re

    from drawio_lib.components import simple_geometry as sgeom
    from drawio_lib.components.simple_shapes import (
        LOGIC_INPUT_BOTTOM_Y,
        LOGIC_INPUT_TOP_Y,
        LOGIC_XOR_EXTRA_X,
        _or_left_arc_x_at_y,
        xor_extra_input_arc_x_at_y,
    )

    xor_gate = importlib.import_module("drawio_lib.components.xor_gate")
    xnor = importlib.import_module("drawio_lib.components.xnor")
    pad = sgeom.side_pad_x(xor_gate.W)
    extra_left = pad + LOGIC_XOR_EXTRA_X
    main_left = _logic_left_cell(xor_gate)
    mid = xor_gate.G.body_mid_y
    for y in (LOGIC_INPUT_TOP_Y, LOGIC_INPUT_BOTTOM_Y):
        expected = xor_extra_input_arc_x_at_y(extra_left=extra_left, mid=mid, y=y)
        main_inner = _or_left_arc_x_at_y(body_left=main_left, mid=mid, y=y)
        assert expected < main_inner, (
            f"extra arc at_y={expected} must stay left of main body inner bulge={main_inner}"
        )
    for mod in (xor_gate, xnor):
        html = mod.label_html()
        for m in re.finditer(
            r'<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="\2"',
            html,
        ):
            y = float(m.group(2))
            if y not in (float(LOGIC_INPUT_TOP_Y), float(LOGIC_INPUT_BOTTOM_Y)):
                continue
            end_x = float(m.group(3))
            expected = xor_extra_input_arc_x_at_y(extra_left=extra_left, mid=mid, y=y)
            assert isclose(end_x, expected, abs_tol=0.02), (
                f"{mod.TITLE} input at y={y}: end_x={end_x}, expected extra arc x={expected}"
            )


def test_on_disk_drawclock_xml_or_shape() -> None:
    """drawio-lib/drawclock.xml on disk must match generated or gate body."""
    import json
    import re

    from drawio_lib.xml_io import decompress_drawio_xml

    raw = (ROOT / "drawio-lib" / "drawclock.xml").read_text(encoding="utf-8")
    match = re.search(r"<mxlibrary>(.*)</mxlibrary>", raw, re.DOTALL)
    assert match, "drawclock.xml must contain mxlibrary"
    entries = json.loads(match.group(1))
    or_entry = next(e for e in entries if e.get("title") == "or")
    xml = decompress_drawio_xml(or_entry["xml"])
    assert "A 10 12" in xml
    assert "Q 54 30" not in xml
    assert "M 8 18 L 18 18 A 12 12 0 1 1 18 42 L 8 42 A 10 12 0 0 0 8 18" in xml


def _logic_left_cell(mod) -> float:
    from drawio_lib.components import simple_geometry as sgeom
    from drawio_lib.components.simple_shapes import LOGIC_GATE_LEFT_X

    return sgeom.side_pad_x(mod.W) + LOGIC_GATE_LEFT_X


def _logic_arc_cell(mod) -> float:
    from drawio_lib.components import simple_geometry as sgeom
    from drawio_lib.components.simple_shapes import LOGIC_GATE_ARC_X

    return sgeom.side_pad_x(mod.W) + LOGIC_GATE_ARC_X


def test_pll_center_label_on_graphic() -> None:
    pll = importlib.import_module("drawio_lib.components.pll")
    from drawio_lib.components import simple_geometry as sgeom
    from drawio_lib.components.simple_shapes import PLL_LABEL_CX

    cx = sgeom.side_pad_x(pll.W) + PLL_LABEL_CX
    left_pct = cx / pll.W * 100
    html = pll.label_html()
    assert f"left:{left_pct}%" in html
    assert "%pll_kind%" in html


def test_div_r_center_label_two_lines() -> None:
    div_r = importlib.import_module("drawio_lib.components.div_r")
    html = div_r.label_html()
    assert ">÷</span>" in html
    assert "%ratio%" in html
    mid = div_r.G.body_mid_y
    ratio_y = mid + 6 - 4 + 2
    symbol_y = ratio_y - 9
    symbol_top = symbol_y / div_r.GRAPHIC_H * 100
    ratio_top = ratio_y / div_r.GRAPHIC_H * 100
    assert f"top:{symbol_top}%" in html
    assert f"top:{ratio_top}%" in html
    assert "font-size:8px" in html


def test_div_r_library_object_carries_ratio_default() -> None:
    div_r = importlib.import_module("drawio_lib.components.div_r")
    frag = div_r.cell_fragment("2")
    assert 'ratio="2"' in frag
    assert "%ratio%" in frag


def test_pll_library_object_carries_pll_kind_default() -> None:
    pll = importlib.import_module("drawio_lib.components.pll")
    frag = pll.cell_fragment("2")
    assert 'pll_kind="SC"' in frag
    assert "%pll_kind%" in frag
    assert "drawclockKind=pll;" in pll.cell_style()


def test_pll2_library_object_carries_unified_kind_in_style() -> None:
    pll2 = importlib.import_module("drawio_lib.components.pll2")
    style = pll2.cell_style()
    assert "drawclockType=pll2;" in style
    assert "drawclockKind=pll;" in style


@pytest.mark.parametrize(
    ("module_name", "inv_kind"),
    [("inv", "inv"), ("inv_cell", "inv_cell"), ("inv_mux", "inv_mux")],
)
def test_inv_library_object_carries_kind_in_style(module_name: str, inv_kind: str) -> None:
    mod = importlib.import_module(f"drawio_lib.components.{module_name}")
    frag = mod.cell_fragment("2")
    style = mod.cell_style()
    assert 'kind="' not in frag
    assert 'inv_kind="' not in frag
    assert f"drawclockKind=inv;" in style
    assert f"drawclockInvKind={inv_kind};" in style


@pytest.mark.parametrize(
    ("module_name", "source_kind"),
    [("source", "source"), ("vdd", "vdd"), ("gnd", "gnd"), ("pad", "pad")],
)
def test_clock_source_library_object_carries_kind_in_style(
    module_name: str, source_kind: str
) -> None:
    mod = importlib.import_module(f"drawio_lib.components.{module_name}")
    frag = mod.cell_fragment("2")
    style = mod.cell_style()
    assert 'kind="' not in frag
    assert 'source_kind="' not in frag
    assert "drawclockKind=source;" in style
    assert f"drawclockSourceKind={source_kind};" in style


@pytest.mark.parametrize(
    ("module_name", "cell_kind"),
    [
        ("cell", "cell"),
        ("occ_clk_cell", "occ_clk_cell"),
        ("gen_cell", "gen_cell"),
        ("bist_clk_cell", "bist_clk_cell"),
        ("occ_bist_clk_cell", "occ_bist_clk_cell"),
    ],
)
def test_cell_library_object_carries_kind_in_style(module_name: str, cell_kind: str) -> None:
    mod = importlib.import_module(f"drawio_lib.components.{module_name}")
    frag = mod.cell_fragment("2")
    style = mod.cell_style()
    assert 'kind="' not in frag
    assert 'cell_kind="' not in frag
    assert "drawclockKind=cell;" in style
    assert f"drawclockCellKind={cell_kind};" in style


def test_gate_library_object_carries_kind_in_style() -> None:
    gate = importlib.import_module("drawio_lib.components.gate")
    frag = gate.cell_fragment("2")
    style = gate.cell_style()
    assert 'kind="' not in frag
    assert "drawclockKind=gate;" in style


@pytest.mark.parametrize(
    "module_name",
    ["mux2", "mux3", "mux4", "mux5", "mux6"],
)
def test_mux_library_object_carries_unified_kind_in_style(module_name: str) -> None:
    mod = importlib.import_module(f"drawio_lib.components.{module_name}")
    frag = mod.cell_fragment("2")
    style = mod.cell_style()
    assert 'kind="' not in frag
    assert f"drawclockType={module_name};" in style
    assert "drawclockKind=mux;" in style


@pytest.mark.parametrize("name", ["gate", "inv", "mux2"])
def test_instance_name_not_in_svg(name: str) -> None:
    mod = importlib.import_module(f"drawio_lib.components.{name}")
    html = mod.label_html()
    assert "%name%</text>" not in html
    assert "font-size:11px" in html
    assert "transform:scale(" not in html
    assert "position:absolute" in html
    assert "overflow:visible" in html
    assert f"width:{mod.W}px" in html
    assert f"height:{mod.H}px" in html
    assert "overflow=visible" in mod.cell_style()
    assert "overflow=fill" not in mod.cell_style()
    assert "resizable=0" in mod.cell_style()


def test_cpu_gate_labels_module_and_outputs() -> None:
    cpu_gate = importlib.import_module("drawio_lib.components.cpu_gate")
    from drawio_lib.components import module_geometry as mgeom
    from drawio_lib.components.simple_geometry import STANDARD_ROW_PITCH

    html = cpu_gate.label_html()
    g = cpu_gate.G
    assert g.cell_w > 40
    assert ">cpu_gate</span>" in html
    for label in ("hclk_en", "hclk", "clk_arm_core"):
        assert f">{label}</span>" in html
    assert "<line " in html
    assert "transform:translate(-100%,-50%)" in html

    pts = cpu_gate._parse_points(cpu_gate.cell_style())
    assert isclose(pts[0][0], g.box_left / cpu_gate.W, abs_tol=0.002)
    assert isclose(pts[0][1], g.left.anchor.cell_y / cpu_gate.H, abs_tol=0.002)
    assert pts[0][1] > g.header_bottom / cpu_gate.H
    for index in range(len(g.outputs) - 1):
        pitch = g.outputs[index + 1].anchor.cell_y - g.outputs[index].anchor.cell_y
        assert pitch == STANDARD_ROW_PITCH
        assert pitch == mgeom.OUTPUT_PITCH


def test_clk_phase_sel_ports_on_right_border() -> None:
    mod = importlib.import_module("drawio_lib.components.clk_phase_sel")
    from drawio_lib.components import simple_geometry as sgeom
    from drawio_lib.components.simple_shapes import (
        CLK_PHASE_SEL_BOX_LEFT,
        CLK_PHASE_SEL_BOX_RIGHT,
        clk_phase_sel_output_positions,
    )

    pts = mod._parse_points(mod.cell_style())
    pad = sgeom.side_pad_x(mod.W)
    mid = mod.G.body_mid_y
    assert isclose(pts[0][0], (pad + CLK_PHASE_SEL_BOX_LEFT) / mod.W, abs_tol=0.001)
    assert isclose(pts[0][1], mid / mod.H, abs_tol=0.001)
    for pt, (design_x, cell_y) in zip(
        pts[1:], clk_phase_sel_output_positions(mid), strict=True
    ):
        assert design_x == CLK_PHASE_SEL_BOX_RIGHT
        assert isclose(pt[0], (pad + CLK_PHASE_SEL_BOX_RIGHT) / mod.W, abs_tol=0.001)
        assert isclose(pt[1], cell_y / mod.H, abs_tol=0.001)


def test_from_ports_on_graphic() -> None:
    from_mod = importlib.import_module("drawio_lib.components.from")
    pts = from_mod._parse_points(from_mod.cell_style())
    assert len(pts) == 1
    assert isclose(pts[0][0], 1.0, abs_tol=0.02)


def test_clock_instance_name_below_graphic() -> None:
    clock = importlib.import_module("drawio_lib.components.clock")
    from drawio_lib.components.simple_shapes import CLOCK_WAVE_AMP

    rect = clock.G.body
    cx = rect.x + rect.w // 2
    wave_bottom = clock.G.body_mid_y + CLOCK_WAVE_AMP
    html = clock.label_html()
    assert f"left:{cx / clock.W * 100}%" in html
    assert f"top:{wave_bottom / clock.H * 100}%" in html


def test_clock_only_left_point() -> None:
    clock = importlib.import_module("drawio_lib.components.clock")
    pts = clock._parse_points(clock.cell_style())
    assert len(pts) == 1
    from drawio_lib.components.simple_shapes import CLOCK_NAME_SIDE_PAD, CLOCK_WAVE_AMP, CLOCK_WAVE_W

    assert isclose(pts[0][0], CLOCK_NAME_SIDE_PAD / clock.W, abs_tol=0.002)
    y_lo = clock.G.body_mid_y + CLOCK_WAVE_AMP
    assert isclose(pts[0][1], y_lo / clock.H, abs_tol=0.002)
    assert clock.W == 40
    assert CLOCK_WAVE_W == 31
    assert "%func_freq%" not in clock.label_html()
    assert "%scan_freq%" not in clock.label_html()
    assert "%bist_freq%" not in clock.label_html()
