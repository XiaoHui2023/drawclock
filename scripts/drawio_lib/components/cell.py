import sys

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.simple_component import SimpleComponent, bind_module
from drawio_lib.components.simple_shapes import CELL_TRI_LEFT_X, CELL_TRI_TIP_X, cell_body

_COMPONENT = SimpleComponent(
    title="cell",
    tags="cell clock drawclock",
    port_mode="both",
    body_svg=cell_body,
    port_cells=(
        (geom.side_pad_x() + CELL_TRI_LEFT_X, geom.BODY_Y + geom.BODY_H // 2),
        (geom.side_pad_x() + CELL_TRI_TIP_X, geom.BODY_Y + geom.BODY_H // 2),
    ),
)

bind_module(sys.modules[__name__], _COMPONENT)
