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
        ("dto", 2),
        ("inv", 2),
        ("pll", 2),
        ("pll2", 3),
        ("source", 1),
        ("clock", 1),
        ("wire", 2),
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


def test_pll2_label_keeps_kind_left_and_adds_output_numbers() -> None:
    pll2 = importlib.import_module("drawio_lib.components.pll2")
    from drawio_lib.components import simple_geometry as sgeom
    from drawio_lib.components.simple_shapes import PLL_LABEL_CX

    cx = sgeom.side_pad_x(pll2.W) + PLL_LABEL_CX
    html = pll2.label_html()
    assert f"left:{cx / pll2.W * 100}%" in html
    assert "%pll_kind%" in html
    assert ">0</span>" in html
    assert ">1</span>" in html


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


def test_pll_center_label_on_graphic() -> None:
    pll = importlib.import_module("drawio_lib.components.pll")
    from drawio_lib.components import simple_geometry as sgeom
    from drawio_lib.components.simple_shapes import PLL_LABEL_CX

    cx = sgeom.side_pad_x(pll.W) + PLL_LABEL_CX
    left_pct = cx / pll.W * 100
    html = pll.label_html()
    assert f"left:{left_pct}%" in html
    assert "%pll_kind%" in html


def test_pll_library_object_carries_pll_kind_default() -> None:
    pll = importlib.import_module("drawio_lib.components.pll")
    frag = pll.cell_fragment("2")
    assert 'pll_kind="SC"' in frag
    assert "%pll_kind%" in frag


@pytest.mark.parametrize("name", ["gate", "inv", "mux2"])
def test_instance_name_not_in_svg(name: str) -> None:
    mod = importlib.import_module(f"drawio_lib.components.{name}")
    html = mod.label_html()
    assert "%name%</text>" not in html
    assert "font-size:11px" in html
    assert "transform:scale(" not in html
    assert "position:absolute" in html
    assert "overflow:visible" in html
    assert "width:100%" in html
    assert "height:100%" in html
    assert "overflow=fill" in mod.cell_style()
    assert "overflow=visible" not in mod.cell_style()


def test_wire_ports_on_graphic() -> None:
    wire = importlib.import_module("drawio_lib.components.wire")
    pts = wire._parse_points(wire.cell_style())
    assert len(pts) == 2
    pad = 40 / 120
    assert isclose(pts[0][0], pad, abs_tol=0.02)
    assert isclose(pts[1][0], 1.0 - pad, abs_tol=0.02)


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
    from drawio_lib.components.label_attrs import CLOCK_FREQ_GAP_PX
    from drawio_lib.components.simple_shapes import CLOCK_BODY_MARGIN_X, CLOCK_LEFT_PAD, CLOCK_WAVE_W

    wave_left_rel = (CLOCK_LEFT_PAD + CLOCK_BODY_MARGIN_X) / clock.W
    assert isclose(pts[0][0], wave_left_rel, abs_tol=0.02)
    assert clock.W == 260
    assert CLOCK_WAVE_W == 36
    assert "%freq%hz)" in clock.label_html()
    assert f"width:{CLOCK_FREQ_GAP_PX}px" in clock.label_html()
    assert "width:%freq_gap%px" not in clock.label_html()
