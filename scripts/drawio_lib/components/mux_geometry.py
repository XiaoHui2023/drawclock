"""Parameterized trapezoid mux geometry (2..N left inputs, one right output)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from drawio_lib.components.simple_geometry import (
    MAX_INSTANCE_GAP,
    MUX_BODY_PAD_BOTTOM,
    NAME_H,
    W,
    side_pad_x,
)

TRAP_MARGIN_X = 8
TRAP_Y = 6
TRAP_W = 24
TRAP_RIGHT_MARGIN_Y = 10
INPUT_PITCH = 16

POINT_FIXED = 0


@dataclass(frozen=True)
class TrapRect:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class Anchor:
    trap_x: float
    trap_y: float
    cell_x: int
    cell_y: int
    label_x: int
    label_y: int
    x_rel: float
    y_rel: float


@dataclass(frozen=True)
class Port:
    trap: Anchor
    outline_cell_x: int
    outline_x_rel: float
    outline_y_rel: float
    stub_x1: int
    stub_y1: int
    stub_x2: int
    stub_y2: int


@dataclass(frozen=True)
class MuxGeometry:
    num_inputs: int
    trap: TrapRect
    inputs: tuple[Port, ...]
    out: Port
    mux_h: int
    cell_h: int


def trap_x() -> int:
    return side_pad_x(W) + TRAP_MARGIN_X


def trap_h(num_inputs: int) -> int:
    if num_inputs < 2:
        raise ValueError(f"mux needs at least 2 inputs, got {num_inputs}")
    return max(64, 20 * num_inputs)


def trap_right_top_y(trap_height: int) -> int:
    return TRAP_RIGHT_MARGIN_Y


def trap_right_bot_y(trap_height: int) -> int:
    return trap_height - TRAP_RIGHT_MARGIN_Y


def trap_rect(num_inputs: int) -> TrapRect:
    h = trap_h(num_inputs)
    return TrapRect(x=trap_x(), y=TRAP_Y, w=TRAP_W, h=h)


def mux_h(num_inputs: int) -> int:
    t = trap_rect(num_inputs)
    return t.y + t.h + MUX_BODY_PAD_BOTTOM


def cell_h(num_inputs: int) -> int:
    return mux_h(num_inputs) + MAX_INSTANCE_GAP + NAME_H


def input_trap_y_positions(num_inputs: int, trap_height: int) -> tuple[float, ...]:
    if num_inputs < 2:
        raise ValueError(f"mux needs at least 2 inputs, got {num_inputs}")
    span = (num_inputs - 1) * INPUT_PITCH
    if span > trap_height:
        raise ValueError(
            f"mux{num_inputs} trap height {trap_height} too short for "
            f"{num_inputs} inputs at pitch {INPUT_PITCH}"
        )
    y0 = (trap_height - span) / 2
    return tuple(y0 + i * INPUT_PITCH for i in range(num_inputs))


def input_fractions(num_inputs: int) -> tuple[float, ...]:
    height = trap_h(num_inputs)
    return tuple(y / height for y in input_trap_y_positions(num_inputs, height))


def trap_left_point(fraction: float, *, trap_height: int) -> tuple[float, float]:
    if not 0.0 <= fraction <= 1.0:
        raise ValueError(f"fraction must be 0..1, got {fraction}")
    return 0.0, trap_height * fraction


def trap_right_midpoint(*, trap_height: int) -> tuple[float, float]:
    top = trap_right_top_y(trap_height)
    bot = trap_right_bot_y(trap_height)
    return float(TRAP_W), (top + bot) / 2


def trap_to_cell(
    trap_xv: float,
    trap_yv: float,
    *,
    rect: TrapRect,
) -> tuple[int, int]:
    return rect.x + round(trap_xv), rect.y + round(trap_yv)


def trap_to_label(trap_xv: float, trap_yv: float) -> tuple[int, int]:
    return round(trap_xv), round(trap_yv)


def cell_to_rel(cell_x: int, cell_y: int, *, w: int = W, h: int) -> tuple[float, float]:
    return cell_x / w, cell_y / h


def make_anchor(trap_xv: float, trap_yv: float, *, rect: TrapRect, cell_height: int) -> Anchor:
    cx, cy = trap_to_cell(trap_xv, trap_yv, rect=rect)
    lx, ly = trap_to_label(trap_xv, trap_yv)
    rx, ry = cell_to_rel(cx, cy, h=cell_height)
    return Anchor(
        trap_x=trap_xv,
        trap_y=trap_yv,
        cell_x=cx,
        cell_y=cy,
        label_x=lx,
        label_y=ly,
        x_rel=rx,
        y_rel=ry,
    )


def _stub_endpoints(
    trap: Anchor, outline_cell_x: int, *, side: Literal["left", "right"]
) -> tuple[int, int, int, int]:
    y = trap.cell_y
    if side == "left":
        return outline_cell_x, y, trap.cell_x, y
    return trap.cell_x, y, outline_cell_x, y


def make_port(
    trap_xv: float,
    trap_yv: float,
    *,
    side: Literal["left", "right"],
    rect: TrapRect,
    cell_height: int,
) -> Port:
    trap = make_anchor(trap_xv, trap_yv, rect=rect, cell_height=cell_height)
    if side == "left":
        outline_x = 0
        outline_x_rel = 0.0
    else:
        outline_x = W
        outline_x_rel = 1.0
    outline_y_rel = trap.y_rel
    x1, y1, x2, y2 = _stub_endpoints(trap, outline_x, side=side)
    return Port(
        trap=trap,
        outline_cell_x=outline_x,
        outline_x_rel=outline_x_rel,
        outline_y_rel=outline_y_rel,
        stub_x1=x1,
        stub_y1=y1,
        stub_x2=x2,
        stub_y2=y2,
    )


def compute_geometry(num_inputs: int) -> MuxGeometry:
    if num_inputs < 2:
        raise ValueError(f"mux needs at least 2 inputs, got {num_inputs}")
    rect = trap_rect(num_inputs)
    height = cell_h(num_inputs)
    inputs = tuple(
        make_port(
            *trap_left_point(frac, trap_height=rect.h),
            side="left",
            rect=rect,
            cell_height=height,
        )
        for frac in input_fractions(num_inputs)
    )
    out = make_port(
        *trap_right_midpoint(trap_height=rect.h),
        side="right",
        rect=rect,
        cell_height=height,
    )
    return MuxGeometry(
        num_inputs=num_inputs,
        trap=rect,
        inputs=inputs,
        out=out,
        mux_h=mux_h(num_inputs),
        cell_h=height,
    )


def port_drawio_point(port: Port) -> str:
    return (
        f"{port.trap.x_rel:.4f},{port.trap.y_rel:.4f},"
        f"{POINT_FIXED},0,0"
    )


def trapezoid_cell_points(rect: TrapRect) -> str:
    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    rt = trap_right_top_y(h)
    rb = trap_right_bot_y(h)
    return (
        f"{x},{y} {x},{y + h} "
        f"{x + w},{y + rb} "
        f"{x + w},{y + rt}"
    )
