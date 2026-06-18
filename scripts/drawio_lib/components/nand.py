import sys

from drawio_lib.components.logic_gate_component import LogicGateComponent, bind_module
from drawio_lib.components.simple_shapes import nand_body

_COMPONENT = LogicGateComponent(
    title="nand",
    tags="nand logic gate clock drawclock",
    body_svg=nand_body,
    with_bubble=True,
)

bind_module(sys.modules[__name__], _COMPONENT)
