import sys

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.dto_n_component import DtoNComponent
from drawio_lib.components.label_attrs import INSTANCE_NAME_PULL_COMPACT_PX
from drawio_lib.components.simple_component import bind_module
from drawio_lib.components.simple_shapes import dto_chip_port_cells, dto_n_body

_mid = geom.BODY_Y + geom.BODY_H // 2
_pad = geom.side_pad_x()

_COMPONENT = DtoNComponent(
    title="dto_n",
    tags="dto_n duty clock drawclock",
    port_mode="both",
    body_svg=dto_n_body,
    port_cells=dto_chip_port_cells(mid_y=_mid, pad=_pad),
    instance_name_pull_px=INSTANCE_NAME_PULL_COMPACT_PX,
)

bind_module(sys.modules[__name__], _COMPONENT)
