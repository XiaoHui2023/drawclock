from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from drawio_decode import (
    compress_diagram_payload,
    decompress_diagram_payload,
    extract_mxfile_xml,
)
from drawio_library import (
    LibraryShape,
    load_library_shapes,
    load_library_titles,
    reload_object_attrs,
)
from drawio_ports import port_anchors, resolve_edge_style

DRAWCLOCK_TYPE_RE = re.compile(r"drawclockType=([^;]+)")
DRAWCLOCK_TYPE_ALIASES = {"clksrc": "source"}


def reload_drawio_file(
    input_path: str | Path,
    library_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Upgrade library styles/labels and default cell size; preserve position (x,y) and non-library cells."""
    lib = Path(library_path)
    inp = Path(input_path)
    out = Path(output_path)
    mxfile = extract_mxfile_xml(str(inp))
    migrated = migrate_mxfile_xml(mxfile, lib)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(migrated, encoding="utf-8")
    return out


def migrate_mxfile_xml(mxfile_xml: str, library_path: str | Path) -> str:
    root = ET.fromstring(mxfile_xml)
    shapes = load_library_shapes(library_path)
    known = load_library_titles(library_path)
    for diagram in root.findall("diagram"):
        was_compressed = False
        model = diagram.find("mxGraphModel")
        if model is None:
            payload = (diagram.text or "").strip()
            if not payload:
                continue
            if not payload.startswith("<"):
                was_compressed = True
                try:
                    payload = decompress_diagram_payload(payload)
                except Exception as exc:
                    raise ValueError(
                        "无法解压 diagram 内容；"
                        "请确认文件为 draw.io 导出的 .drawio / .drawio.svg"
                    ) from exc
            model = ET.fromstring(payload)
            diagram.text = None
            diagram.append(model)
        root_el = model.find("root")
        if root_el is None:
            continue
        _migrate_root(root_el, shapes, known, library_path)
        if was_compressed:
            model_xml = ET.tostring(model, encoding="unicode")
            diagram.remove(model)
            diagram.text = compress_diagram_payload(model_xml)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode") + "\n"


def _migrate_root(
    root_el: ET.Element,
    shapes: dict,
    known: set[str],
    library_path: str | Path,
) -> None:
    id_to_vertex: dict[str, tuple[str, str]] = {}

    for child in list(root_el):
        parsed = _parse_library_vertex(child)
        if parsed is None:
            continue
        cell_id, dtype, obj, mxcell = parsed
        dtype = DRAWCLOCK_TYPE_ALIASES.get(dtype, dtype)
        if dtype not in known:
            raise ValueError(f"图中器件类型不在新器件库中: {dtype}")
        _upgrade_library_vertex(obj, mxcell, dtype, shapes[dtype], library_path)
        id_to_vertex[cell_id] = (dtype, mxcell.get("style") or "")

    for child in list(root_el):
        if child.tag != "mxCell" or child.get("edge") != "1":
            continue
        src_id = child.get("source")
        tgt_id = child.get("target")
        if not src_id or not tgt_id:
            continue
        if src_id not in id_to_vertex or tgt_id not in id_to_vertex:
            continue
        src_type, src_style = id_to_vertex[src_id]
        tgt_type, tgt_style = id_to_vertex[tgt_id]
        child.set(
            "style",
            resolve_edge_style(
                src_style,
                src_type,
                tgt_style,
                tgt_type,
                child.get("style") or "",
            ),
        )


def _parse_library_vertex(
    child: ET.Element,
) -> tuple[str, str, ET.Element, ET.Element] | None:
    if child.tag == "object":
        obj = child
        mxcell = obj.find("mxCell")
        if mxcell is None or mxcell.get("vertex") != "1":
            return None
        dtype = _style_dtype(mxcell.get("style") or "")
        if not dtype:
            return None
        cell_id = obj.get("id") or mxcell.get("id")
        if not cell_id:
            return None
        return cell_id, dtype, obj, mxcell
    if child.tag == "mxCell" and child.get("vertex") == "1":
        dtype = _style_dtype(child.get("style") or "")
        if not dtype:
            return None
        cell_id = child.get("id")
        if not cell_id:
            return None
        return cell_id, dtype, child, child
    return None


def _upgrade_library_vertex(
    obj: ET.Element,
    mxcell: ET.Element,
    dtype: str,
    shape: LibraryShape,
    library_path: str | Path,
) -> None:
    _apply_library_geometry(mxcell, shape)
    if obj is mxcell:
        mxcell.set("style", shape.style)
        return
    attrs = {key: obj.get(key) for key in obj.attrib if obj.get(key) is not None}
    if "name" not in attrs and attrs.get("_name"):
        attrs["name"] = attrs["_name"]
    canonical = reload_object_attrs(dtype, attrs, library_path=library_path)
    mxcell.set("style", shape.style)
    for key in ("label", "placeholders"):
        if key in obj.attrib:
            del obj.attrib[key]
    for key, value in canonical.items():
        if key == "id":
            continue
        obj.set(key, value)


def _apply_library_geometry(mxcell: ET.Element, shape: LibraryShape) -> None:
    geom = mxcell.find("mxGeometry")
    if geom is None:
        geom = ET.SubElement(mxcell, "mxGeometry")
        geom.set("as", "geometry")
    if geom.get("x") is None:
        geom.set("x", "0")
    if geom.get("y") is None:
        geom.set("y", "0")
    geom.set("width", str(shape.w))
    geom.set("height", str(shape.h))


def _style_dtype(style: str) -> str | None:
    match = DRAWCLOCK_TYPE_RE.search(style)
    return match.group(1) if match else None
