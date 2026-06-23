"""Container-style module box: header band + pitched output rows."""

from __future__ import annotations

import math
from dataclasses import dataclass

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.simple_geometry import (
    BODY_H,
    BODY_Y,
    MAX_INSTANCE_GAP,
    MUX_BODY_PAD_BOTTOM,
    NAME_H,
    STANDARD_ROW_PITCH,
    W,
)

MODULE_BOX_Y = BODY_Y
MODULE_HEADER_H = 10
MODULE_BOX_MARGIN_X = 4
MODULE_PORT_LABEL_FONT_PX = 7
MODULE_PORT_LABEL_CHAR_W_RATIO = 0.58
MODULE_PORT_LABEL_PAD_X = 4
MODULE_TYPE_FONT_PX = 7
OUTPUT_PITCH = STANDARD_ROW_PITCH
PORT_ANCHOR_MARGIN = BODY_H // 2
BODY_MIN_H = BODY_H

STROKE = "#000000"
FILL = "none"
SW = 2


@dataclass(frozen=True)
class ModuleGeometry:
    output_labels: tuple[str, ...]
    cell_w: int
    cell_h: int
    box_left: int
    box_right: int
    outer_top: int
    header_bottom: int
    body_top: int
    body_bottom: int
    body_inner_h: int
    graphic_h: int
    left: geom.Port
    outputs: tuple[geom.Port, ...]
    type_label: tuple[float, float]
    port_labels: tuple[tuple[float, float, str, int, str], ...]


def module_design_width(labels: tuple[str, ...]) -> int:
    max_text = max(
        len(label) * MODULE_PORT_LABEL_FONT_PX * MODULE_PORT_LABEL_CHAR_W_RATIO
        for label in labels
    )
    inner_w = max_text + 2 * MODULE_PORT_LABEL_PAD_X
    return max(W, int(math.ceil(inner_w + 2 * MODULE_BOX_MARGIN_X)))


def module_body_inner_h(output_count: int) -> int:
    if output_count < 1:
        raise ValueError("module needs at least one output")
    span = (output_count - 1) * OUTPUT_PITCH
    return max(BODY_MIN_H, span + 2 * PORT_ANCHOR_MARGIN)


def output_body_y_positions(
    body_top: float,
    body_inner_h: float,
    output_count: int,
) -> tuple[float, ...]:
    span = (output_count - 1) * OUTPUT_PITCH
    if span > body_inner_h:
        raise ValueError(
            f"body height {body_inner_h} too short for {output_count} outputs "
            f"at pitch {OUTPUT_PITCH}"
        )
    y0 = body_top + (body_inner_h - span) / 2
    return tuple(y0 + index * OUTPUT_PITCH for index in range(output_count))


def module_cell_h(graphic_h: int) -> int:
    return MODULE_BOX_Y + graphic_h + MUX_BODY_PAD_BOTTOM


def compute_module_geometry(output_labels: tuple[str, ...]) -> ModuleGeometry:
    if not output_labels:
        raise ValueError("module needs at least one output label")
    output_count = len(output_labels)
    cell_w = module_design_width(output_labels)
    body_inner_h = module_body_inner_h(output_count)
    graphic_h = MODULE_HEADER_H + body_inner_h
    cell_h = module_cell_h(graphic_h)

    box_left = MODULE_BOX_MARGIN_X
    box_right = cell_w - MODULE_BOX_MARGIN_X
    outer_top = MODULE_BOX_Y
    header_bottom = outer_top + MODULE_HEADER_H
    body_top = header_bottom
    body_bottom = body_top + body_inner_h

    output_ys = output_body_y_positions(body_top, body_inner_h, output_count)
    body_mid = body_top + body_inner_h / 2

    left = geom.make_port(
        box_left,
        body_mid,
        side="left",
        cell_height=cell_h,
        cell_w=cell_w,
    )
    outputs = tuple(
        geom.make_port(
            box_right,
            y,
            side="right",
            cell_height=cell_h,
            cell_w=cell_w,
        )
        for y in output_ys
    )

    type_cx = (box_left + box_right) / 2
    type_cy = (outer_top + header_bottom) / 2
    label_x = box_right - MODULE_PORT_LABEL_PAD_X
    port_labels = tuple(
        (label_x, y, label, MODULE_PORT_LABEL_FONT_PX, "right")
        for y, label in zip(output_ys, output_labels, strict=True)
    )

    return ModuleGeometry(
        output_labels=output_labels,
        cell_w=cell_w,
        cell_h=cell_h,
        box_left=box_left,
        box_right=box_right,
        outer_top=outer_top,
        header_bottom=header_bottom,
        body_top=body_top,
        body_bottom=body_bottom,
        body_inner_h=body_inner_h,
        graphic_h=graphic_h,
        left=left,
        outputs=outputs,
        type_label=(type_cx, type_cy),
        port_labels=port_labels,
    )


def reheight_module_geometry(g: ModuleGeometry, cell_h: int) -> ModuleGeometry:
    left = geom.reanchor_port(g.left, cell_h=cell_h, cell_w=g.cell_w)
    outputs = tuple(
        geom.reanchor_port(port, cell_h=cell_h, cell_w=g.cell_w) for port in g.outputs
    )
    return ModuleGeometry(
        output_labels=g.output_labels,
        cell_w=g.cell_w,
        cell_h=cell_h,
        box_left=g.box_left,
        box_right=g.box_right,
        outer_top=g.outer_top,
        header_bottom=g.header_bottom,
        body_top=g.body_top,
        body_bottom=g.body_bottom,
        body_inner_h=g.body_inner_h,
        graphic_h=g.graphic_h,
        left=left,
        outputs=outputs,
        type_label=g.type_label,
        port_labels=g.port_labels,
    )


def module_body_svg(g: ModuleGeometry) -> str:
    width = g.box_right - g.box_left
    height = g.body_bottom - g.outer_top
    return (
        f'<rect x="{g.box_left}" y="{g.outer_top}" width="{width}" '
        f'height="{height}" fill="{FILL}" stroke="{STROKE}" stroke-width="{SW}"/>'
        f'<line x1="{g.box_left}" y1="{g.header_bottom}" x2="{g.box_right}" '
        f'y2="{g.header_bottom}" stroke="{STROKE}" stroke-width="{SW}"/>'
    )


def port_drawio_point(port: geom.Port) -> str:
    return geom.port_drawio_point(port)
