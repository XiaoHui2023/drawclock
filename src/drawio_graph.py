from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from internal_kind import INTERNAL_OBJECT_KEYS, STYLE_KEY_TO_JSON

DRAWCLOCK_TYPE_RE = re.compile(r"drawclockType=([^;]+)")
STYLE_XY_RE = re.compile(r"(exit|entry)(X|Y)=([0-9.]+)")
STYLE_KV_RE = re.compile(r"(?:^|;)([^=;]+)=([^;]*)")


@dataclass
class GraphCell:
    cell_id: str
    is_edge: bool
    style: str = ""
    source_id: str | None = None
    target_id: str | None = None
    drawclock_type: str | None = None
    name: str = ""
    pll_kind: str | None = None
    mux_labels: dict[str, str] = field(default_factory=dict)
    points: tuple[tuple[float, float], ...] = ()
    object_attrs: dict[str, str] = field(default_factory=dict)
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    edge_relative: bool = True
    edge_waypoints: tuple[tuple[float, float], ...] = ()


@dataclass
class ParsedDiagram:
    cells: dict[str, GraphCell]
    cell_sources: dict[str, Path] = field(default_factory=dict)


def parse_models(models: list[ET.Element], *, id_prefix: str = "") -> ParsedDiagram:
    cells: dict[str, GraphCell] = {}
    for model in models:
        root_el = model.find("root")
        if root_el is None:
            continue
        _collect_cells(root_el, cells, id_prefix=id_prefix)
    return ParsedDiagram(cells=cells)


def merge_diagrams(parts: list[ParsedDiagram]) -> ParsedDiagram:
    merged: dict[str, GraphCell] = {}
    sources: dict[str, Path] = {}
    for part in parts:
        merged.update(part.cells)
        sources.update(part.cell_sources)
    return ParsedDiagram(cells=merged, cell_sources=sources)


def is_library_cell(cell: GraphCell) -> bool:
    """True for drawclock library vertices; doodles and edges are False."""
    return not cell.is_edge and bool(cell.drawclock_type)


def validate_diagram_library(diagram: ParsedDiagram, library_path: str | Path) -> None:
    from drawio_library import load_library_titles, unknown_library_vertex_message

    known = load_library_titles(library_path)
    unknown: list[tuple[str, str]] = []
    for cell in diagram.cells.values():
        if cell.is_edge or not cell.drawclock_type or cell.drawclock_type in known:
            continue
        name = (cell.name or cell.drawclock_type).strip()
        unknown.append((name, cell.drawclock_type))
    if unknown:
        raise ValueError(unknown_library_vertex_message(unknown, reload=False))


def _collect_cells(root_el: ET.Element, out: dict[str, GraphCell], *, id_prefix: str) -> None:
    for child in root_el:
        if child.tag == "object":
            _add_vertex_from_object(child, out, id_prefix=id_prefix)
        elif child.tag == "mxCell":
            _add_mxcell(child, out, id_prefix=id_prefix, attrs={})


def _add_vertex_from_object(obj: ET.Element, out: dict[str, GraphCell], *, id_prefix: str) -> None:
    attrs = dict(obj.attrib)
    obj_id = attrs.pop("id", None)
    mxcell = obj.find("mxCell")
    if mxcell is None:
        return
    cell_id = obj_id or mxcell.get("id")
    if not cell_id:
        return
    _add_mxcell(mxcell, out, id_prefix=id_prefix, attrs=attrs, forced_id=cell_id)


def _add_mxcell(
    mxcell: ET.Element,
    out: dict[str, GraphCell],
    *,
    id_prefix: str,
    attrs: dict[str, str],
    forced_id: str | None = None,
) -> None:
    raw_id = forced_id or mxcell.get("id")
    if not raw_id:
        return
    cell_id = f"{id_prefix}{raw_id}"
    style = mxcell.get("style") or ""
    if mxcell.get("edge") == "1":
        rel, waypoints = _parse_edge_geometry(mxcell)
        out[cell_id] = GraphCell(
            cell_id=cell_id,
            is_edge=True,
            style=style,
            source_id=_prefixed(mxcell.get("source"), id_prefix),
            target_id=_prefixed(mxcell.get("target"), id_prefix),
            edge_relative=rel,
            edge_waypoints=waypoints,
        )
        return
    if mxcell.get("vertex") != "1":
        return
    dtype = _style_value(style, DRAWCLOCK_TYPE_RE)
    merged = {**attrs, **mxcell.attrib}
    if not dtype:
        gx, gy, gw, gh = _parse_vertex_geometry(mxcell)
        out[cell_id] = GraphCell(
            cell_id=cell_id,
            is_edge=False,
            style=style,
            drawclock_type=None,
            name=_doodle_label(merged),
            x=gx,
            y=gy,
            width=gw,
            height=gh,
        )
        return
    internal_from_style = _internal_attrs_from_style(style)
    for key in INTERNAL_OBJECT_KEYS:
        legacy = attrs.get(key)
        if key not in internal_from_style and legacy is not None and str(legacy).strip():
            internal_from_style[key] = str(legacy).strip()
    object_attrs = {
        key: value
        for key, value in attrs.items()
        if key not in ("id",) and value is not None and key not in INTERNAL_OBJECT_KEYS
    }
    object_attrs.update(internal_from_style)
    gx, gy, gw, gh = _parse_vertex_geometry(mxcell)
    name = merged.get("name", merged.get("_name", "")).strip()
    pll_kind = merged.get("pll_kind")
    if pll_kind is not None:
        pll_kind = pll_kind.strip() or None
    mux_labels = {
        key: merged[key].strip()
        for key in sorted(merged)
        if key.startswith("in") and key.endswith("_label") and merged[key].strip()
    }
    out[cell_id] = GraphCell(
        cell_id=cell_id,
        is_edge=False,
        style=style,
        drawclock_type=dtype,
        name=name or dtype,
        pll_kind=pll_kind,
        mux_labels=mux_labels,
        points=_parse_points(style),
        object_attrs=object_attrs,
        x=gx,
        y=gy,
        width=gw,
        height=gh,
    )



def _parse_vertex_geometry(mxcell: ET.Element) -> tuple[float | None, float | None, float | None, float | None]:
    geom = mxcell.find("mxGeometry")
    if geom is None:
        return None, None, None, None

    def _float(key: str) -> float | None:
        raw = geom.get(key)
        return float(raw) if raw is not None else None

    return _float("x"), _float("y"), _float("width"), _float("height")


def _parse_edge_geometry(mxcell: ET.Element) -> tuple[bool, tuple[tuple[float, float], ...]]:
    geom = mxcell.find("mxGeometry")
    if geom is None:
        return True, ()
    relative = geom.get("relative", "1") != "0"
    waypoints: list[tuple[float, float]] = []
    array = geom.find("Array")
    if array is not None:
        for point in array.findall("mxPoint"):
            x_raw = point.get("x")
            y_raw = point.get("y")
            if x_raw is None or y_raw is None:
                continue
            waypoints.append((float(x_raw), float(y_raw)))
    return relative, tuple(waypoints)


def _prefixed(cell_id: str | None, prefix: str) -> str | None:
    if not cell_id:
        return None
    return f"{prefix}{cell_id}"


def _doodle_label(merged: dict[str, str]) -> str:
    for key in ("name", "_name", "value", "label"):
        raw = merged.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return ""


def _style_value(style: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(style)
    return match.group(1) if match else None


def _internal_attrs_from_style(style: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for style_key, json_key in STYLE_KEY_TO_JSON.items():
        value = _style_value(style, re.compile(rf"{re.escape(style_key)}=([^;]+)"))
        if value:
            out[json_key] = value.strip()
    return out


def _parse_points(style: str) -> tuple[tuple[float, float], ...]:
    marker = "points=[["
    start = style.find(marker)
    if start < 0:
        return ()
    start += len(marker)
    end = style.find("]]", start)
    if end < 0:
        return ()
    inner = style[start:end].strip()
    if not inner:
        return ()
    coords: list[tuple[float, float]] = []
    for segment in inner.split("],["):
        parts = [p.strip() for p in segment.split(",")]
        if len(parts) < 2:
            continue
        coords.append((float(parts[0]), float(parts[1])))
    return tuple(coords)


def edge_style_value(style: str, key: str, *, default: str | None = None) -> str | None:
    normalized = style.strip()
    if not normalized:
        return default
    for match in STYLE_KV_RE.finditer(f";{normalized}"):
        if match.group(1) == key:
            return match.group(2)
    return default


def edge_is_undirected(style: str) -> bool:
    """True when both ends have no arrow (draw.io default end arrow counts as directed)."""
    start = edge_style_value(style, "startArrow", default="none")
    end = edge_style_value(style, "endArrow", default="classic")
    return start == "none" and end == "none"


def edge_attachment(style: str, *, end: str) -> tuple[float, float] | None:
    prefix = "exit" if end == "exit" else "entry"
    x = y = None
    for kind, axis, value in STYLE_XY_RE.findall(style):
        if kind != prefix:
            continue
        if axis == "X":
            x = float(value)
        else:
            y = float(value)
    if x is None or y is None:
        return None
    return (x, y)
