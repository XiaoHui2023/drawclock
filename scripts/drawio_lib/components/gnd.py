import sys

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.label_attrs import INSTANCE_NAME_PULL_COMPACT_PX
from drawio_lib.components.clock_source_component import ClockSourceComponent
from drawio_lib.components.simple_component import bind_module
from drawio_lib.components.simple_shapes import gnd_body, gnd_port_cell

_mid = geom.BODY_Y + geom.BODY_H // 2
_pad = geom.side_pad_x()

_COMPONENT = ClockSourceComponent(
    title="gnd",
    tags="gnd vss ground tie-low logic0 clock drawclock",
    port_mode="right",
    body_svg=gnd_body,
    body_margin_x=4,
    port_cells=gnd_port_cell(mid_y=_mid, pad=_pad),
    instance_name_pull_px=INSTANCE_NAME_PULL_COMPACT_PX,
)

bind_module(sys.modules[__name__], _COMPONENT)
