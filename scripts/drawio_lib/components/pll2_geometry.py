from __future__ import annotations

from dataclasses import dataclass

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.simple_shapes import (
    PLL_BODY_HALF_H,
    PLL_LEFT_X,
    PLL_TIP_X,
)

NUM_OUTPUTS = 2
POINT_FIXED = 0
PLL2_SHOULDER_X = 34


@dataclass(frozen=True)
class Pll2Geometry:
    left: geom.Port
    outputs: tuple[geom.Port, ...]
    body_mid_y: int
    cell_h: int
    cell_w: int = geom.W


def output_fraction(index: int) -> float:
    return (index + 1) / (NUM_OUTPUTS + 1)


def _interpolate_line(
    start: tuple[float, float],
    end: tuple[float, float],
    fraction: float,
) -> tuple[float, float]:
    x0, y0 = start
    x1, y1 = end
    return x0 + (x1 - x0) * fraction, y0 + (y1 - y0) * fraction


def output_on_right_chevron(index: int, *, pad: int, mid: int) -> tuple[float, float]:
    """Place PLL2 outputs evenly along the right-side chevron stroke."""
    top = (pad + PLL2_SHOULDER_X, mid - PLL_BODY_HALF_H)
    tip = (pad + PLL_TIP_X, mid)
    bottom = (pad + PLL2_SHOULDER_X, mid + PLL_BODY_HALF_H)
    fraction = output_fraction(index)
    if fraction <= 0.5:
        return _interpolate_line(top, tip, fraction * 2)
    return _interpolate_line(tip, bottom, (fraction - 0.5) * 2)


def compute_geometry() -> Pll2Geometry:
    rect = geom.body_rect()
    mid = geom.body_mid_y(rect)
    height = geom.cell_h_for_body(geom.BODY_H)
    pad = geom.side_pad_x(geom.W)
    left = geom.make_port(
        pad + PLL_LEFT_X,
        mid,
        side="left",
        cell_height=height,
        cell_w=geom.W,
    )
    outputs: list[geom.Port] = []
    for index in range(NUM_OUTPUTS):
        x, y = output_on_right_chevron(index, pad=pad, mid=mid)
        outputs.append(
            geom.make_port(
                x,
                y,
                side="right",
                cell_height=height,
                cell_w=geom.W,
            )
        )
    return Pll2Geometry(
        left=left,
        outputs=tuple(outputs),
        body_mid_y=mid,
        cell_h=height,
    )


def reheight_pll2_geometry(g: Pll2Geometry, cell_h: int) -> Pll2Geometry:
    left = geom.reanchor_port(g.left, cell_h=cell_h)
    outputs = tuple(geom.reanchor_port(port, cell_h=cell_h) for port in g.outputs)
    return Pll2Geometry(
        left=left,
        outputs=outputs,
        body_mid_y=g.body_mid_y,
        cell_h=cell_h,
    )


def port_drawio_point(port: geom.Port) -> str:
    a = port.anchor
    return f"{a.x_rel:.4f},{a.y_rel:.4f},{POINT_FIXED},0,0"
