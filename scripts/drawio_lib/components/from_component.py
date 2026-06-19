from __future__ import annotations

from dataclasses import dataclass
from math import isclose

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.label_attrs import verify_label_placeholders
from drawio_lib.components.label_overflow import (
    mxcell_html_label_style_parts,
    verify_label_overflow_policy,
)
from drawio_lib.components.label_html import name_block, shell_close, shell_open, stretch_body_layer
from drawio_lib.components.simple_component import SimpleComponent
from drawio_lib.components.simple_shapes import wire_body


@dataclass
class FromComponent(SimpleComponent):
    """Cross-sheet output stub; logical input follows the same-named clock."""

    def _instance_name_top_y(self) -> int:
        return geom.WIRE_STROKE_Y + 8

    def label_html(self) -> str:
        body = wire_body(self._g)
        return (
            f"{shell_open(self.w, self.h)}"
            f"{stretch_body_layer(body, view_w=self.w, view_h=self.h)}"
            f"{name_block(self._instance_name_top_y(), design_cell_h=self.h, gap_px=self.instance_name_gap_px)}"
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
        body = wire_body(self._g)
        name_y = self._instance_name_top_y() + 6
        stub_lines = []
        for port, color in zip(self._ports(), ("#090",)):
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
{stubs}
  <text x="{self.w // 2}" y="{name_y}" font-size="11" fill="#000000" text-anchor="middle" dominant-baseline="middle">{self.title}</text>
</svg>
"""

    def verify_geometry(self) -> None:
        html = self.label_html()
        verify_label_placeholders(html, title="from")
        if "width:100%" not in html or "height:100%" not in html:
            raise ValueError("from label shell must fill the shape (100%)")
        if f'viewBox="0 0 {self.w} {self.h}"' not in html:
            raise ValueError("from viewBox must match cell width and height")
        if 'preserveAspectRatio="none"' not in html:
            raise ValueError("from body SVG must stretch with the shape (none)")
        style = self.cell_style()
        verify_label_overflow_policy(
            html,
            style,
            title="from",
            design_cell_w=self.w,
            design_cell_h=self.h,
        )

        pts = self._parse_points(style)
        if len(pts) != 1:
            raise ValueError(f"from expects 1 connection point, got {pts}")
        right = self._ports()[0]
        pt = pts[0]
        a = right.anchor
        if len(pt) != 5 or pt[2] != float(geom.POINT_FIXED):
            raise ValueError("from right: must use 5-value points [x,y,0,0,0]")
        if not isclose(pt[0], a.x_rel, abs_tol=0.002):
            raise ValueError("from right: rel_x mismatch")
        if not isclose(pt[1], a.y_rel, abs_tol=0.002):
            raise ValueError("from right: rel_y mismatch")
