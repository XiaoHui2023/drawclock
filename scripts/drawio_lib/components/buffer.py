import sys

from drawio_lib.components.logic_gate_component import LogicGateComponent, bind_module
from drawio_lib.components.simple_shapes import buffer_body

_COMPONENT = LogicGateComponent(
    title="buffer",
    tags="buffer logic gate clock drawclock",
    body_svg=buffer_body,
    dual_input=False,
    buffer=True,
)

bind_module(sys.modules[__name__], _COMPONENT)
