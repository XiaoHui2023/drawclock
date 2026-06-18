import sys

from drawio_lib.components.logic_gate_component import LogicGateComponent, bind_module
from drawio_lib.components.simple_shapes import and_body

_COMPONENT = LogicGateComponent(
    title="and",
    tags="and logic gate clock drawclock",
    body_svg=and_body,
)

bind_module(sys.modules[__name__], _COMPONENT)
