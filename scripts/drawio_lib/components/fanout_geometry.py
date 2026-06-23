from __future__ import annotations

from dataclasses import dataclass

from drawio_lib.components import simple_geometry as geom

POINT_FIXED = 0
OUTPUT_RIGHT_X = geom.DESIGN_W - 2


@dataclass(frozen=True)
class FanoutGeometry:
    left: geom.Port
    outputs: tuple[geom.Port, ...]
    body_mid_y: int
    cell_h: int
    cell_w: int = geom.W


def _output_cell_positions(
    count: int,
    *,
    pad: int,
    top_y: int,
    bottom_y: int,
) -> list[tuple[float, float]]:
    if count <= 0:
        return []
    if count == 1:
        mid = (top_y + bottom_y) / 2
        return [(pad + OUTPUT_RIGHT_X, mid)]
    span = bottom_y - top_y
    return [
        (pad + OUTPUT_RIGHT_X, top_y + span * (index + 1) / (count + 1))
        for index in range(count)
    ]


def compute_fanout_geometry(
    *,
    left_x: float,
    left_y: float,
    output_count: int,
    body_half_h: int | None = None,
    cell_w: int = geom.W,
    body_height: int = geom.BODY_H,
    output_cells: tuple[tuple[float, float], ...] | None = None,
) -> FanoutGeometry:
    rect = geom.body_rect(cell_w=cell_w, height=body_height)
    mid = geom.body_mid_y(rect)
    half_h = body_half_h if body_half_h is not None else body_height // 2 - 2
    height = geom.cell_h_for_body(body_height)
    pad = geom.side_pad_x(cell_w)
    left = geom.make_port(
        left_x,
        left_y,
        side="left",
        cell_height=height,
        cell_w=cell_w,
    )
    outputs: list[geom.Port] = []
    if output_cells:
        positions = list(output_cells)
    else:
        positions = _output_cell_positions(
            output_count,
            pad=pad,
            top_y=mid - half_h,
            bottom_y=mid + half_h,
        )
    for x, y in positions:
        outputs.append(
            geom.make_port(x, y, side="right", cell_height=height, cell_w=cell_w)
        )
    return FanoutGeometry(
        left=left,
        outputs=tuple(outputs),
        body_mid_y=mid,
        cell_h=height,
        cell_w=cell_w,
    )


def reheight_fanout_geometry(g: FanoutGeometry, cell_h: int) -> FanoutGeometry:
    left = geom.reanchor_port(g.left, cell_h=cell_h, cell_w=g.cell_w)
    outputs = tuple(
        geom.reanchor_port(port, cell_h=cell_h, cell_w=g.cell_w) for port in g.outputs
    )
    return FanoutGeometry(
        left=left,
        outputs=outputs,
        body_mid_y=g.body_mid_y,
        cell_h=cell_h,
        cell_w=g.cell_w,
    )


def port_drawio_point(port: geom.Port) -> str:
    anchor = port.anchor
    return f"{anchor.x_rel:.4f},{anchor.y_rel:.4f},{POINT_FIXED},0,0"
