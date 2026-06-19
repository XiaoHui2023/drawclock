import sys

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.clock_component import CLOCK_CELL_W, ClockComponent
from drawio_lib.components.label_attrs import INSTANCE_NAME_GAP_LOOSE_PX
from drawio_lib.components.simple_component import bind_module
from drawio_lib.components.simple_shapes import (
    CLOCK_CELL_W,
    CLOCK_NAME_SIDE_PAD,
    CLOCK_WAVE_AMP,
    clock_body,
)

_BODY_MID_Y = geom.BODY_Y + geom.BODY_H // 2
_BODY_LO_Y = _BODY_MID_Y + CLOCK_WAVE_AMP

_COMPONENT = ClockComponent(
    title="clock",
    tags="clock terminal sink drawclock",
    port_mode="left",
    body_svg=clock_body,
    port_cells=((CLOCK_NAME_SIDE_PAD, _BODY_LO_Y),),
    cell_w=CLOCK_CELL_W,
    instance_name_gap_px=INSTANCE_NAME_GAP_LOOSE_PX,
)

bind_module(sys.modules[__name__], _COMPONENT)
