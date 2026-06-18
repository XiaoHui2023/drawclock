import sys

from drawio_lib.components.logic_gate_component import LogicGateComponent, bind_module
from drawio_lib.components.simple_shapes import nor_body

_COMPONENT = LogicGateComponent(
    title="nor",
    tags="nor logic gate clock drawclock",
    body_svg=nor_body,
    with_bubble=True,
)

bind_module(sys.modules[__name__], _COMPONENT)
