from __future__ import annotations

import sys
from collections.abc import Callable

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.label_attrs import INSTANCE_NAME_PULL_COMPACT_PX
from drawio_lib.components.cell_component import CellComponent
from drawio_lib.components.simple_component import bind_module
from drawio_lib.components.simple_shapes import CELL_TRI_LEFT_X, CELL_TRI_TIP_X


def register_colored_cell(
    module: object,
    *,
    title: str,
    fill: str,
    tags: str,
    body_svg: Callable[[geom.SimpleGeometry], str],
    port_mode: geom.PortMode = "both",
    instance_name_pull_px: int = INSTANCE_NAME_PULL_COMPACT_PX,
) -> None:
    mid = geom.BODY_Y + geom.BODY_H // 2
    pad = geom.side_pad_x(geom.COLORED_CELL_W)
    left_port = (pad + CELL_TRI_LEFT_X, mid)
    right_port = (pad + CELL_TRI_TIP_X, mid)
    if port_mode == "both":
        port_cells: tuple[tuple[int, int], ...] | None = (left_port, right_port)
    elif port_mode == "left":
        port_cells = (left_port,)
    elif port_mode == "right":
        port_cells = (right_port,)
    else:
        port_cells = None
    component = CellComponent(
        title=title,
        tags=tags,
        port_mode=port_mode,
        body_svg=body_svg,
        cell_w=geom.COLORED_CELL_W,
        port_cells=port_cells,
        instance_name_pull_px=instance_name_pull_px,
    )
    bind_module(module, component)
