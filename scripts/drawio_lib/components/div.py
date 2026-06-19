import sys

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.div_component import DivComponent
from drawio_lib.components.simple_component import bind_module
from drawio_lib.components.simple_shapes import div_body, div_hex_port_cells

_mid = geom.BODY_Y + geom.BODY_H // 2
_pad = geom.side_pad_x()

_COMPONENT = DivComponent(
    title="div",
    tags="div divider clock drawclock",
    port_mode="both",
    body_svg=div_body,
    port_cells=div_hex_port_cells(mid_y=_mid, pad=_pad),
)

bind_module(sys.modules[__name__], _COMPONENT)
