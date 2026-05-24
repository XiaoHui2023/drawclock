from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from drawio_graph import GraphCell, ParsedDiagram
from drawio_library import canonical_object_attrs, canonical_vertex_style
from drawio_ports import resolve_edge_style

LAYOUT_VERSION = 1


@dataclass
class VertexLayout:
    name: str
    cell_id: str
    drawclock_type: str
    x: float
    y: float
    width: float
    height: float
    style: str
    object_attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class EdgeLayout:
    cell_id: str
    source_id: str
    target_id: str
    style: str
    relative: bool = True
    waypoints: tuple[tuple[float, float], ...] = ()


@dataclass
class LayoutDocument:
    version: int
    vertices: list[VertexLayout]
    edges: list[EdgeLayout]


def layout_from_diagram(diagram: ParsedDiagram) -> LayoutDocument:
    vertices: list[VertexLayout] = []
    edges: list[EdgeLayout] = []
    for cell in diagram.cells.values():
        if cell.is_edge:
            if not cell.source_id or not cell.target_id:
                continue
            edges.append(
                EdgeLayout(
                    cell_id=cell.cell_id,
                    source_id=cell.source_id,
                    target_id=cell.target_id,
                    style=cell.style,
                    relative=cell.edge_relative,
                    waypoints=cell.edge_waypoints,
                )
            )
            continue
        if not cell.drawclock_type:
            continue
        if cell.x is None or cell.y is None or cell.width is None or cell.height is None:
            raise ValueError(f"器件 {cell.name} 缺少 mxGeometry 坐标或尺寸")
        object_attrs = canonical_object_attrs(
            cell.drawclock_type,
            {**dict(cell.object_attrs), "name": cell.name},
        )
        style = canonical_vertex_style(cell.drawclock_type, cell.style)
        if object_attrs.get("placeholders") == "0":
            style = style.replace("placeholders=1;", "placeholders=0;")
        vertices.append(
            VertexLayout(
                name=cell.name,
                cell_id=cell.cell_id,
                drawclock_type=cell.drawclock_type,
                x=cell.x,
                y=cell.y,
                width=cell.width,
                height=cell.height,
                style=style,
                object_attrs=object_attrs,
            )
        )
    vertices.sort(key=lambda item: item.name)
    edges.sort(key=lambda item: item.cell_id)
    by_id = {vertex.cell_id: vertex for vertex in vertices}
    normalized_edges: list[EdgeLayout] = []
    for edge in edges:
        src = by_id.get(edge.source_id)
        tgt = by_id.get(edge.target_id)
        style = edge.style
        if src is not None and tgt is not None:
            style = resolve_edge_style(
                src.style,
                src.drawclock_type,
                tgt.style,
                tgt.drawclock_type,
                edge.style,
            )
        normalized_edges.append(
            EdgeLayout(
                cell_id=edge.cell_id,
                source_id=edge.source_id,
                target_id=edge.target_id,
                style=style,
                relative=edge.relative,
                waypoints=edge.waypoints,
            )
        )
    return LayoutDocument(
        version=LAYOUT_VERSION, vertices=vertices, edges=normalized_edges
    )


def layout_to_dict(doc: LayoutDocument) -> dict[str, Any]:
    return {
        "version": doc.version,
        "vertices": [
            {
                "name": vertex.name,
                "cell_id": vertex.cell_id,
                "drawclock_type": vertex.drawclock_type,
                "x": vertex.x,
                "y": vertex.y,
                "width": vertex.width,
                "height": vertex.height,
                "style": vertex.style,
                "object": vertex.object_attrs,
            }
            for vertex in doc.vertices
        ],
        "edges": [
            {
                "cell_id": edge.cell_id,
                "source": edge.source_id,
                "target": edge.target_id,
                "style": edge.style,
                "relative": edge.relative,
                "waypoints": [list(point) for point in edge.waypoints],
            }
            for edge in doc.edges
        ],
    }


def layout_from_dict(data: dict[str, Any]) -> LayoutDocument:
    version = int(data.get("version", 0))
    if version != LAYOUT_VERSION:
        raise ValueError(f"不支持的布局 JSON 版本: {version}")
    vertices: list[VertexLayout] = []
    for raw in data.get("vertices", []):
        obj = raw.get("object") or {}
        if not isinstance(obj, dict):
            raise ValueError(f"器件 {raw.get('name')} 的 object 必须是对象")
        vertices.append(
            VertexLayout(
                name=str(raw["name"]),
                cell_id=str(raw["cell_id"]),
                drawclock_type=str(raw["drawclock_type"]),
                x=float(raw["x"]),
                y=float(raw["y"]),
                width=float(raw["width"]),
                height=float(raw["height"]),
                style=str(raw.get("style", "")),
                object_attrs={str(k): str(v) for k, v in obj.items()},
            )
        )
    edges: list[EdgeLayout] = []
    for raw in data.get("edges", []):
        way_raw = raw.get("waypoints") or []
        waypoints = tuple(
            (float(point[0]), float(point[1]))
            for point in way_raw
            if isinstance(point, (list, tuple)) and len(point) >= 2
        )
        edges.append(
            EdgeLayout(
                cell_id=str(raw["cell_id"]),
                source_id=str(raw["source"]),
                target_id=str(raw["target"]),
                style=str(raw.get("style", "")),
                relative=bool(raw.get("relative", True)),
                waypoints=waypoints,
            )
        )
    return LayoutDocument(version=version, vertices=vertices, edges=edges)
