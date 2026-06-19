from __future__ import annotations

from dataclasses import dataclass
from math import isclose

import xml.etree.ElementTree as ET

from drawio_lib.components import pll2_geometry as geom
from drawio_lib.components import simple_geometry as sgeom
from drawio_lib.components.label_attrs import ATTR_NAME, INSTANCE_NAME_GAP_PX
from drawio_lib.components.pll_component import (
    ATTR_PLL_KIND,
    DEFAULT_PLL_KIND,
    PLL_CENTER_FONT_PX,
)
from drawio_lib.components.label_html import (
    name_block,
    shell_close,
    shell_open,
    stretch_body_layer,
)
from drawio_lib.components.label_overflow import (
    mxcell_html_label_style_parts,
    verify_label_overflow_policy,
)
from drawio_lib.components.simple_component import STROKE, verify_label_placeholders
from drawio_lib.components.simple_shapes import (
    FILL,
    PLL_BODY_HALF_H,
    PLL_LEFT_NOTCH_HALF,
    PLL_LEFT_X,
    PLL_TIP_X,
    SW,
    pll_label_cx,
)
from drawio_lib.xml_io import graph_root, xml_attr

DRAWCLOCK_TYPE_KEY = "drawclockType"


def _svg_num(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def pll2_body(g: sgeom.SimpleGeometry) -> str:
    mid = g.body_mid_y
    top_y = mid - PLL_BODY_HALF_H
    bot_y = mid + PLL_BODY_HALF_H
    pad = sgeom.side_pad_x(g.cell_w)
    lx = pad + PLL_LEFT_X
    sx = pad + geom.PLL2_SHOULDER_X
    tx = pad + PLL_TIP_X
    notch_top = mid - PLL_LEFT_NOTCH_HALF
    notch_bot = mid + PLL_LEFT_NOTCH_HALF
    return (
        f'<path d="M {lx} {top_y} L {sx} {top_y} L {tx} {mid} L {sx} {bot_y} '
        f'L {lx} {bot_y} L {lx} {notch_bot} M {lx} {notch_top} L {lx} {top_y}" '
        f'fill="{FILL}" stroke="{STROKE}" stroke-width="{SW}" stroke-linejoin="round" '
        f'stroke-linecap="round"/>'
    )


@dataclass
class Pll2Component:
    """PLL with two independent outputs on the right edge."""

    title: str = "pll2"
    tags: str = "pll2 pll clock drawclock"

    def __post_init__(self) -> None:
        self._g = geom.compute_geometry()
        pad = sgeom.side_pad_x(sgeom.W) + PLL_LEFT_X
        self._body_g = sgeom.compute_geometry(
            "both",
            margin_x=4,
            port_cells=((pad, self._g.body_mid_y),),
        )

    @property
    def drawclock_type(self) -> str:
        return self.title

    @property
    def w(self) -> int:
        return sgeom.W

    @property
    def h(self) -> int:
        return self._g.cell_h

    @property
    def g(self) -> geom.Pll2Geometry:
        return self._g

    @property
    def edit_data_attr_prefix(self) -> tuple[str, ...]:
        return (ATTR_PLL_KIND, ATTR_NAME, "label")

    @property
    def required_object_attrs(self) -> tuple[str, ...]:
        return (ATTR_PLL_KIND, ATTR_NAME)

    def _center_labels(self) -> tuple[tuple[float, float, str], ...]:
        mid = self._g.body_mid_y
        return ((pll_label_cx(self._body_g), mid, f"%{ATTR_PLL_KIND}%"),)

    def label_html(self) -> str:
        body = pll2_body(self._body_g)
        overlays = self._center_labels()
        return (
            f"{shell_open(self.w, self.h)}"
            f"{stretch_body_layer(body, view_w=self.w, view_h=self.h, overlays=overlays)}"
            f"{name_block(self._instance_name_top_y(), design_cell_h=self.h, gap_px=INSTANCE_NAME_GAP_PX)}"
            f"{shell_close()}"
        )

    def _instance_name_top_y(self) -> int:
        return sgeom.BODY_Y + sgeom.BODY_H + sgeom.MUX_BODY_PAD_BOTTOM

    def cell_style(self) -> str:
        bare = [geom.port_drawio_point(self._g.left)]
        bare.extend(geom.port_drawio_point(port) for port in self._g.outputs)
        points_inner = "],[".join(bare)
        return (
            f"{mxcell_html_label_style_parts()}"
            f"{DRAWCLOCK_TYPE_KEY}={self.drawclock_type};"
            f"points=[[{points_inner}]];"
        )

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
        name = xml_attr(instance_name if instance_name is not None else self.title)
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
        body = pll2_body(self._body_g)
        mid = self._g.body_mid_y
        stub_lines = []
        for port, color in (
            (self._g.left, "#c00"),
            *[(port, "#090") for port in self._g.outputs],
        ):
            stub_lines.append(
                f'  <line x1="{_svg_num(port.stub_x1)}" y1="{_svg_num(port.stub_y1)}" '
                f'x2="{_svg_num(port.stub_x2)}" y2="{_svg_num(port.stub_y2)}" stroke="{color}" '
                f'stroke-width="1"/>'
            )
            a = port.anchor
            stub_lines.append(
                f'  <circle cx="{_svg_num(a.cell_x)}" cy="{_svg_num(a.cell_y)}" '
                f'r="2.5" fill="{color}"/>'
            )
        stubs = "\n".join(stub_lines)
        name_y = self._instance_name_top_y() + sgeom.NAME_H // 2
        label_x = pll_label_cx(self._body_g)
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">
{body}
  <text x="{label_x}" y="{mid}" font-size="{PLL_CENTER_FONT_PX}" fill="{STROKE}" text-anchor="middle" dominant-baseline="middle">{DEFAULT_PLL_KIND}</text>
{stubs}
  <text x="{self.w // 2}" y="{name_y}" font-size="11" fill="{STROKE}" text-anchor="middle" dominant-baseline="middle">{self.title}</text>
</svg>
"""

    def graph_xml(self) -> str:
        return (
            "<mxGraphModel><root>"
            '<mxCell id="0"/>'
            '<mxCell id="1" parent="0"/>'
            f'{self.cell_fragment("2")}'
            "</root></mxGraphModel>"
        )

    def library_entry(self) -> dict[str, object]:
        from drawio_lib.xml_io import compress_drawio_xml

        return {
            "xml": compress_drawio_xml(self.graph_xml()),
            "w": self.w,
            "h": self.h,
            "title": self.title,
            "tags": self.tags,
        }

    def _parse_points(self, style: str) -> list[tuple[float, ...]]:
        marker = "points=[["
        start = style.find(marker)
        if start < 0:
            return []
        start += len(marker)
        end = style.find("]]", start)
        if end < 0:
            raise ValueError(f"{self.title} style: unclosed points=[[...]]")
        pairs: list[tuple[float, ...]] = []
        for token in style[start:end].split("],["):
            parts = [float(v) for v in token.split(",")]
            if len(parts) not in (2, 5):
                raise ValueError(f"{self.title} style: bad point tuple {token!r}")
            pairs.append(tuple(parts))
        return pairs

    def verify_geometry(self) -> None:
        html = self.label_html()
        verify_label_placeholders(html, title=self.title)
        if f">%{ATTR_PLL_KIND}%</span>" not in html:
            raise ValueError("pll2 label must render pll_kind as non-scaling HTML overlay")
        if f'viewBox="0 0 {self.w} {self.h}"' not in html:
            raise ValueError(f"{self.title} label must use cell viewBox")
        style = self.cell_style()
        verify_label_overflow_policy(
            html,
            style,
            title=self.title,
            design_cell_w=self.w,
            design_cell_h=self.h,
        )
        pts = self._parse_points(style)
        expected = 1 + len(self._g.outputs)
        if len(pts) != expected:
            raise ValueError(f"{self.title} expects {expected} connection points, got {pts}")
        ports = (self._g.left, *self._g.outputs)
        labels = ("left", "out0", "out1")
        for pt, port, label in zip(pts, ports, labels):
            a = port.anchor
            if len(pt) != 5 or pt[2] != float(geom.POINT_FIXED):
                raise ValueError(f"{label}: must use 5-value points [x,y,0,0,0]")
            if not isclose(pt[0], a.x_rel, abs_tol=0.002):
                raise ValueError(f"{label}: rel_x mismatch")
            if not isclose(pt[1], a.y_rel, abs_tol=0.002):
                raise ValueError(f"{label}: rel_y mismatch")

    def verify_object(self, wrapper: ET.Element, *, context: str = "") -> None:
        prefix = f"{context}: " if context else ""
        for field in self.required_object_attrs:
            if wrapper.get(field) is None:
                raise ValueError(f"{prefix}outer <object> missing {field}")

    def verify_library_graph(self, graph_xml: str) -> None:
        graph_root_elem = ET.fromstring(graph_xml)
        graph = graph_root(graph_root_elem)
        for obj in graph.iter("object"):
            if obj.find("mxCell") is None:
                continue
            self.verify_object(obj, context=self.title)
            mxcell = obj.find("mxCell")
            assert mxcell is not None
            style = mxcell.get("style") or ""
            if f"{DRAWCLOCK_TYPE_KEY}={self.drawclock_type}" not in style:
                raise ValueError(
                    f"{self.title} library XML: mxCell style must include "
                    f"{DRAWCLOCK_TYPE_KEY}={self.drawclock_type}"
                )
            break
        else:
            raise ValueError(f"{self.title} library: missing object wrapper")


def bind_module(module: object, component: Pll2Component) -> None:
    mapping = {
        "TITLE": component.title,
        "TAGS": component.tags,
        "W": component.w,
        "H": component.h,
        "G": component.g,
        "label_html": component.label_html,
        "preview_svg": component.preview_svg,
        "cell_style": component.cell_style,
        "cell_fragment": component.cell_fragment,
        "graph_xml": component.graph_xml,
        "library_entry": component.library_entry,
        "verify_geometry": component.verify_geometry,
        "verify_object": component.verify_object,
        "verify_library_graph": component.verify_library_graph,
        "_parse_points": component._parse_points,
    }
    for name, value in mapping.items():
        setattr(module, name, value)
