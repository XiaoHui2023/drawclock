import sys

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.pll_component import PllComponent
from drawio_lib.components.simple_component import bind_module
from drawio_lib.components.simple_shapes import PLL_TIP_X, pll_body

_mid = geom.BODY_Y + geom.BODY_H // 2
_pad = geom.side_pad_x()

_COMPONENT = PllComponent(
    title="pll",
    tags="pll clock source drawclock",
    port_mode="right",
    body_svg=pll_body,
    body_margin_x=4,
    port_cells=((_pad + PLL_TIP_X, _mid),),
)

bind_module(sys.modules[__name__], _COMPONENT)
