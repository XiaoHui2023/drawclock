from __future__ import annotations

from dataclasses import dataclass

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.label_attrs import ATTR_NAME
from drawio_lib.components.simple_component import STROKE, SimpleComponent, xml_attr
from drawio_lib.components.simple_shapes import pll_body, pll_label_cx

ATTR_PLL_KIND = "pll_kind"
DEFAULT_PLL_KIND = "SC"
PLL_CENTER_FONT_PX = 9


@dataclass
class PllComponent(SimpleComponent):
    """PLL tag shape; center label is HTML so it does not stretch with the shape."""

    @property
    def edit_data_attr_prefix(self) -> tuple[str, ...]:
        return (ATTR_PLL_KIND, ATTR_NAME, "label")

    @property
    def required_object_attrs(self) -> tuple[str, ...]:
        return (ATTR_PLL_KIND, ATTR_NAME)

    def _center_labels(self) -> tuple[tuple[float, float, str], ...]:
        mid = self._g.body_mid_y
        return ((pll_label_cx(self._g), mid, f"%{ATTR_PLL_KIND}%"),)

    def label_html(self) -> str:
        return self._label_html_with_overlay(pll_body(self._g), self._center_labels())

    def cell_fragment(
        self,
        cell_id: str,
        instance_name: str | None = None,
        *,
        pll_kind: str = DEFAULT_PLL_KIND,
        x: int | None = None,
        y: int | None = None,
    ) -> str:
        style = self.cell_style()
        name = xml_attr(self._resolve_instance_name(instance_name))
        kind_val = xml_attr(pll_kind)
        label = xml_attr(self.label_html())
        attrs = [
            f'{ATTR_PLL_KIND}="{kind_val}"',
            f'{ATTR_NAME}="{name}"',
            f'label="{label}"',
            'placeholders="1"',
            f'id="{cell_id}"',
        ]
        if x is None and y is None:
            geom_xml = f'<mxGeometry width="{self.w}" height="{self.h}" as="geometry"/>'
        else:
            geom_xml = (
                f'<mxGeometry x="{x or 0}" y="{y or 0}" width="{self.w}" '
                f'height="{self.h}" as="geometry"/>'
            )
        return (
            f"<object {' '.join(attrs)}>"
            f'<mxCell style="{style}" vertex="1" parent="1">'
            f"{geom_xml}"
            "</mxCell>"
            "</object>"
        )

    def preview_svg(self) -> str:
        body = pll_body(self._g)
        mid = self._g.body_mid_y
        port = self._ports()[0]
        a = port.anchor
        name_y = self._instance_name_top_y() + geom.NAME_H // 2
        label_x = pll_label_cx(self._g)
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">
{body}
  <text x="{label_x}" y="{mid}" font-size="{PLL_CENTER_FONT_PX}" fill="{STROKE}" text-anchor="middle" dominant-baseline="middle">{DEFAULT_PLL_KIND}</text>
  <line x1="{port.stub_x1}" y1="{port.stub_y1}" x2="{port.stub_x2}" y2="{port.stub_y2}" stroke="#c00" stroke-width="1"/>
  <circle cx="{a.cell_x}" cy="{a.cell_y}" r="2.5" fill="#c00"/>
  <text x="{self.w // 2}" y="{name_y}" font-size="11" fill="{STROKE}" text-anchor="middle" dominant-baseline="middle">{self.title}</text>
</svg>
"""

    def verify_geometry(self) -> None:
        html = self.label_html()
        if f">%{ATTR_PLL_KIND}%</span>" not in html:
            raise ValueError("pll label must render pll_kind as non-scaling HTML overlay")
        super().verify_geometry()
