from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DESIGN_W = 40
W = 120
BODY_MARGIN_X = 8
BODY_Y = 6
BODY_H = 48
WIRE_BODY_Y = 10
WIRE_STROKE_Y = 14
WIRE_CELL_H = 40

MUX_BODY_PAD_BOTTOM = 4
NAME_H = 16
MAX_INSTANCE_GAP = 16
POINT_FIXED = 0

PortMode = Literal["both", "left", "right", "wire"]


@dataclass(frozen=True)
class BodyRect:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class Anchor:
    cell_x: float
    cell_y: float
    x_rel: float
    y_rel: float


@dataclass(frozen=True)
class Port:
    anchor: Anchor
    stub_x1: float
    stub_y1: float
    stub_x2: float
    stub_y2: float


@dataclass(frozen=True)
class SimpleGeometry:
    body: BodyRect
    left: Port | None
    right: Port | None
    body_mid_y: int
    cell_h: int
    cell_w: int = W


def side_pad_x(cell_w: int = W) -> int:
    return (cell_w - DESIGN_W) // 2


def clock_left_pad_x(cell_w: int) -> int:
    return cell_w - DESIGN_W - clock_right_pad_x()


def clock_right_pad_x() -> int:
    from drawio_lib.components.label_attrs import CLOCK_FREQ_GAP_PX, CLOCK_FREQ_TEXT_RESERVE_PX

    return CLOCK_FREQ_GAP_PX + CLOCK_FREQ_TEXT_RESERVE_PX


def clock_body_rect(
    *,
    height: int = BODY_H,
    margin_x: int = BODY_MARGIN_X,
    cell_w: int,
) -> BodyRect:
    pad = clock_left_pad_x(cell_w)
    return BodyRect(x=pad + margin_x, y=BODY_Y, w=DESIGN_W - 2 * margin_x, h=height)


def body_rect(
    *,
    height: int = BODY_H,
    margin_x: int = BODY_MARGIN_X,
    cell_w: int = W,
) -> BodyRect:
    pad = side_pad_x(cell_w)
    return BodyRect(x=pad + margin_x, y=BODY_Y, w=DESIGN_W - 2 * margin_x, h=height)


def body_mid_y(rect: BodyRect) -> int:
    return rect.y + rect.h // 2


def cell_h_for_body(body_height: int) -> int:
    return BODY_Y + body_height + MUX_BODY_PAD_BOTTOM + MAX_INSTANCE_GAP + NAME_H


def clock_cell_h(body_height: int = BODY_H) -> int:
    from drawio_lib.components.simple_shapes import CLOCK_WAVE_AMP
    from drawio_lib.components.label_attrs import CLOCK_INSTANCE_NAME_GAP_PX

    mid = BODY_Y + body_height // 2
    return (
        mid
        + CLOCK_WAVE_AMP
        + CLOCK_INSTANCE_NAME_GAP_PX
        + NAME_H
        + MUX_BODY_PAD_BOTTOM
    )


def cell_to_rel(cell_x: float, cell_y: float, *, w: int = W, h: int) -> tuple[float, float]:
    return cell_x / w, cell_y / h


def make_anchor(cell_x: float, cell_y: float, *, cell_height: int, cell_w: int = W) -> Anchor:
    rx, ry = cell_to_rel(cell_x, cell_y, w=cell_w, h=cell_height)
    return Anchor(cell_x=cell_x, cell_y=cell_y, x_rel=rx, y_rel=ry)


def _stub_endpoints(
    anchor: Anchor, outline_x: int, *, side: Literal["left", "right"]
) -> tuple[int, int, int, int]:
    y = anchor.cell_y
    if side == "left":
        return outline_x, y, anchor.cell_x, y
    return anchor.cell_x, y, outline_x, y


def make_port(
    cell_x: float,
    cell_y: float,
    *,
    side: Literal["left", "right"],
    cell_height: int,
    cell_w: int = W,
) -> Port:
    anchor = make_anchor(cell_x, cell_y, cell_height=cell_height, cell_w=cell_w)
    outline_x = 0 if side == "left" else cell_w
    x1, y1, x2, y2 = _stub_endpoints(anchor, outline_x, side=side)
    return Port(anchor=anchor, stub_x1=x1, stub_y1=y1, stub_x2=x2, stub_y2=y2)


def compute_wire_geometry() -> SimpleGeometry:
    height = WIRE_CELL_H
    pad = side_pad_x(W)
    left_x = pad
    right_x = pad + DESIGN_W
    left = make_port(left_x, WIRE_STROKE_Y, side="left", cell_height=height, cell_w=W)
    right = make_port(right_x, WIRE_STROKE_Y, side="right", cell_height=height, cell_w=W)
    return SimpleGeometry(
        body=BodyRect(x=pad, y=WIRE_BODY_Y, w=DESIGN_W, h=4),
        left=left,
        right=right,
        body_mid_y=WIRE_STROKE_Y,
        cell_h=height,
        cell_w=W,
    )


def compute_geometry(
    port_mode: PortMode,
    *,
    body_height: int = BODY_H,
    margin_x: int = BODY_MARGIN_X,
    port_cells: tuple[tuple[int, int], ...] | None = None,
    cell_w: int = W,
    asymmetric_clock: bool = False,
) -> SimpleGeometry:
    if port_mode == "wire":
        return compute_wire_geometry()

    if asymmetric_clock:
        rect = clock_body_rect(height=body_height, margin_x=margin_x, cell_w=cell_w)
    else:
        rect = body_rect(height=body_height, margin_x=margin_x, cell_w=cell_w)
    mid = body_mid_y(rect)
    height = clock_cell_h(body_height) if asymmetric_clock else cell_h_for_body(body_height)
    left: Port | None = None
    right: Port | None = None
    if port_cells:
        cells = list(port_cells)
        if port_mode in ("both", "left") and cells:
            lx, ly = cells.pop(0)
            left = make_port(lx, ly, side="left", cell_height=height, cell_w=cell_w)
        if port_mode in ("both", "right") and cells:
            rx, ry = cells.pop(0)
            right = make_port(rx, ry, side="right", cell_height=height, cell_w=cell_w)
    else:
        if port_mode in ("both", "left"):
            left = make_port(rect.x, mid, side="left", cell_height=height, cell_w=cell_w)
        if port_mode in ("both", "right"):
            right = make_port(
                rect.x + rect.w, mid, side="right", cell_height=height, cell_w=cell_w
            )
    return SimpleGeometry(
        body=rect,
        left=left,
        right=right,
        body_mid_y=mid,
        cell_h=height,
        cell_w=cell_w,
    )


def port_drawio_point(port: Port) -> str:
    a = port.anchor
    return f"{a.x_rel:.4f},{a.y_rel:.4f},{POINT_FIXED},0,0"
