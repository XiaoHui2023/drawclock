import sys
from dataclasses import dataclass

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.label_attrs import INSTANCE_NAME_PULL_COMPACT_PX, LABEL_FONT_PX
from drawio_lib.components.simple_component import STROKE, SimpleComponent, bind_module
from drawio_lib.components.simple_shapes import div2_body, div_hex_port_cells

_mid = geom.BODY_Y + geom.BODY_H // 2
_pad = geom.side_pad_x()


@dataclass
class Div2Component(SimpleComponent):
    """Divide-by-2 hexagon; denominator digit does not stretch with the shape."""

    def _center_label_overlay(self) -> tuple[tuple[float, float, str, int], ...]:
        cx = self.w / 2
        cy = self._g.body_mid_y
        return ((cx, cy, "÷2", LABEL_FONT_PX),)

    def label_html(self) -> str:
        return self._label_html_with_overlay(div2_body(self._g), self._center_label_overlay())

    def preview_svg(self) -> str:
        body = div2_body(self._g)
        cx = self.w / 2
        cy = self._g.body_mid_y
        stub_lines = []
        for port, color in zip(self._ports(), ("#c00", "#090")):
            stub_lines.append(
                f'  <line x1="{port.stub_x1}" y1="{port.stub_y1}" '
                f'x2="{port.stub_x2}" y2="{port.stub_y2}" stroke="{color}" '
                f'stroke-width="1"/>'
            )
            a = port.anchor
            stub_lines.append(
                f'  <circle cx="{a.cell_x}" cy="{a.cell_y}" r="2.5" fill="{color}"/>'
            )
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
  <text x="{cx}" y="{cy}" font-size="{LABEL_FONT_PX}" fill="{STROKE}" text-anchor="middle" dominant-baseline="middle">÷2</text>
{stubs}{name_line}
</svg>
"""

    def verify_geometry(self) -> None:
        html = self.label_html()
        if ">÷2</span>" not in html:
            raise ValueError("div2 center label must use non-scaling HTML overlay")
        if "÷2</text>" in html:
            raise ValueError("div2 center label must not be SVG text inside the stretchable body")
        super().verify_geometry()


_COMPONENT = Div2Component(
    title="div2",
    tags="div2 divider clock drawclock",
    port_mode="both",
    body_svg=div2_body,
    port_cells=div_hex_port_cells(mid_y=_mid, pad=_pad),
    instance_name_pull_px=INSTANCE_NAME_PULL_COMPACT_PX,
)

bind_module(sys.modules[__name__], _COMPONENT)
