from __future__ import annotations

from drawio_layout import EdgeLayout, LayoutDocument, VertexLayout
from drawio_library import (
    LABEL_PLACEHOLDER_RE,
    bake_label_placeholders,
    canonical_object_attrs,
    canonical_vertex_style,
)
from drawio_ports import resolve_edge_style


def xml_attr(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_drawio_xml(layout: LayoutDocument) -> str:
    lines = [
        "<mxfile>",
        "  <diagram>",
        "    <mxGraphModel>",
        "      <root>",
        '        <mxCell id="0"/>',
        '        <mxCell id="1" parent="0"/>',
    ]
    by_id = {vertex.cell_id: vertex for vertex in layout.vertices}
    for vertex in layout.vertices:
        lines.append("        " + _vertex_xml(vertex))
    for edge in layout.edges:
        lines.append("        " + _edge_xml(edge, by_id))
    lines.extend(
        [
            "      </root>",
            "    </mxGraphModel>",
            "  </diagram>",
            "</mxfile>",
        ]
    )
    return "\n".join(lines) + "\n"


def _vertex_xml(vertex: VertexLayout) -> str:
    attrs = dict(vertex.object_attrs)
    attrs["name"] = vertex.name
    attrs = canonical_object_attrs(vertex.drawclock_type, attrs)
    label = attrs.get("label", "")
    if label and LABEL_PLACEHOLDER_RE.search(label):
        attrs["label"] = bake_label_placeholders(label, attrs)
    if attrs.get("label") and not LABEL_PLACEHOLDER_RE.search(attrs["label"]):
        attrs["placeholders"] = "0"
    elif "placeholders" not in attrs:
        attrs["placeholders"] = "1"
    attrs["id"] = vertex.cell_id
    attr_order = ["name", "label", "placeholders", "id"]
    remaining = [k for k in sorted(attrs) if k not in attr_order]
    ordered_keys = [k for k in attr_order if k in attrs] + remaining
    attr_parts = [f'{key}="{xml_attr(attrs[key])}"' for key in ordered_keys]
    geom = (
        f'<mxGeometry x="{_fmt(vertex.x)}" y="{_fmt(vertex.y)}" '
        f'width="{_fmt(vertex.width)}" height="{_fmt(vertex.height)}" as="geometry"/>'
    )
    style_raw = canonical_vertex_style(vertex.drawclock_type, vertex.style)
    if attrs.get("placeholders") == "0":
        style_raw = style_raw.replace("placeholders=1;", "placeholders=0;")
    style = xml_attr(style_raw)
    return (
        f"<object {' '.join(attr_parts)}>"
        f'<mxCell style="{style}" vertex="1" parent="1">'
        f"{geom}"
        "</mxCell>"
        "</object>"
    )


def _edge_xml(edge: EdgeLayout, by_id: dict[str, VertexLayout]) -> str:
    src = by_id.get(edge.source_id)
    tgt = by_id.get(edge.target_id)
    if src is not None and tgt is not None:
        style_raw = resolve_edge_style(
            src.style,
            src.drawclock_type,
            tgt.style,
            tgt.drawclock_type,
            edge.style,
        )
    else:
        style_raw = edge.style
    style = xml_attr(style_raw)
    rel = "1" if edge.relative else "0"
    geom_inner = ""
    if edge.waypoints:
        points = "".join(
            f'<mxPoint x="{_fmt(x)}" y="{_fmt(y)}" as="point"/>' for x, y in edge.waypoints
        )
        geom_inner = f"<Array as=\"points\">{points}</Array>"
    geom = f'<mxGeometry relative="{rel}" as="geometry">{geom_inner}</mxGeometry>'
    return (
        f'<mxCell id="{xml_attr(edge.cell_id)}" style="{style}" edge="1" parent="1" '
        f'source="{xml_attr(edge.source_id)}" target="{xml_attr(edge.target_id)}">'
        f"{geom}"
        "</mxCell>"
    )


def _fmt(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)
