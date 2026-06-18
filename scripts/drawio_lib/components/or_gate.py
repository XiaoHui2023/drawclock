import sys

from drawio_lib.components.logic_gate_component import LogicGateComponent, bind_module
from drawio_lib.components.simple_shapes import or_body

_COMPONENT = LogicGateComponent(
    title="or",
    tags="or logic gate clock drawclock",
    body_svg=or_body,
)

bind_module(sys.modules[__name__], _COMPONENT)
