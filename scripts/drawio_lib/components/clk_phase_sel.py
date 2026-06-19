import sys

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.fanout_component import FanoutComponent, bind_module
from drawio_lib.components.label_attrs import INSTANCE_NAME_GAP_LOOSE_PX
from drawio_lib.components.simple_shapes import (
    CLK_PHASE_SEL_BOX_HALF_H,
    CLK_PHASE_SEL_BOX_LEFT,
    clk_phase_sel_body,
    clk_phase_sel_output_cell_positions,
)

_pad = geom.side_pad_x()
_mid = geom.BODY_Y + geom.BODY_H // 2

_COMPONENT = FanoutComponent(
    title="clk_phase_sel",
    tags="clk_phase_sel phase clock drawclock",
    body_svg=clk_phase_sel_body,
    output_count=3,
    left_port_x=_pad + CLK_PHASE_SEL_BOX_LEFT,
    left_port_y=_mid,
    body_half_h=CLK_PHASE_SEL_BOX_HALF_H,
    label_output_indices=False,
    output_cells=clk_phase_sel_output_cell_positions(_pad, _mid),
    instance_name_gap_px=INSTANCE_NAME_GAP_LOOSE_PX,
)

bind_module(sys.modules[__name__], _COMPONENT)
