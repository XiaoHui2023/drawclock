import sys

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.fanout_component import FanoutComponent, bind_module
from drawio_lib.components.simple_shapes import (
    INV_MUX_OUT_SPREAD,
    INV_PORT_LEFT_X,
    inv_mux_body,
    inv_mux_output_cell_positions,
)

_pad = geom.side_pad_x()
_mid = geom.BODY_Y + geom.BODY_H // 2

_COMPONENT = FanoutComponent(
    title="inv_mux",
    tags="inv_mux mux inverter clock drawclock",
    body_svg=inv_mux_body,
    output_count=2,
    left_port_x=_pad + INV_PORT_LEFT_X,
    left_port_y=_mid,
    body_half_h=16,
    label_output_indices=False,
    output_cells=inv_mux_output_cell_positions(_pad, _mid),
)

bind_module(sys.modules[__name__], _COMPONENT)
