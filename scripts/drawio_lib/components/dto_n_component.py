from __future__ import annotations

from dataclasses import dataclass

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.dto_component import DtoComponent
from drawio_lib.components.simple_shapes import (
    DTO_CENTER_FONT_PX,
    DTO_LABEL_Y_OFFSET,
    dto_n_body,
)


@dataclass
class DtoNComponent(DtoComponent):
    """Programmable DTO; center label shows DTO_N with mirrored waveform."""

    def _center_labels(self) -> tuple[tuple[float, float, str, int], ...]:
        cx = geom.W / 2
        cy = self._g.body_mid_y + DTO_LABEL_Y_OFFSET
        return ((cx, cy, "DTO_N", DTO_CENTER_FONT_PX),)

    def label_html(self) -> str:
        return self._label_html_with_overlay(dto_n_body(self._g), self._center_labels())

    def preview_svg(self) -> str:
        from drawio_lib.components.simple_component import STROKE

        body = dto_n_body(self._g)
        cx = geom.W / 2
        cy = self._g.body_mid_y + DTO_LABEL_Y_OFFSET
        name_y = self._instance_name_top_y() + geom.NAME_H // 2
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
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">
{body}
  <text x="{cx}" y="{cy}" font-size="{DTO_CENTER_FONT_PX}" fill="{STROKE}" text-anchor="middle" dominant-baseline="middle">DTO_N</text>
{stubs}
  <text x="{self.w // 2}" y="{name_y}" font-size="11" fill="{STROKE}" text-anchor="middle" dominant-baseline="middle">{self.title}</text>
</svg>
"""

    def verify_geometry(self) -> None:
        html = self.label_html()
        if ">DTO_N</span>" not in html:
            raise ValueError("dto_n label must show DTO_N on one line")
        if f"font-size:{DTO_CENTER_FONT_PX}px" not in html:
            raise ValueError("dto_n center label must use fixed smaller font")
        from drawio_lib.components.simple_component import SimpleComponent

        SimpleComponent.verify_geometry(self)
