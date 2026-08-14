from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


LAYOUT_VERSION = 1
CROSSING_STYLES = ("arc", "gap", "sharp", "none")


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
    logical_name: str | None = None


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


def apply_crossing_style(document: LayoutDocument, crossing_style: str) -> None:
    """Apply one draw.io line-jump policy without changing route coordinates."""
    if crossing_style not in CROSSING_STYLES:
        raise ValueError(f"unsupported crossing style: {crossing_style}")
    for edge in document.edges:
        parts = [
            part
            for part in edge.style.split(";")
            if part and not part.startswith(("jumpStyle=", "jumpSize="))
        ]
        if crossing_style != "none":
            parts.extend((f"jumpStyle={crossing_style}", "jumpSize=6"))
        edge.style = ";".join(parts) + ";"


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
                **({"logical_name": vertex.logical_name} if vertex.logical_name else {}),
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
                logical_name=(
                    str(raw["logical_name"])
                    if raw.get("logical_name") is not None
                    else None
                ),
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
