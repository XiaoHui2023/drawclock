from __future__ import annotations

import sys
from math import isclose
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from drawio_lib.components import mux2
from drawio_lib.components import mux2_geometry as geom2
from drawio_lib.components import mux_geometry as geom


def test_mux2_constants_match_geometry_module() -> None:
    assert mux2.TRAP_X == geom.trap_x()
    assert mux2.TRAP_Y == geom.TRAP_Y
    assert mux2.TRAP_W == geom.TRAP_W
    assert mux2.TRAP_H == geom.trap_h(2)
    assert mux2.W == geom.W
    assert mux2.H == geom.cell_h(2)


def test_left_inputs_on_trap_left_edge() -> None:
    g = geom2.compute_geometry()
    for port in (g.in0, g.in1):
        assert port.trap.trap_x == 0.0
        assert port.trap.cell_x == geom2.TRAP_X
        assert port.outline_cell_x == 0
        assert port.outline_x_rel == 0.0
        assert port.stub_x1 == 0
        assert port.stub_x2 == geom2.TRAP_X
    assert isclose(g.in0.trap.trap_y, geom2.TRAP_H * geom2.IN0_FRAC)
    assert g.in0.trap.cell_y == geom2.TRAP_Y + round(geom2.TRAP_H * geom2.IN0_FRAC)


def test_output_trap_vs_outline() -> None:
    g = geom2.compute_geometry()
    trap_right = geom2.TRAP_X + geom2.TRAP_W
    assert g.out.trap.trap_x == float(geom.TRAP_W)
    assert g.out.trap.cell_x == trap_right
    assert g.out.outline_cell_x == geom2.W
    assert g.out.outline_x_rel == 1.0
    assert g.out.stub_x1 == trap_right
    assert g.out.stub_x2 == geom2.W


def test_label_has_no_stub_lines() -> None:
    assert "<line " not in mux2.label_html()


def test_label_uses_non_scaling_layers() -> None:
    g = mux2.G
    assert g.in0.trap.label_y == round(g.in0.trap.trap_y)
    html = mux2.label_html()
    assert 'viewBox="0 0 80 106"' in html
    assert 'preserveAspectRatio="none"' in html
    assert "transform:scale(" not in html
    assert "width:100%" in html
    assert "%in0_label%" in html


def test_edit_data_fields_and_type_in_style() -> None:
    html = mux2.label_html()
    assert "%name%" in html
    assert "font-size:11px" in html
    assert "component_type=" not in mux2.cell_fragment("x")
    assert f"{mux2.DRAWCLOCK_TYPE_KEY}={mux2.DRAWCLOCK_TYPE_VALUE}" in mux2.cell_style()
    assert list(mux2.EDIT_DATA_ATTR_PREFIX) == [
        "in0_label",
        "in1_label",
        "name",
        "label",
    ]


def test_verify_geometry_passes() -> None:
    mux2.verify_geometry()


def test_style_points_on_trap_ports() -> None:
    style = mux2.cell_style()
    assert "overflow=fill" in style
    assert "overflow=visible" not in style
    pts = mux2._parse_points(style)
    g = mux2.G
    assert isclose(pts[0][0], g.in0.trap.x_rel, abs_tol=0.001)
    assert isclose(pts[1][0], g.in1.trap.x_rel, abs_tol=0.001)
    assert isclose(pts[2][0], g.out.trap.x_rel, abs_tol=0.001)
    for pt, port in zip(pts, (g.in0, g.in1, g.out)):
        assert isclose(pt[1], port.trap.y_rel, abs_tol=0.001)
        assert geom2.cell_y_from_rel(pt[1]) == port.trap.cell_y
