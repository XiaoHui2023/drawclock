import sys

from drawio_lib.components.from_component import FromComponent
from drawio_lib.components.label_attrs import INSTANCE_NAME_GAP_LOOSE_PX
from drawio_lib.components.simple_component import bind_module
from drawio_lib.components.simple_shapes import wire_body

_COMPONENT = FromComponent(
    title="from",
    tags="from connect line drawclock",
    port_mode="from",
    body_svg=wire_body,
    show_instance_name=True,
    instance_name_gap_px=INSTANCE_NAME_GAP_LOOSE_PX,
)

bind_module(sys.modules[__name__], _COMPONENT)
