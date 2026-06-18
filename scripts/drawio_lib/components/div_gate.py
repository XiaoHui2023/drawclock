import sys

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.fanout_component import FanoutComponent, bind_module
from drawio_lib.components.simple_shapes import (
    DIV_GATE_BODY_HALF_H,
    DIV_SYMBOL_FONT_PX,
    GATE_LEFT_X,
    div_gate_body,
    div_gate_output_cell_positions,
    div_gate_symbol_cell,
)

_pad = geom.side_pad_x()
_mid = geom.BODY_Y + geom.BODY_H // 2
_symbol_cx, _symbol_cy = div_gate_symbol_cell(_pad, _mid)

_COMPONENT = FanoutComponent(
    title="div_gate",
    tags="div_gate divider gate clock drawclock",
    body_svg=div_gate_body,
    output_count=3,
    left_port_x=_pad + GATE_LEFT_X,
    left_port_y=_mid,
    body_half_h=DIV_GATE_BODY_HALF_H,
    label_output_indices=False,
    output_cells=div_gate_output_cell_positions(_pad, _mid),
    center_labels=((_symbol_cx, _symbol_cy, "÷", DIV_SYMBOL_FONT_PX),),
)


def verify_geometry() -> None:
    _COMPONENT.verify_geometry()
    html = _COMPONENT.label_html()
    if ">÷</span>" not in html:
        raise ValueError("div_gate ÷ must use non-scaling HTML overlay")
    if "÷</text>" in html:
        raise ValueError("div_gate ÷ must not be SVG text inside the stretchable body")


bind_module(sys.modules[__name__], _COMPONENT)
setattr(sys.modules[__name__], "verify_geometry", verify_geometry)
