from __future__ import annotations

from dataclasses import dataclass
from math import isclose

import xml.etree.ElementTree as ET

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.label_attrs import (
    ATTR_NAME,
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


@dataclass
class ClockComponent(SimpleComponent):
    """Clock terminal with square wave and instance name."""

    cell_w: int = CLOCK_CELL_W
    body_margin_x: int = CLOCK_BODY_MARGIN_X

    def __post_init__(self) -> None:
        self._g = geom.compute_geometry(
            self.port_mode,
            body_height=self.body_height,
            margin_x=self.body_margin_x,
            port_cells=self.port_cells,
            cell_w=self.cell_w,
            asymmetric_clock=True,
            instance_name_gap_px=self.instance_name_gap_px,
        )
        self._graphic_h = self._g.cell_h
        self._expand_cell_h_for_instance_name()

    @property
    def w(self) -> int:
        return self.cell_w

    @property
    def edit_data_attr_prefix(self) -> tuple[str, ...]:
        return (
            ATTR_NAME,
            "label",
        )

    @property
    def required_object_attrs(self) -> tuple[str, ...]:
        return (ATTR_NAME,)

    def _graphic_center_x(self) -> int:
        rect = self._g.body
        return rect.x + rect.w // 2

    def _instance_name_top_y(self) -> int:
        return self._g.body_mid_y + CLOCK_WAVE_AMP

    def label_html(self) -> str:
        wave = clock_body(self._g)
        return (
            f"{shell_open(self.w, self.h)}"
            f"{stretch_body_layer(wave, view_w=self.w, view_h=self.graphic_h)}"
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
        port = self._ports()[0]
        a = port.anchor
        name_y = (
            self._instance_name_top_y()
            + self.instance_name_gap_px
            + geom.NAME_H // 2
        )
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">
{wave}
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
        x: int | None = None,
        y: int | None = None,
    ) -> str:
        style = self.cell_style()
        name = xml_attr(instance_name if instance_name is not None else self.title)
        label = xml_attr(self.label_html())
        attrs = [
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
        if f'viewBox="0 0 {self.w} {self.graphic_h}"' not in html:
            raise ValueError("clock wave SVG viewBox must match cell width and graphic height")
        if 'preserveAspectRatio="none"' not in html:
            raise ValueError("clock body SVG must stretch with the shape (none)")
        style = self.cell_style()
        if "autosize=0" not in style:
            raise ValueError("clock style must use autosize=0")
        verify_label_overflow_policy(
            html,
            style,
            title="clock",
            design_cell_w=self.w,
            design_cell_h=self.h,
            graphic_cell_h=self.graphic_h,
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
