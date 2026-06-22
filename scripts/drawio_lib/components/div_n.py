import sys

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.label_attrs import INSTANCE_NAME_PULL_COMPACT_PX
from drawio_lib.components.simple_component import SimpleComponent, bind_module
from drawio_lib.components.simple_shapes import div_hex_port_cells, div_n_body

_mid = geom.BODY_Y + geom.BODY_H // 2
_pad = geom.side_pad_x()

_COMPONENT = SimpleComponent(
    title="div_n",
    tags="div_n divider clock drawclock",
    port_mode="both",
    body_svg=div_n_body,
    port_cells=div_hex_port_cells(mid_y=_mid, pad=_pad),
    instance_name_pull_px=INSTANCE_NAME_PULL_COMPACT_PX,
)

bind_module(sys.modules[__name__], _COMPONENT)
