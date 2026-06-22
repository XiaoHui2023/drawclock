from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import isclose

import xml.etree.ElementTree as ET

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.label_attrs import (
    ATTR_NAME,
    INSTANCE_NAME_GAP_PX,
    LABEL_FONT_PX,
    base_object_attrs,
    verify_label_placeholders,
)
from drawio_lib.components.label_html import (
    name_block,
    shell_close,
    shell_open,
    stretch_body_layer,
)
from drawio_lib.components.internal_kind import kind_style_suffix
from drawio_lib.components.label_overflow import (
    mxcell_html_label_style_parts,
    verify_label_overflow_policy,
)
from drawio_lib.xml_io import graph_root, xml_attr

STROKE = "#000000"
FILL = "none"
DEFAULT_INSTANCE_GAP = INSTANCE_NAME_GAP_PX
ATTR_INSTANCE_NAME = ATTR_NAME
DRAWCLOCK_TYPE_KEY = "drawclockType"


@dataclass
class SimpleComponent:
    """One draw.io library shape with left/right clock-tree ports."""

    title: str
    tags: str
    port_mode: geom.PortMode
    body_svg: Callable[[geom.SimpleGeometry], str]
    body_height: int = geom.BODY_H
    body_margin_x: int = geom.BODY_MARGIN_X
    show_instance_name: bool = True
    port_cells: tuple[tuple[int, int], ...] | None = None
    instance_name_gap_px: int = INSTANCE_NAME_GAP_PX
    instance_name_pull_px: int = 0
    cell_w: int = geom.W
    body_pad_bottom: int = geom.MUX_BODY_PAD_BOTTOM
    max_instance_gap: int = geom.MAX_INSTANCE_GAP

    def __post_init__(self) -> None:
        if self.port_mode == "from":
            self._g = geom.compute_from_geometry()
        else:
            self._g = geom.compute_geometry(
                self.port_mode,
                body_height=self.body_height,
                margin_x=self.body_margin_x,
                port_cells=self.port_cells,
                cell_w=self.cell_w,
                body_pad_bottom=self.body_pad_bottom,
                max_instance_gap=self.max_instance_gap,
            )

    @property
    def drawclock_type(self) -> str:
        return self.title

    @property
    def json_kind(self) -> str:
        return self.drawclock_type

    @property
    def w(self) -> int:
        return self.cell_w

    @property
    def h(self) -> int:
        return self._g.cell_h

    @property
    def g(self) -> geom.SimpleGeometry:
        return self._g

    @property
    def edit_data_attr_prefix(self) -> tuple[str, ...]:
        return (ATTR_NAME, "label")

    @property
    def required_object_attrs(self) -> tuple[str, ...]:
        return (ATTR_NAME,)

    def _ports(self) -> tuple[geom.Port, ...]:
        out: list[geom.Port] = []
        if self._g.left is not None:
            out.append(self._g.left)
        if self._g.right is not None:
            out.append(self._g.right)
        return tuple(out)

    def _instance_name_top_y(self) -> int:
        if self.port_mode == "from":
            return geom.WIRE_STROKE_Y + 8
        return (
            geom.BODY_Y
            + self.body_height
            + self.body_pad_bottom
            - self.instance_name_pull_px
        )

    def _resolve_instance_name(self, instance_name: str | None) -> str:
        if instance_name is None:
            return self.title
        return instance_name

    def _label_html_with_overlay(
        self,
        body: str,
        overlays: tuple[tuple[float, float, str], ...] | tuple[tuple[float, float, str, int], ...],
    ) -> str:
        parts = [
            shell_open(self.w, self.h),
            stretch_body_layer(
                body,
                view_w=self.w,
                view_h=self.h,
                overlays=overlays,
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

    def label_html(self) -> str:
        body = self.body_svg(self._g)
        return self._label_html_with_overlay(body, ())

    def preview_svg(self) -> str:
        body = self.body_svg(self._g)
        stub_lines = []
        for port, color in zip(
            self._ports(),
            ("#c00", "#090") if len(self._ports()) == 2 else ("#c00",),
        ):
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
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">
{body}
{stubs}{name_line}
</svg>
"""

    def cell_style(self) -> str:
        bare = [geom.port_drawio_point(p) for p in self._ports()]
        points_inner = "],[".join(bare)
        points_clause = f"points=[[{points_inner}]];" if bare else ""
        return (
            f"{mxcell_html_label_style_parts()}"
            f"{DRAWCLOCK_TYPE_KEY}={self.drawclock_type};"
            f"{kind_style_suffix(self.json_kind)}"
            f"{points_clause}"
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
        name = xml_attr(self._resolve_instance_name(instance_name))
        label = xml_attr(self.label_html())
        attrs = [
            f'{k}="{xml_attr(v)}"'
            for k, v in base_object_attrs(name=name)
        ]
        attrs.extend(
            [
                f'label="{label}"',
                'placeholders="1"',
                f'id="{cell_id}"',
            ]
        )
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
        if f'viewBox="0 0 {self.w} {self.h}"' not in html:
            raise ValueError(f"{self.title} label must use cell viewBox")
        if 'preserveAspectRatio="none"' not in html:
            raise ValueError(f"{self.title} body SVG must stretch with the shape (none)")
        if f'width="{self.w}"' not in html:
            raise ValueError(f"{self.title} label shell must size the SVG ({self.w}px width)")
        if "<line " in html and self.port_mode != "from":
            raise ValueError(f"{self.title} label must not draw port stub lines")
        style = self.cell_style()
        if self.show_instance_name:
            verify_label_overflow_policy(
                html,
                style,
                title=self.title,
                design_cell_w=self.w,
                design_cell_h=self.h,
            )
        if f"{DRAWCLOCK_TYPE_KEY}={self.drawclock_type}" not in style:
            raise ValueError(f"{self.title} style must set {DRAWCLOCK_TYPE_KEY}")

        pts = self._parse_points(style)
        expected = len(self._ports())
        if len(pts) != expected:
            raise ValueError(
                f"{self.title} expects {expected} connection points, got {pts}"
            )
        for pt, port in zip(pts, self._ports()):
            a = port.anchor
            if len(pt) != 5 or pt[2] != float(geom.POINT_FIXED):
                raise ValueError(f"{self.title}: must use 5-value points [x,y,0,0,0]")
            if not isclose(pt[0], a.x_rel, abs_tol=0.002):
                raise ValueError(f"{self.title}: rel_x mismatch")
            if not isclose(pt[1], a.y_rel, abs_tol=0.002):
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


def bind_module(module: object, component: SimpleComponent) -> None:
    mapping = {
        "TITLE": component.title,
        "TAGS": component.tags,
        "W": component.w,
        "H": component.h,
        "G": component.g,
        "DEFAULT_INSTANCE_GAP": DEFAULT_INSTANCE_GAP,
        "ATTR_INSTANCE_NAME": ATTR_INSTANCE_NAME,
        "LABEL_FONT_PX": LABEL_FONT_PX,
        "DRAWCLOCK_TYPE_KEY": DRAWCLOCK_TYPE_KEY,
        "DRAWCLOCK_TYPE_VALUE": component.drawclock_type,
        "EDIT_DATA_ATTR_PREFIX": component.edit_data_attr_prefix,
        "REQUIRED_OBJECT_ATTRS": component.required_object_attrs,
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
