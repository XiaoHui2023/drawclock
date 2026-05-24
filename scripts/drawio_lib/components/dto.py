import sys

from drawio_lib.components.dto_component import DtoComponent
from drawio_lib.components.simple_component import bind_module
from drawio_lib.components.simple_shapes import dto_body

_COMPONENT = DtoComponent(
    title="dto",
    tags="dto duty clock drawclock",
    port_mode="both",
    body_svg=dto_body,
)

bind_module(sys.modules[__name__], _COMPONENT)
