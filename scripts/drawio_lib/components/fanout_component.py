from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import isclose

import xml.etree.ElementTree as ET

from drawio_lib.components import fanout_geometry as fgeom
from drawio_lib.components import simple_geometry as sgeom
from drawio_lib.components.label_attrs import ATTR_NAME, INSTANCE_NAME_GAP_PX, LABEL_FONT_PX
from drawio_lib.components.label_html import (
    name_block,
    overlay_anchor,
    overlay_font_px,
    shell_close,
    shell_open,
    stretch_body_layer,
)
from drawio_lib.components.internal_kind import kind_style_suffix
from drawio_lib.components.label_overflow import (
    mxcell_html_label_style_parts,
    verify_label_overflow_policy,
)
from drawio_lib.components.simple_component import STROKE, verify_label_placeholders
from drawio_lib.xml_io import graph_root, xml_attr

DRAWCLOCK_TYPE_KEY = "drawclockType"
OUTPUT_LABEL_OFFSET_X = 6


def _svg_num(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


@dataclass
class FanoutComponent:
    """One input on the left and evenly spaced outputs on the right edge."""

    title: str
    tags: str
    body_svg: Callable[[sgeom.SimpleGeometry], str]
    output_count: int
    left_port_x: float
    left_port_y: float | None = None
    body_half_h: int | None = None
    center_labels: tuple[tuple[float, float, str], ...] | tuple[tuple[float, float, str, int], ...] = ()
    output_overlays: tuple[tuple[float, float, str], ...] | tuple[tuple[float, float, str, int], ...] = ()
    label_output_indices: bool = True
    output_cells: tuple[tuple[float, float], ...] | None = None
    instance_name_gap_px: int = INSTANCE_NAME_GAP_PX

    def __post_init__(self) -> None:
        rect = sgeom.body_rect()
        mid = sgeom.body_mid_y(rect)
        left_y = self.left_port_y if self.left_port_y is not None else mid
        self._g = fgeom.compute_fanout_geometry(
            left_x=self.left_port_x,
            left_y=left_y,
            output_count=self.output_count,
            body_half_h=self.body_half_h,
            output_cells=self.output_cells,
        )
        self._graphic_h = self._g.cell_h
        full_h = sgeom.cell_h_with_instance_name(
            name_top_y=self._instance_name_top_y(),
            instance_name_gap_px=self.instance_name_gap_px,
        )
        if full_h != self._g.cell_h:
            self._g = fgeom.reheight_fanout_geometry(self._g, full_h)
        self._body_g = sgeom.compute_geometry(
            "both",
            margin_x=4,
            port_cells=((self.left_port_x, left_y),),
        )

    @property
    def graphic_h(self) -> int:
        return self._graphic_h

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
    def g(self) -> fgeom.FanoutGeometry:
        return self._g

    @property
    def edit_data_attr_prefix(self) -> tuple[str, ...]:
        return (ATTR_NAME, "label")

    @property
    def required_object_attrs(self) -> tuple[str, ...]:
        return (ATTR_NAME,)

    def _output_labels(self) -> tuple[tuple[float, float, str], ...]:
        if not self.label_output_indices:
            return ()
        return tuple(
            (port.anchor.cell_x - OUTPUT_LABEL_OFFSET_X, port.anchor.cell_y, str(index))
            for index, port in enumerate(self._g.outputs)
        )

    def label_html(self) -> str:
        body = self.body_svg(self._body_g)
        overlays = self.center_labels + self.output_overlays + self._output_labels()
        return (
            f"{shell_open(self.w, self.h)}"
            f"{stretch_body_layer(body, view_w=self.w, view_h=self.graphic_h, overlays=overlays)}"
            f"{name_block(self._instance_name_top_y(), design_cell_h=self.h, gap_px=self.instance_name_gap_px)}"
            f"{shell_close()}"
        )

    def _instance_name_top_y(self) -> int:
        return sgeom.BODY_Y + sgeom.BODY_H + sgeom.MUX_BODY_PAD_BOTTOM

    def cell_style(self) -> str:
        bare = [fgeom.port_drawio_point(self._g.left)]
        bare.extend(fgeom.port_drawio_point(port) for port in self._g.outputs)
        points_inner = "],[".join(bare)
        return (
            f"{mxcell_html_label_style_parts()}"
            f"{DRAWCLOCK_TYPE_KEY}={self.drawclock_type};"
            f"{kind_style_suffix(self.drawclock_type)}"
            f"points=[[{points_inner}]];"
        )

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

    def preview_svg(self) -> str:
        body = self.body_svg(self._body_g)
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
            anchor = port.anchor
            stub_lines.append(
                f'  <circle cx="{_svg_num(anchor.cell_x)}" cy="{_svg_num(anchor.cell_y)}" '
                f'r="2.5" fill="{color}"/>'
            )
        stubs = "\n".join(stub_lines)
        output_texts = ""
        if self.label_output_indices:
            output_texts = "\n".join(
                f'  <text x="{_svg_num(port.anchor.cell_x - OUTPUT_LABEL_OFFSET_X)}" '
                f'y="{_svg_num(port.anchor.cell_y)}" font-size="11" fill="{STROKE}" '
                f'text-anchor="middle" dominant-baseline="middle">{index}</text>'
                for index, port in enumerate(self._g.outputs)
            )
        _anchor_to_svg = {"left": "start", "center": "middle", "right": "end"}
        overlay_texts = "\n".join(
            f'  <text x="{_svg_num(item[0])}" y="{_svg_num(item[1])}" '
            f'font-size="{overlay_font_px(item)}" fill="{STROKE}" '
            f'text-anchor="{_anchor_to_svg[overlay_anchor(item)]}" '
            f'dominant-baseline="middle">{item[2]}</text>'
            for item in (*self.center_labels, *self.output_overlays)
        )
        name_y = (
            self._instance_name_top_y()
            + self.instance_name_gap_px
            + sgeom.NAME_H // 2
        )
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">
{body}
{overlay_texts}
{output_texts}
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
            parts = [float(value) for value in token.split(",")]
            if len(parts) not in (2, 5):
                raise ValueError(f"{self.title} style: bad point tuple {token!r}")
            pairs.append(tuple(parts))
        return pairs

    def verify_geometry(self) -> None:
        html = self.label_html()
        verify_label_placeholders(html, title=self.title)
        if f'viewBox="0 0 {self.w} {self.graphic_h}"' not in html:
            raise ValueError(f"{self.title} label must use graphic viewBox")
        style = self.cell_style()
        verify_label_overflow_policy(
            html,
            style,
            title=self.title,
            design_cell_w=self.w,
            design_cell_h=self.h,
            graphic_cell_h=self.graphic_h,
        )
        points = self._parse_points(style)
        expected = 1 + len(self._g.outputs)
        if len(points) != expected:
            raise ValueError(
                f"{self.title} expects {expected} connection points, got {points}"
            )
        ports = (self._g.left, *self._g.outputs)
        for point, port in zip(points, ports):
            anchor = port.anchor
            if len(point) != 5 or point[2] != float(fgeom.POINT_FIXED):
                raise ValueError(f"{self.title}: must use 5-value points [x,y,0,0,0]")
            if not isclose(point[0], anchor.x_rel, abs_tol=0.002):
                raise ValueError(f"{self.title}: rel_x mismatch")
            if not isclose(point[1], anchor.y_rel, abs_tol=0.002):
                raise ValueError(f"{self.title}: rel_y mismatch")

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


def bind_module(module: object, component: FanoutComponent) -> None:
    mapping = {
        "TITLE": component.title,
        "TAGS": component.tags,
        "W": component.w,
        "H": component.h,
        "GRAPHIC_H": component.graphic_h,
        "DEFAULT_INSTANCE_GAP": component.instance_name_gap_px,
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
