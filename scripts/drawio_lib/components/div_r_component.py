from __future__ import annotations

from dataclasses import dataclass

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.label_attrs import ATTR_NAME, LABEL_FONT_PX
from drawio_lib.components.simple_component import STROKE, SimpleComponent
from drawio_lib.components.simple_shapes import DIV_HEX_FLAT_BOTTOM_Y_OFFSET, div_r_body
from drawio_lib.xml_io import xml_attr

ATTR_RATIO = "ratio"
DEFAULT_RATIO = "2"
# Hex inner width ~21px; 8px fits three digits with margin in the library template.
DIV_RATIO_FONT_PX = 8
# ÷ and ratio center-to-center spacing in the hex body.
_DIV_R_LABEL_GAP = 9
# Helvetica digits sit above the em-box bottom; nudge down to meet the hex flat edge.
_DIV_R_DIGIT_BASELINE_NUDGE = 2


def div_r_ratio_font_px(digit_count: int) -> int:
    """Font size for ratio overlay; smaller when more digits (used at bake time)."""
    if digit_count <= 2:
        return 9
    if digit_count <= 3:
        return DIV_RATIO_FONT_PX
    if digit_count <= 4:
        return 7
    return 6


@dataclass
class DivRComponent(SimpleComponent):
    """Hexagon divide-by-ratio; ÷ and ratio render as fixed-size HTML overlays."""

    @property
    def edit_data_attr_prefix(self) -> tuple[str, ...]:
        return (ATTR_RATIO, ATTR_NAME, "label")

    @property
    def required_object_attrs(self) -> tuple[str, ...]:
        return (ATTR_RATIO, ATTR_NAME)

    def _center_labels(self) -> tuple[tuple[float, float, str, int], ...]:
        cx = self.w / 2
        mid = self._g.body_mid_y
        ratio_y = (
            mid
            + DIV_HEX_FLAT_BOTTOM_Y_OFFSET
            - DIV_RATIO_FONT_PX / 2
            + _DIV_R_DIGIT_BASELINE_NUDGE
        )
        symbol_y = ratio_y - _DIV_R_LABEL_GAP
        return (
            (cx, symbol_y, "÷", LABEL_FONT_PX),
            (cx, ratio_y, f"%{ATTR_RATIO}%", DIV_RATIO_FONT_PX),
        )

    def label_html(self) -> str:
        return self._label_html_with_overlay(div_r_body(self._g), self._center_labels())

    def cell_fragment(
        self,
        cell_id: str,
        instance_name: str | None = None,
        *,
        ratio: str = DEFAULT_RATIO,
        x: int | None = None,
        y: int | None = None,
    ) -> str:
        style = self.cell_style()
        name = xml_attr(self._resolve_instance_name(instance_name))
        ratio_val = xml_attr(ratio)
        label = xml_attr(self.label_html())
        attrs = [
            f'{ATTR_RATIO}="{ratio_val}"',
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
        body = div_r_body(self._g)
        cx = self.w / 2
        mid = self._g.body_mid_y
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
        ratio_y = (
            mid
            + DIV_HEX_FLAT_BOTTOM_Y_OFFSET
            - DIV_RATIO_FONT_PX / 2
            + _DIV_R_DIGIT_BASELINE_NUDGE
        )
        symbol_y = ratio_y - _DIV_R_LABEL_GAP
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">
{body}
  <text x="{cx}" y="{symbol_y}" font-size="{LABEL_FONT_PX}" fill="{STROKE}" text-anchor="middle" dominant-baseline="middle">÷</text>
  <text x="{cx}" y="{ratio_y}" font-size="{DIV_RATIO_FONT_PX}" fill="{STROKE}" text-anchor="middle" dominant-baseline="middle">{DEFAULT_RATIO}</text>
{stubs}{name_line}
</svg>
"""

    def verify_geometry(self) -> None:
        html = self.label_html()
        if ">÷</span>" not in html:
            raise ValueError("div_r center label must render ÷ as non-scaling HTML overlay")
        if f">%{ATTR_RATIO}%</span>" not in html:
            raise ValueError("div_r center label must render ratio as non-scaling HTML overlay")
        if "÷</text>" in html:
            raise ValueError("div_r center label must not be SVG text inside the stretchable body")
        super().verify_geometry()
