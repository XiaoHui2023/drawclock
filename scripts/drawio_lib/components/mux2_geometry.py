"""mux2 geometry (re-exports mux_geometry with 2 inputs)."""

from __future__ import annotations

from dataclasses import dataclass

from drawio_lib.components.mux_geometry import (
    POINT_FIXED,
    Anchor,
    Port,
    TrapRect,
    W,
    cell_h,
    cell_to_rel,
    compute_geometry as _compute,
    input_fractions,
    make_anchor,
    make_port,
    mux_h,
    port_drawio_point,
    trap_h,
    trap_left_point,
    trap_rect,
    trap_right_midpoint,
    trap_to_cell,
    trap_to_label,
    trap_x,
    TRAP_MARGIN_X,
    TRAP_W,
    TRAP_Y,
)

NUM_INPUTS = 2

TRAP_X = trap_x()
TRAP_H = trap_h(NUM_INPUTS)
TRAP_RIGHT_TOP_Y = 10
TRAP_RIGHT_BOT_Y = TRAP_H - 10

IN0_FRAC, IN1_FRAC = input_fractions(NUM_INPUTS)


@dataclass
class Mux2Geometry:
    trap: TrapRect
    in0: Port
    in1: Port
    out: Port
    mux_h: int
    cell_h: int


def compute_geometry() -> Mux2Geometry:
    g = _compute(NUM_INPUTS)
    return Mux2Geometry(
        trap=g.trap,
        in0=g.inputs[0],
        in1=g.inputs[1],
        out=g.out,
        mux_h=g.mux_h,
        cell_h=g.cell_h,
    )


def cell_y_from_rel(y_rel: float) -> int:
    return round(y_rel * cell_h(NUM_INPUTS))


shape_h = cell_h


def shape_y_from_rel(y_rel: float) -> int:
    return cell_y_from_rel(y_rel)
