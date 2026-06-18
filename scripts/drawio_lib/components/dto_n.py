import sys

from drawio_lib.components.dto_n_component import DtoNComponent
from drawio_lib.components.simple_component import bind_module
from drawio_lib.components.simple_shapes import dto_n_body

_COMPONENT = DtoNComponent(
    title="dto_n",
    tags="dto_n duty clock drawclock",
    port_mode="both",
    body_svg=dto_n_body,
)

bind_module(sys.modules[__name__], _COMPONENT)
