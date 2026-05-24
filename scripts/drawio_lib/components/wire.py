import sys

from drawio_lib.components.simple_component import bind_module
from drawio_lib.components.simple_shapes import wire_body
from drawio_lib.components.wire_component import WireComponent

_COMPONENT = WireComponent(
    title="wire",
    tags="wire connect line drawclock",
    port_mode="wire",
    body_svg=wire_body,
    show_instance_name=True,
)

bind_module(sys.modules[__name__], _COMPONENT)
