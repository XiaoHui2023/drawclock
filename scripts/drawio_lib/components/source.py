import sys

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.label_attrs import INSTANCE_NAME_PULL_COMPACT_PX
from drawio_lib.components.simple_component import SimpleComponent, bind_module
from drawio_lib.components.simple_shapes import SOURCE_PORT_X, source_body

_mid = geom.BODY_Y + geom.BODY_H // 2
_pad = geom.side_pad_x()

_COMPONENT = SimpleComponent(
    title="source",
    tags="source clock oscillator xtal drawclock",
    port_mode="right",
    body_svg=source_body,
    body_margin_x=4,
    port_cells=((_pad + SOURCE_PORT_X, _mid),),
    instance_name_pull_px=INSTANCE_NAME_PULL_COMPACT_PX,
)

bind_module(sys.modules[__name__], _COMPONENT)
