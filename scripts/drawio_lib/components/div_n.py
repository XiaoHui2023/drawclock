import sys

from drawio_lib.components.div_n_component import DivNComponent
from drawio_lib.components.simple_component import bind_module
from drawio_lib.components.simple_shapes import div_body

_COMPONENT = DivNComponent(
    title="div_n",
    tags="div_n divider clock drawclock",
    port_mode="both",
    body_svg=div_body,
)

bind_module(sys.modules[__name__], _COMPONENT)
