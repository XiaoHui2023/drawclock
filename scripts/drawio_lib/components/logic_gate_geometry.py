from __future__ import annotations

from dataclasses import dataclass

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.simple_shapes import (
    LOGIC_INPUT_BOTTOM_Y,
    LOGIC_INPUT_TOP_Y,
    logic_input_port_x,
    logic_output_port_x,
)

POINT_FIXED = 0
OUTPUT_RIGHT_X = geom.DESIGN_W - 2


@dataclass(frozen=True)
class LogicGateGeometry:
    inputs: tuple[geom.Port, ...]
    output: geom.Port
    body_mid_y: int
    cell_h: int
    cell_w: int = geom.W


def compute_logic_gate_geometry(
    *,
    dual_input: bool,
    with_bubble: bool = False,
    buffer: bool = False,
) -> LogicGateGeometry:
    rect = geom.body_rect()
    mid = geom.body_mid_y(rect)
    height = geom.cell_h_for_body(geom.BODY_H)
    pad = geom.side_pad_x(geom.W)
    input_x = pad + logic_input_port_x()
    output_x = pad + logic_output_port_x(with_bubble=with_bubble, buffer=buffer)
    inputs: list[geom.Port] = []
    if dual_input:
        for y in (LOGIC_INPUT_TOP_Y, LOGIC_INPUT_BOTTOM_Y):
            inputs.append(
                geom.make_port(
                    input_x,
                    y,
                    side="left",
                    cell_height=height,
                    cell_w=geom.W,
                )
            )
    else:
        inputs.append(
            geom.make_port(
                input_x,
                mid,
                side="left",
                cell_height=height,
                cell_w=geom.W,
            )
        )
    output = geom.make_port(
        output_x,
        mid,
        side="right",
        cell_height=height,
        cell_w=geom.W,
    )
    return LogicGateGeometry(
        inputs=tuple(inputs),
        output=output,
        body_mid_y=mid,
        cell_h=height,
    )


def reheight_logic_gate_geometry(g: LogicGateGeometry, cell_h: int) -> LogicGateGeometry:
    inputs = tuple(geom.reanchor_port(port, cell_h=cell_h) for port in g.inputs)
    output = geom.reanchor_port(g.output, cell_h=cell_h)
    return LogicGateGeometry(
        inputs=inputs,
        output=output,
        body_mid_y=g.body_mid_y,
        cell_h=cell_h,
    )


def port_drawio_point(port: geom.Port) -> str:
    anchor = port.anchor
    return f"{anchor.x_rel:.4f},{anchor.y_rel:.4f},{POINT_FIXED},0,0"
