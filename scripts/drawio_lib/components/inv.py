import sys

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.label_attrs import INSTANCE_NAME_PULL_COMPACT_PX
from drawio_lib.components.inv_component import InvComponent
from drawio_lib.components.simple_component import bind_module
from drawio_lib.components.simple_shapes import INV_PORT_LEFT_X, INV_RIGHT_PORT_X, inv_body

_mid = geom.BODY_Y + geom.BODY_H // 2
_pad = geom.side_pad_x()

_COMPONENT = InvComponent(
    title="inv",
    tags="inv inverter clock drawclock",
    port_mode="both",
    body_svg=inv_body,
    port_cells=((_pad + INV_PORT_LEFT_X, _mid), (_pad + INV_RIGHT_PORT_X, _mid)),
    instance_name_pull_px=INSTANCE_NAME_PULL_COMPACT_PX,
)

bind_module(sys.modules[__name__], _COMPONENT)
