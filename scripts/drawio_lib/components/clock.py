import sys

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.clock_component import CLOCK_CELL_W, ClockComponent
from drawio_lib.components.simple_component import bind_module
from drawio_lib.components.simple_shapes import (
    CLOCK_BODY_MARGIN_X,
    CLOCK_CELL_W,
    CLOCK_LEFT_PAD,
    clock_body,
)

_BODY_MID_Y = geom.BODY_Y + geom.BODY_H // 2
_LEFT_PORT_X = CLOCK_LEFT_PAD + CLOCK_BODY_MARGIN_X

_COMPONENT = ClockComponent(
    title="clock",
    tags="clock terminal sink drawclock",
    port_mode="left",
    body_svg=clock_body,
    port_cells=((_LEFT_PORT_X, _BODY_MID_Y),),
    cell_w=CLOCK_CELL_W,
)

bind_module(sys.modules[__name__], _COMPONENT)
