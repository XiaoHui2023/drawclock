from __future__ import annotations

from dataclasses import dataclass
from math import isclose

import xml.etree.ElementTree as ET

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.label_attrs import (
    ATTR_NAME,
    CLOCK_FREQ_GAP_PX,
    CLOCK_INSTANCE_NAME_GAP_PX,
    LABEL_FONT_PX,
    verify_label_placeholders,
)
from drawio_lib.components.label_html import name_block, shell_close, shell_open, stretch_body_layer
from drawio_lib.components.label_overflow import (
    mxcell_html_label_style_parts,
    verify_label_overflow_policy,
)
from drawio_lib.components.simple_component import (
    STROKE,
    SimpleComponent,
    xml_attr,
)
from drawio_lib.components.simple_shapes import (
    CLOCK_BODY_MARGIN_X,
    CLOCK_CELL_W,
    CLOCK_WAVE_AMP,
    clock_body,
)

ATTR_FREQ = "freq"


@dataclass
class ClockComponent(SimpleComponent):
    """Clock terminal with (freq hz) label."""

    cell_w: int = CLOCK_CELL_W
    body_margin_x: int = CLOCK_BODY_MARGIN_X
    instance_name_gap_px: int = CLOCK_INSTANCE_NAME_GAP_PX
    freq_gap_px: int = CLOCK_FREQ_GAP_PX

    def __post_init__(self) -> None:
        self._g = geom.compute_geometry(
            self.port_mode,
            body_height=self.body_height,
            margin_x=self.body_margin_x,
            port_cells=self.port_cells,
            cell_w=self.cell_w,
            asymmetric_clock=True,
        )

    @property
    def w(self) -> int:
        return self.cell_w

    @property
    def edit_data_attr_prefix(self) -> tuple[str, ...]:
        return (
            ATTR_FREQ,
            ATTR_NAME,
            "label",
        )

    @property
    def required_object_attrs(self) -> tuple[str, ...]:
        return (
            ATTR_FREQ,
            ATTR_NAME,
        )

    def _graphic_center_x(self) -> int:
        rect = self._g.body
        return rect.x + rect.w // 2

    def _instance_name_top_y(self) -> int:
        return self._g.body_mid_y + CLOCK_WAVE_AMP

    def label_html(self) -> str:
        wave = clock_body(self._g)
        rect = self._g.body
        wave_right = rect.x + rect.w
        row_h = self.h - geom.NAME_H - geom.MUX_BODY_PAD_BOTTOM
        freq_left_pct = wave_right / self.w * 100
        freq_top_pct = (row_h // 2) / self.h * 100
        return (
            f"{shell_open(self.w, self.h)}"
            f"{stretch_body_layer(wave, view_w=self.w, view_h=self.h)}"
            f'<div style="position:absolute;left:{freq_left_pct}%;top:{freq_top_pct}%;'
            f"display:flex;align-items:center;"
            f'white-space:nowrap;transform:translateY(-50%);">'
            f'<div style="flex:0 0 auto;width:{self.freq_gap_px}px;"></div>'
            f'<span style="flex:0 0 auto;font-size:{LABEL_FONT_PX}px;line-height:1;'
            f'white-space:nowrap;">(%freq%hz)</span>'
            f"</div>"
            f"{name_block(self._instance_name_top_y(), design_cell_h=self.h, design_cell_w=self.w, center_x=self._graphic_center_x(), gap_px=self.instance_name_gap_px)}"
            f"{shell_close()}"
        )

    def cell_style(self) -> str:
        bare = [geom.port_drawio_point(p) for p in self._ports()]
        points_inner = "],[".join(bare)
        points_clause = f"points=[[{points_inner}]];" if bare else ""
        return (
            f"{mxcell_html_label_style_parts()}"
            f"drawclockType={self.drawclock_type};"
            f"{points_clause}"
        )

    def preview_svg(self) -> str:
        wave = clock_body(self._g)
        cell_mid = self._g.body_mid_y
        port = self._ports()[0]
        a = port.anchor
        name_y = (
            self._instance_name_top_y()
            + self.instance_name_gap_px
            + geom.NAME_H // 2
        )
        wave_right = self._g.body.x + self._g.body.w
        freq_x = wave_right + self.freq_gap_px
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">
{wave}
<text x="{freq_x}" y="{cell_mid}" font-size="7" fill="{STROKE}" text-anchor="start" dominant-baseline="middle">(MHz)</text>
  <text x="{self._graphic_center_x()}" y="{name_y}" font-size="{LABEL_FONT_PX}" fill="{STROKE}" text-anchor="middle" dominant-baseline="middle">{self.title}</text>
  <line x1="{port.stub_x1}" y1="{port.stub_y1}" x2="{port.stub_x2}" y2="{port.stub_y2}" stroke="#c00" stroke-width="1"/>
  <circle cx="{a.cell_x}" cy="{a.cell_y}" r="2.5" fill="#c00"/>
</svg>
"""

    def cell_fragment(
        self,
        cell_id: str,
        instance_name: str | None = None,
        *,
        freq: str = "",
        x: int | None = None,
        y: int | None = None,
    ) -> str:
        style = self.cell_style()
        name = xml_attr(instance_name if instance_name is not None else self.title)
        freq_val = xml_attr(freq)
        label = xml_attr(self.label_html())
        attrs = [
            f'{ATTR_FREQ}="{freq_val}"',
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

    def verify_geometry(self) -> None:
        html = self.label_html()
        verify_label_placeholders(html, title="clock")
        if f"%{ATTR_FREQ}%hz)" not in html:
            raise ValueError("clock label must include (freq hz) placeholder")
        if f"width:{self.freq_gap_px}px" not in html:
            raise ValueError("clock label must include fixed freq gap spacer width")
        if "width:%freq_gap%px" in html:
            raise ValueError("clock label must not use editable freq_gap placeholder")
        if f'viewBox="0 0 {self.w} {self.h}"' not in html:
            raise ValueError("clock wave SVG viewBox must match cell width and height")
        if 'preserveAspectRatio="none"' not in html:
            raise ValueError("clock body SVG must stretch with the shape (none)")
        if "white-space:nowrap" not in html:
            raise ValueError("clock freq label must not wrap")
        style = self.cell_style()
        if "autosize=0" not in style:
            raise ValueError("clock style must use autosize=0")
        verify_label_overflow_policy(
            html,
            style,
            title="clock",
            design_cell_w=self.w,
            design_cell_h=self.h,
        )

        pts = self._parse_points(style)
        if len(pts) != 1:
            raise ValueError(f"clock expects 1 connection point, got {pts}")
        port = self._ports()[0]
        a = port.anchor
        pt = pts[0]
        if len(pt) != 5 or pt[2] != float(geom.POINT_FIXED):
            raise ValueError("clock: must use 5-value points [x,y,0,0,0]")
        if not isclose(pt[0], a.x_rel, abs_tol=0.002):
            raise ValueError("clock: rel_x mismatch")
        if not isclose(pt[1], a.y_rel, abs_tol=0.002):
            raise ValueError("clock: rel_y mismatch")

    def verify_library_graph(self, graph_xml: str) -> None:
        from drawio_lib.xml_io import graph_root

        graph = graph_root(ET.fromstring(graph_xml))
        for obj in graph.iter("object"):
            if obj.find("mxCell") is None:
                continue
            keys = list(obj.attrib.keys())
            if keys[: len(self.edit_data_attr_prefix)] != list(
                self.edit_data_attr_prefix
            ):
                raise ValueError(
                    f"{self.title} edit-data attribute order must start with "
                    f"{list(self.edit_data_attr_prefix)}, got "
                    f"{keys[: len(self.edit_data_attr_prefix)]}"
                )
            break
        else:
            raise ValueError(f"{self.title} library: missing object wrapper")
        super().verify_library_graph(graph_xml)
