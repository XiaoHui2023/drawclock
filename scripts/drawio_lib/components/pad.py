import sys
from dataclasses import dataclass

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.label_attrs import INSTANCE_NAME_PULL_COMPACT_PX, LABEL_FONT_PX
from drawio_lib.components.simple_component import (
    STROKE,
    SimpleComponent,
    bind_module,
)
from drawio_lib.components.simple_shapes import PAD_RIGHT_X, pad_body

_mid = geom.BODY_Y + geom.BODY_H // 2
_pad = geom.side_pad_x()
OUTPUT_LABEL_OFFSET_X = 6


@dataclass
class PadComponent(SimpleComponent):
    def _output_label_overlay(self) -> tuple[tuple[float, float, str], ...]:
        assert self._g.right is not None
        port = self._g.right
        return (
            (port.anchor.cell_x - OUTPUT_LABEL_OFFSET_X, port.anchor.cell_y, "C"),
        )

    def label_html(self) -> str:
        return self._label_html_with_overlay(
            self.body_svg(self._g),
            self._output_label_overlay(),
        )

    def preview_svg(self) -> str:
        body = self.body_svg(self._g)
        port = self._g.right
        assert port is not None
        stub_lines = [
            f'  <line x1="{port.stub_x1}" y1="{port.stub_y1}" '
            f'x2="{port.stub_x2}" y2="{port.stub_y2}" stroke="#c00" stroke-width="1"/>',
            f'  <circle cx="{port.anchor.cell_x}" cy="{port.anchor.cell_y}" '
            f'r="2.5" fill="#c00"/>',
            f'  <text x="{port.anchor.cell_x - OUTPUT_LABEL_OFFSET_X}" '
            f'y="{port.anchor.cell_y}" font-size="{LABEL_FONT_PX}" fill="{STROKE}" '
            f'text-anchor="middle" dominant-baseline="middle">C</text>',
        ]
        stubs = "\n".join(stub_lines)
        name_line = ""
        if self.show_instance_name:
            name_y = (
                self._instance_name_top_y()
                + self.instance_name_gap_px
                + geom.NAME_H // 2
            )
            name_line = (
                f'\n  <text x="{self.w // 2}" y="{name_y}" font-size="{LABEL_FONT_PX}" '
                f'fill="{STROKE}" text-anchor="middle" dominant-baseline="middle">'
                f"{self.title}</text>"
            )
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">
{body}
{stubs}{name_line}
</svg>
"""


_COMPONENT = PadComponent(
    title="pad",
    tags="pad io terminal output drawclock",
    port_mode="right",
    body_svg=pad_body,
    port_cells=((_pad + PAD_RIGHT_X, _mid),),
    instance_name_pull_px=INSTANCE_NAME_PULL_COMPACT_PX,
)

bind_module(sys.modules[__name__], _COMPONENT)
