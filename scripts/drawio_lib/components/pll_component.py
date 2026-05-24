from __future__ import annotations

from dataclasses import dataclass

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.simple_component import STROKE, SimpleComponent
from drawio_lib.components.simple_shapes import pll_body, pll_label_cx

PLL_CENTER_FONT_PX = 9


@dataclass
class PllComponent(SimpleComponent):
    """PLL tag shape; center label is HTML so it does not stretch with the shape."""

    def _center_labels(self) -> tuple[tuple[float, float, str], ...]:
        mid = self._g.body_mid_y
        return ((pll_label_cx(self._g), mid, "PLL"),)

    def label_html(self) -> str:
        return self._label_html_with_overlay(pll_body(self._g), self._center_labels())

    def preview_svg(self) -> str:
        body = pll_body(self._g)
        mid = self._g.body_mid_y
        port = self._ports()[0]
        a = port.anchor
        name_y = self._instance_name_top_y() + geom.NAME_H // 2
        label_x = pll_label_cx(self._g)
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">
{body}
  <text x="{label_x}" y="{mid}" font-size="{PLL_CENTER_FONT_PX}" fill="{STROKE}" text-anchor="middle" dominant-baseline="middle">PLL</text>
  <line x1="{port.stub_x1}" y1="{port.stub_y1}" x2="{port.stub_x2}" y2="{port.stub_y2}" stroke="#c00" stroke-width="1"/>
  <circle cx="{a.cell_x}" cy="{a.cell_y}" r="2.5" fill="#c00"/>
  <text x="{self.w // 2}" y="{name_y}" font-size="11" fill="{STROKE}" text-anchor="middle" dominant-baseline="middle">{self.title}</text>
</svg>
"""

    def verify_geometry(self) -> None:
        html = self.label_html()
        if ">PLL</span>" not in html:
            raise ValueError("pll label must render PLL as non-scaling HTML overlay")
        super().verify_geometry()
