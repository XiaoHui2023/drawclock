import sys

from drawio_lib.components.logic_gate_component import LogicGateComponent, bind_module
from drawio_lib.components.simple_shapes import xor_body

_COMPONENT = LogicGateComponent(
    title="xor",
    tags="xor logic gate clock drawclock",
    body_svg=xor_body,
)

bind_module(sys.modules[__name__], _COMPONENT)
