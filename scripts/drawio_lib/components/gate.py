import sys

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.simple_component import SimpleComponent, bind_module
from drawio_lib.components.simple_shapes import GATE_BUBBLE_X, GATE_LEFT_X, gate_body

_mid = geom.BODY_Y + geom.BODY_H // 2
_pad = geom.side_pad_x()

_COMPONENT = SimpleComponent(
    title="gate",
    tags="gate clock gating drawclock",
    port_mode="both",
    body_svg=gate_body,
    port_cells=((_pad + GATE_LEFT_X, _mid), (_pad + GATE_BUBBLE_X, _mid)),
)

bind_module(sys.modules[__name__], _COMPONENT)
