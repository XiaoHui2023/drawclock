from __future__ import annotations

from dataclasses import dataclass
from math import isclose

import xml.etree.ElementTree as ET

from drawio_lib.components import mux_geometry as geom
from drawio_lib.components.label_attrs import (
    ATTR_NAME,
    INSTANCE_NAME_GAP_PX,
    LABEL_FONT_PX,
    verify_label_placeholders,
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
from drawio_lib.xml_io import graph_root, xml_attr

STROKE = "#000000"
FILL = "none"
DEFAULT_INSTANCE_GAP = INSTANCE_NAME_GAP_PX
LABEL_INSET_X = 6
ATTR_INSTANCE_NAME = ATTR_NAME
DRAWCLOCK_TYPE_KEY = "drawclockType"


@dataclass
class MuxComponent:
    """One muxN library shape (N = num_inputs)."""

    num_inputs: int
    title: str
    tags: str

    def __post_init__(self) -> None:
        if self.num_inputs < 2:
            raise ValueError(f"mux needs at least 2 inputs, got {self.num_inputs}")
        self._g = geom.compute_geometry(self.num_inputs)
        self._t = self._g.trap

    @property
    def drawclock_type(self) -> str:
        return self.title

    @property
    def w(self) -> int:
        return geom.W

    @property
    def h(self) -> int:
        return self._g.cell_h

    @property
    def g(self) -> geom.MuxGeometry:
        return self._g

    @property
    def trap_x(self) -> int:
        return self._t.x

    @property
    def trap_y(self) -> int:
        return self._t.y

    @property
    def trap_w(self) -> int:
        return self._t.w

    @property
    def trap_h(self) -> int:
        return self._t.h

    @property
    def mux_body_h(self) -> int:
        return self._g.mux_h

    @property
    def edit_data_attr_prefix(self) -> tuple[str, ...]:
        return (ATTR_NAME, "label")

    @property
    def required_object_attrs(self) -> tuple[str, ...]:
        return (ATTR_NAME,)

    def label_html(self) -> str:
        poly = geom.trapezoid_cell_points(self._t)
        body = (
            f'<polygon points="{poly}" fill="{FILL}" stroke="{STROKE}" '
            f'stroke-width="2"/>'
        )
        label_x = self._t.x + LABEL_INSET_X
        in_overlays = tuple(
            (label_x, port.trap.cell_y, str(i))
            for i, port in enumerate(self._g.inputs)
        )
        name_top = self._g.mux_h + geom.MUX_BODY_PAD_BOTTOM
        return (
            f"{shell_open(self.w, self.h)}"
            f"{stretch_body_layer(body, view_w=self.w, view_h=self.h, overlays=in_overlays)}"
            f"{name_block(name_top, design_cell_h=self.h, gap_px=INSTANCE_NAME_GAP_PX)}"
            f"{shell_close()}"
        )

    def preview_svg(self) -> str:
        poly = geom.trapezoid_cell_points(self._t)
        lx = self._t.x + LABEL_INSET_X
        name_y = self._g.mux_h + DEFAULT_INSTANCE_GAP
        stub_lines = []
        for port, color in (
            *[(p, "#c00") for p in self._g.inputs],
            (self._g.out, "#090"),
        ):
            stub_lines.append(
                f'  <line x1="{port.stub_x1}" y1="{port.stub_y1}" '
                f'x2="{port.stub_x2}" y2="{port.stub_y2}" stroke="{color}" '
                f'stroke-width="1"/>'
            )
            stub_lines.append(
                f'  <circle cx="{port.trap.cell_x}" cy="{port.trap.cell_y}" '
                f'r="2.5" fill="{color}"/>'
            )
        stubs = "\n".join(stub_lines)
        texts = []
        for i, port in enumerate(self._g.inputs):
            texts.append(
                f'  <text x="{lx}" y="{port.trap.cell_y}" '
                f'font-size="{LABEL_FONT_PX}" fill="{STROKE}">'
                f"{i}</text>"
            )
        text_block = "\n".join(texts)
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">
  <polygon points="{poly}" fill="{FILL}" stroke="{STROKE}" stroke-width="2"/>
{stubs}
{text_block}
  <text x="{self.w // 2}" y="{name_y + 12}" font-size="{LABEL_FONT_PX}" fill="{STROKE}"
    text-anchor="middle" dominant-baseline="middle">{self.title}</text>
</svg>
"""

    def cell_style(self) -> str:
        bare = [geom.port_drawio_point(p) for p in (*self._g.inputs, self._g.out)]
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
            raise ValueError(f"{self.title} style: missing points=[[...]]")
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
        g = geom.compute_geometry(self.num_inputs)
        if g.cell_h != self._g.cell_h:
            raise ValueError(f"{self.title} geometry cache out of sync")

        poly = geom.trapezoid_cell_points(g.trap)
        parts = [tuple(map(float, p.split(","))) for p in poly.split()]
        left_top, left_bot, right_bot, right_top = parts
        if left_bot[1] - left_top[1] <= right_bot[1] - right_top[1]:
            raise ValueError(f"{self.title} trapezoid: left edge must be longer than right")

        th = g.trap.h
        if th / g.trap.w < 1.2:
            raise ValueError(f"{self.title} trapezoid: too flat")

        fracs = geom.input_fractions(self.num_inputs)
        for i, (port, frac) in enumerate(zip(g.inputs, fracs)):
            which = f"in{i}"
            if port.trap.trap_x != 0.0:
                raise ValueError(f"{which}: trap_x must be 0 on left edge")
            if not isclose(port.trap.trap_y, th * frac, abs_tol=0.01):
                raise ValueError(f"{which}: trap_y must be at fraction {frac}")

        out = g.out.trap
        if out.trap_x != float(g.trap.w):
            raise ValueError(f"output trap_x must be {g.trap.w}")
        mid = (
            geom.trap_right_top_y(th) + geom.trap_right_bot_y(th)
        ) / 2
        if not isclose(out.trap_y, mid, abs_tol=0.51):
            raise ValueError(f"output trap_y must be right-edge mid {mid}")

        for i in range(len(g.inputs) - 1):
            if g.inputs[i].trap.cell_y >= g.inputs[i + 1].trap.cell_y:
                raise ValueError(f"in{i} must be above in{i + 1}")

        html = self.label_html()
        verify_label_placeholders(html, title=self.title)
        if f'viewBox="0 0 {self.w} {self.h}"' not in html:
            raise ValueError(f"{self.title} label must use cell viewBox")
        if 'preserveAspectRatio="none"' not in html:
            raise ValueError(f"{self.title} body SVG must stretch with the shape (none)")
        if "<line " in html:
            raise ValueError(f"{self.title} label must not draw port stub lines")
        if "in0_label" in html:
            raise ValueError(f"{self.title} input labels must be fixed text")
        style = self.cell_style()
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
        expected = len(g.inputs) + 1
        if len(pts) != expected:
            raise ValueError(f"{self.title} expects {expected} connection points, got {pts}")
        for pt, port, which in zip(
            pts,
            (*g.inputs, g.out),
            [*(f"in{i}" for i in range(self.num_inputs)), "out"],
        ):
            if len(pt) != 5 or pt[2] != float(geom.POINT_FIXED):
                raise ValueError(f"{which}: must use 5-value points [x,y,0,0,0]")
            if not isclose(pt[0], port.trap.x_rel, abs_tol=0.002):
                raise ValueError(f"{which} trap rel_x mismatch")
            if not isclose(pt[1], port.trap.y_rel, abs_tol=0.002):
                raise ValueError(f"{which} trap rel_y mismatch")

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
            keys = list(obj.attrib.keys())
            if keys[: len(self.edit_data_attr_prefix)] != list(
                self.edit_data_attr_prefix
            ):
                raise ValueError(
                    f"{self.title} edit-data attribute order must start with "
                    f"{list(self.edit_data_attr_prefix)}, got "
                    f"{keys[: len(self.edit_data_attr_prefix)]}"
                )
            mxcell = obj.find("mxCell")
            assert mxcell is not None
            style = mxcell.get("style") or ""
            if f"{DRAWCLOCK_TYPE_KEY}={self.drawclock_type}" not in style:
                raise ValueError(
                    f"{self.title} library XML: mxCell style must include "
                    f"{DRAWCLOCK_TYPE_KEY}={self.drawclock_type}"
                )
            pts = self._parse_points(style)
            if not isclose(pts[-1][0], self._g.out.trap.x_rel, abs_tol=0.002):
                raise ValueError(f"{self.title} library XML: output trap point X wrong")
            break
        else:
            raise ValueError(f"{self.title} library: missing object wrapper")


def bind_module(module: object, component: MuxComponent) -> None:
    """Expose component API on a per-muxN module (mux2.py, mux3.py, …)."""
    g = component.g
    mapping = {
        "TITLE": component.title,
        "TAGS": component.tags,
        "W": component.w,
        "H": component.h,
        "G": g,
        "TRAP_X": component.trap_x,
        "TRAP_Y": component.trap_y,
        "TRAP_W": component.trap_w,
        "TRAP_H": component.trap_h,
        "MUX_H": component.mux_body_h,
        "DEFAULT_INSTANCE_GAP": DEFAULT_INSTANCE_GAP,
        "LABEL_INSET_X": LABEL_INSET_X,
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
