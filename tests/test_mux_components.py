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

from drawio_lib.components import mux_geometry as geom
from drawio_lib.components import simple_geometry as sgeom


@pytest.mark.parametrize("num_inputs", [2, 3, 4, 5, 6])
def test_mux_verify_geometry_passes(num_inputs: int) -> None:
    mod = importlib.import_module(f"drawio_lib.components.mux{num_inputs}")
    mod.verify_geometry()


@pytest.mark.parametrize("num_inputs", [2, 3, 4, 5, 6])
def test_mux_style_point_count(num_inputs: int) -> None:
    mod = importlib.import_module(f"drawio_lib.components.mux{num_inputs}")
    pts = mod._parse_points(mod.cell_style())
    assert len(pts) == num_inputs + 1


@pytest.mark.parametrize("num_inputs", [3, 4, 5, 6])
def test_mux_taller_than_mux2(num_inputs: int) -> None:
    mod = importlib.import_module(f"drawio_lib.components.mux{num_inputs}")
    mux2 = importlib.import_module("drawio_lib.components.mux2")
    assert mod.H >= mux2.H


def test_mux3_input_fractions() -> None:
    g = geom.compute_geometry(3)
    fracs = geom.input_fractions(3)
    assert len(g.inputs) == 3
    for port, frac in zip(g.inputs, fracs):
        assert isclose(port.trap.trap_y, g.trap.h * frac, abs_tol=0.01)


@pytest.mark.parametrize("num_inputs", [2, 3, 4, 5, 6])
def test_mux_equal_input_label_pitch(num_inputs: int) -> None:
    g = geom.compute_geometry(num_inputs)
    for i in range(len(g.inputs) - 1):
        pitch = g.inputs[i + 1].trap.cell_y - g.inputs[i].trap.cell_y
        assert pitch == geom.INPUT_PITCH


def test_mux_input_pitch_matches_standard_row_pitch() -> None:
    assert geom.INPUT_PITCH == sgeom.STANDARD_ROW_PITCH


@pytest.mark.parametrize("num_inputs", [2, 3, 4, 5, 6])
def test_mux_first_input_aligns_with_standard_port_row(num_inputs: int) -> None:
    g = geom.compute_geometry(num_inputs)
    standard_mid = sgeom.BODY_Y + sgeom.BODY_H // 2
    assert g.inputs[0].trap.cell_y == standard_mid


@pytest.mark.parametrize(
    "name",
    [
        "gate",
        "div",
        "div2",
        "div_n",
        "dto",
        "dto_n",
        "inv",
        "occ_clk_cell",
        "gen_cell",
        "bist_clk_cell",
        "occ_bist_clk_cell",
    ],
)
def test_standard_body_components_share_cell_height(name: str) -> None:
    mod = importlib.import_module(f"drawio_lib.components.{name}")
    expected = sgeom.cell_h_for_body(sgeom.BODY_H)
    assert mod.H == expected
