from __future__ import annotations

from dataclasses import dataclass

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.div_r_component import (
    DIV_RATIO_FONT_PX,
    TEXT_HEX_CLEARANCE_PX,
    estimated_text_half_height,
    estimated_text_half_width,
)
from drawio_lib.components.label_attrs import ATTR_NAME, LABEL_FONT_PX
from drawio_lib.components.label_html import name_block, shell_close, shell_open, stretch_body_layer
from drawio_lib.components.simple_component import STROKE, SimpleComponent
from drawio_lib.components.simple_shapes import div_hex_half_width_at_y, div_power_body
from drawio_lib.xml_io import xml_attr

ATTR_WIDTH = "div_width"
DEFAULT_WIDTH = "6"
_DIV_EXPONENT_PREFIX_FONT_PX = 5
DIV_POWER_VALUE_FONT_PX = 8
DIV_POWER_VALUE_DEFAULT_FONT_PX = 9
DIV_POWER_BAR_Y_OFFSET = -2
DIV_POWER_WIDTH_Y = 33.8
DIV_POWER_MIN_BAR_GAP_PX = 2.0


@dataclass
class DivComponent(SimpleComponent):
    """Hexagon divider; top dot/line and bottom 2^width render as HTML overlays."""

    @property
    def edit_data_attr_prefix(self) -> tuple[str, ...]:
        return (ATTR_WIDTH, ATTR_NAME, "label")

    @property
    def required_object_attrs(self) -> tuple[str, ...]:
        return (ATTR_WIDTH, ATTR_NAME)

    def _center_labels(self) -> tuple[tuple[float, float, str, int], ...]:
        cx = self.w / 2
        return (
            (cx, self._width_y(), f"2^%{ATTR_WIDTH}%", DIV_RATIO_FONT_PX),
        )

    def _width_y(self) -> float:
        return DIV_POWER_WIDTH_Y

    def _width_overlay_html(self) -> str:
        return (
            f'<span style="font-size:{_DIV_EXPONENT_PREFIX_FONT_PX}px;'
            f'color:#555555;vertical-align:baseline;">2^</span>'
            f'<span style="font-size:{DIV_POWER_VALUE_DEFAULT_FONT_PX}px;'
            f'color:{STROKE};vertical-align:baseline;">%{ATTR_WIDTH}%</span>'
        )

    def label_html(self) -> str:
        parts = [
            shell_open(self.w, self.h),
            stretch_body_layer(
                div_power_body(self._g, bar_y_offset=DIV_POWER_BAR_Y_OFFSET),
                view_w=self.w,
                view_h=self.graphic_h,
                overlays=((self.w / 2, self._width_y(), self._width_overlay_html(), DIV_RATIO_FONT_PX),),
            ),
        ]
        if self.show_instance_name:
            parts.append(
                name_block(
                    self._instance_name_top_y(),
                    design_cell_h=self.h,
                    gap_px=self.instance_name_gap_px,
                )
            )
        parts.append(shell_close())
        return "".join(parts)

    def cell_fragment(
        self,
        cell_id: str,
        instance_name: str | None = None,
        *,
        div_width: str | None = None,
        width: str | None = None,
        x: int | None = None,
        y: int | None = None,
    ) -> str:
        style = self.cell_style()
        name = xml_attr(self._resolve_instance_name(instance_name))
        width_val = xml_attr(div_width if div_width is not None else width or DEFAULT_WIDTH)
        label = xml_attr(self.label_html())
        attrs = [
            f'{ATTR_WIDTH}="{width_val}"',
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
        body = div_power_body(self._g, bar_y_offset=DIV_POWER_BAR_Y_OFFSET)
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
        width_y = self._width_y()
        width_font = DIV_POWER_VALUE_DEFAULT_FONT_PX
        prefix_x = cx - 3.5
        value_x = cx + 3
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">
{body}
  <text x="{prefix_x}" y="{width_y}" font-size="{_DIV_EXPONENT_PREFIX_FONT_PX}" fill="#555555" text-anchor="middle" dominant-baseline="middle">2^</text>
  <text x="{value_x}" y="{width_y}" font-size="{width_font}" fill="{STROKE}" text-anchor="middle" dominant-baseline="middle">{DEFAULT_WIDTH}</text>
{stubs}{name_line}
</svg>
"""

    def verify_geometry(self) -> None:
        html = self.label_html()
        if f">%{ATTR_WIDTH}%</span>" not in html:
            raise ValueError("div_pow center label must render width exponent as HTML overlay")
        if f"font-size:{_DIV_EXPONENT_PREFIX_FONT_PX}px" not in html:
            raise ValueError("div_pow exponent prefix must render smaller than the width value")
        if "stroke-linecap=\"round\"" not in html or "<circle " not in html:
            raise ValueError("div_pow body must keep original top dot and horizontal bar")
        combined_half_w = (
            estimated_text_half_width("2^", _DIV_EXPONENT_PREFIX_FONT_PX) * 2
            + estimated_text_half_width("88", DIV_POWER_VALUE_FONT_PX) * 2
        ) / 2 + TEXT_HEX_CLEARANCE_PX
        top_y = self._width_y() - estimated_text_half_height(DIV_POWER_VALUE_FONT_PX)
        bar_y = self._g.body_mid_y + DIV_POWER_BAR_Y_OFFSET
        if top_y - bar_y < DIV_POWER_MIN_BAR_GAP_PX:
            raise ValueError("div_pow text must clear the divider bar")
        bottom_y = self._width_y() + estimated_text_half_height(DIV_POWER_VALUE_FONT_PX)
        available = div_hex_half_width_at_y(center_y=self._g.body_mid_y, y=bottom_y)
        if combined_half_w > available:
            raise ValueError("div_pow must fit two-digit width text inside the hexagon")
        super().verify_geometry()
