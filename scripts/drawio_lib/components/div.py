import sys

from drawio_lib.components.div_component import DivComponent
from drawio_lib.components.simple_component import bind_module
from drawio_lib.components.simple_shapes import div_body

_COMPONENT = DivComponent(
    title="div",
    tags="div divider clock drawclock",
    port_mode="both",
    body_svg=div_body,
)

bind_module(sys.modules[__name__], _COMPONENT)
