from __future__ import annotations

import sys
from collections.abc import Callable

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.simple_component import SimpleComponent, bind_module
from drawio_lib.components.simple_shapes import CELL_TRI_LEFT_X, CELL_TRI_TIP_X


def register_colored_cell(
    module: object,
    *,
    title: str,
    fill: str,
    tags: str,
    body_svg: Callable[[geom.SimpleGeometry], str],
) -> None:
    mid = geom.BODY_Y + geom.BODY_H // 2
    pad = geom.side_pad_x()
    component = SimpleComponent(
        title=title,
        tags=tags,
        port_mode="both",
        body_svg=body_svg,
        port_cells=(
            (pad + CELL_TRI_LEFT_X, mid),
            (pad + CELL_TRI_TIP_X, mid),
        ),
    )
    bind_module(module, component)
