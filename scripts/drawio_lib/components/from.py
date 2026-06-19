import sys

from drawio_lib.components.from_component import FromComponent
from drawio_lib.components.simple_component import bind_module
from drawio_lib.components.simple_shapes import wire_body

_COMPONENT = FromComponent(
    title="from",
    tags="from connect line drawclock",
    port_mode="from",
    body_svg=wire_body,
    show_instance_name=True,
)

bind_module(sys.modules[__name__], _COMPONENT)
