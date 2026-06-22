from __future__ import annotations

from dataclasses import dataclass

import xml.etree.ElementTree as ET

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.label_html import shell_close, shell_open, stretch_body_layer
from drawio_lib.components.internal_kind import kind_style_suffix
from drawio_lib.components.label_overflow import mxcell_html_label_style_parts
from drawio_lib.components.simple_component import verify_label_placeholders
from drawio_lib.components.simple_shapes import (
    ASYNC_CROSS_HALF_H,
    ASYNC_CROSS_LEFT,
    ASYNC_CROSS_RIGHT,
    ASYNC_STROKE,
)
from drawio_lib.xml_io import graph_root, xml_attr

DRAWCLOCK_TYPE_KEY = "drawclockType"
ASYNC_CELL_W = ASYNC_CROSS_RIGHT - ASYNC_CROSS_LEFT
ASYNC_CELL_H = 2 * ASYNC_CROSS_HALF_H


def _async_geometry() -> geom.SimpleGeometry:
    mid = ASYNC_CELL_H / 2
    left = geom.make_port(0, mid, side="left", cell_height=ASYNC_CELL_H, cell_w=ASYNC_CELL_W)
    right = geom.make_port(
        ASYNC_CELL_W, mid, side="right", cell_height=ASYNC_CELL_H, cell_w=ASYNC_CELL_W
    )
    return geom.SimpleGeometry(
        body=geom.BodyRect(x=0, y=0, w=ASYNC_CELL_W, h=ASYNC_CELL_H),
        left=left,
        right=right,
        body_mid_y=int(mid),
        cell_h=ASYNC_CELL_H,
        cell_w=ASYNC_CELL_W,
    )


def _async_body(g: geom.SimpleGeometry) -> str:
    mid = g.body_mid_y
    left = g.body.x
    right = g.body.x + g.body.w
    top = mid - ASYNC_CROSS_HALF_H
    bottom = mid + ASYNC_CROSS_HALF_H
    return (
        f'<path d="M {left} {top} L {right} {bottom} '
        f"M {right} {top} L {left} {bottom}\" "
        f'fill="none" stroke="{ASYNC_STROKE}" stroke-width="2.5" '
        f'stroke-linecap="round"/>'
    )


@dataclass
class AsyncMarkerComponent:
    title: str = "async"
    tags: str = "async clock drawclock"

    def __post_init__(self) -> None:
        self._g = _async_geometry()

    @property
    def drawclock_type(self) -> str:
        return self.title

    @property
    def w(self) -> int:
        return ASYNC_CELL_W

    @property
    def h(self) -> int:
        return ASYNC_CELL_H

    @property
    def g(self) -> geom.SimpleGeometry:
        return self._g

    @property
    def edit_data_attr_prefix(self) -> tuple[str, ...]:
        return ()

    @property
    def required_object_attrs(self) -> tuple[str, ...]:
        return ()

    def label_html(self) -> str:
        body = _async_body(self._g)
        return (
            f"{shell_open(self.w, self.h)}"
            f"{stretch_body_layer(body, view_w=self.w, view_h=self.h, overlays=())}"
            f"{shell_close()}"
        )

    def preview_svg(self) -> str:
        body = _async_body(self._g)
        stub_lines = []
        for port, color in zip(
            (self._g.left, self._g.right),
            ("#c00", "#090"),
        ):
            assert port is not None
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
</svg>
"""

    def cell_style(self) -> str:
        ports = [self._g.left, self._g.right]
        bare = [geom.port_drawio_point(p) for p in ports if p is not None]
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
        del instance_name
        style = self.cell_style()
        label = xml_attr(self.label_html())
        attrs = [
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
            pairs.append(tuple(parts))
        return pairs

    def verify_geometry(self) -> None:
        html = self.label_html()
        verify_label_placeholders(html, title=self.title)
        if f'viewBox="0 0 {self.w} {self.h}"' not in html:
            raise ValueError(f"{self.title} label must use cell viewBox")
        if "%name%" in html:
            raise ValueError(f"{self.title} must not include instance name placeholder")
        if f'stroke="{ASYNC_STROKE}"' not in html:
            raise ValueError(f"{self.title} must draw red cross")
        style = self.cell_style()
        pts = self._parse_points(style)
        assert len(pts) == 2

    def verify_object(self, wrapper: ET.Element, *, context: str = "") -> None:
        del wrapper, context

    def verify_library_graph(self, graph_xml: str) -> None:
        graph_root_elem = ET.fromstring(graph_xml)
        graph = graph_root(graph_root_elem)
        for obj in graph.iter("object"):
            if obj.find("mxCell") is None:
                continue
            if obj.get("name") is not None:
                raise ValueError(f"{self.title} library: async must not carry name attr")
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


def bind_module(module: object, component: AsyncMarkerComponent) -> None:
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
