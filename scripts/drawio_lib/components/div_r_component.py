from __future__ import annotations

from dataclasses import dataclass

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.label_attrs import ATTR_NAME, LABEL_FONT_PX
from drawio_lib.components.simple_component import STROKE, SimpleComponent
from drawio_lib.components.simple_shapes import (
    DIV_HEX_R,
    DIV_SYMBOL_DOT_OFFSET,
    div_hex_half_width_at_y,
    div_ratio_body,
)
from drawio_lib.xml_io import xml_attr

ATTR_RATIO = "ratio"
DEFAULT_RATIO = "2"
# Small enough for 3 digits to fit where the bottom dot normally sits.
DIV_RATIO_FONT_PX = 7
DIV_R_DENOMINATOR_Y_OFFSET = DIV_SYMBOL_DOT_OFFSET
TEXT_DIGIT_WIDTH_FACTOR = 0.56
TEXT_HEIGHT_FACTOR = 0.9
TEXT_HEX_CLEARANCE_PX = 0.4


def div_r_ratio_font_px(digit_count: int) -> int:
    """Font size for ratio overlay; smaller when more digits (used at bake time)."""
    if digit_count <= 3:
        return 7
    if digit_count <= 4:
        return 6
    return 6


def div_ratio_font_px(digit_count: int) -> int:
    return div_r_ratio_font_px(digit_count)


@dataclass
class DivRComponent(SimpleComponent):
    """Hexagon divide-by-ratio; numerator and ratio render as fixed-size HTML overlays."""

    @property
    def edit_data_attr_prefix(self) -> tuple[str, ...]:
        return (ATTR_RATIO, ATTR_NAME, "label")

    @property
    def required_object_attrs(self) -> tuple[str, ...]:
        return (ATTR_RATIO, ATTR_NAME)

    def _center_labels(self) -> tuple[tuple[float, float, str, int], ...]:
        cx = self.w / 2
        mid = self._g.body_mid_y
        return (
            (cx, mid + DIV_R_DENOMINATOR_Y_OFFSET, f"%{ATTR_RATIO}%", DIV_RATIO_FONT_PX),
        )

    def label_html(self) -> str:
        return self._label_html_with_overlay(div_ratio_body(self._g), self._center_labels())

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
        body = div_ratio_body(self._g)
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
        ratio_y = mid + DIV_R_DENOMINATOR_Y_OFFSET
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">
{body}
  <text x="{cx}" y="{ratio_y}" font-size="{DIV_RATIO_FONT_PX}" fill="{STROKE}" text-anchor="middle" dominant-baseline="middle">{DEFAULT_RATIO}</text>
{stubs}{name_line}
</svg>
"""

    def verify_geometry(self) -> None:
        html = self.label_html()
        if f">%{ATTR_RATIO}%</span>" not in html:
            raise ValueError("div_r center label must render ratio as non-scaling HTML overlay")
        if ">1</span>" in html or ">1</text>" in html:
            raise ValueError("div_r must use a top dot, not a numerator")
        if "stroke-linecap=\"round\"" not in html or "<circle " not in html:
            raise ValueError("div_r body must keep centered divider bar and top dot")
        if not fits_centered_text_in_div_hex(
            text="888",
            font_px=div_r_ratio_font_px(3),
            text_center_y=self._center_labels()[0][1],
            hex_center_y=self._g.body_mid_y,
        ):
            raise ValueError("div_r ratio text must fit 3 digits inside the hexagon")
        super().verify_geometry()


def estimated_text_half_width(text: str, font_px: int) -> float:
    return len(text) * font_px * TEXT_DIGIT_WIDTH_FACTOR / 2


def estimated_text_half_height(font_px: int) -> float:
    return font_px * TEXT_HEIGHT_FACTOR / 2


def fits_centered_text_in_div_hex(
    *,
    text: str,
    font_px: int,
    text_center_y: float,
    hex_center_y: float,
) -> bool:
    half_w = estimated_text_half_width(text, font_px) + TEXT_HEX_CLEARANCE_PX
    bottom_y = text_center_y + estimated_text_half_height(font_px)
    available = div_hex_half_width_at_y(center_y=hex_center_y, y=bottom_y)
    return half_w <= available
