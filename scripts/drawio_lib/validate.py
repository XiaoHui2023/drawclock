from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from drawio_lib.xml_io import decompress_drawio_xml, graph_root


def validate_drawio_graph_xml(xml_str: str, *, context: str = "") -> None:
    """Fail if XML is ill-formed or breaks draw.io library import rules."""
    prefix = f"{context}: " if context else ""
    if re.search(r'\slabel="[^"]*<', xml_str):
        raise ValueError(
            f"{prefix}outer <object> label must be XML-escaped "
            "(raw < in attribute)"
        )
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as exc:
        raise ValueError(f"{prefix}invalid XML: {exc}") from exc

    graph = graph_root(root)

    seen: Counter[str] = Counter()
    for elem in graph.iter():
        elem_id = elem.get("id")
        if elem_id is not None:
            seen[elem_id] += 1
    duplicates = sorted(eid for eid, count in seen.items() if count > 1)
    if duplicates:
        raise ValueError(f"{prefix}duplicate ID(s): {', '.join(duplicates)}")

    for mxcell in graph.iter("mxCell"):
        nested_objects = [child for child in mxcell if child.tag == "object"]
        if nested_objects:
            raise ValueError(
                f"{prefix}mxCell must not contain child <object> "
                "(draw.io: could not add object for object)"
            )

    wrappers = [obj for obj in graph.iter("object") if obj.find("mxCell") is not None]
    for wrapper in wrappers:
        if not wrapper.get("id"):
            raise ValueError(f"{prefix}outer <object> wrapper must have id")
        if wrapper.get("placeholders") != "1":
            raise ValueError(f'{prefix}outer <object> must have placeholders="1"')
        mxcell = wrapper.find("mxCell")
        assert mxcell is not None
        if mxcell.get("id") is not None:
            raise ValueError(
                f"{prefix}mxCell inside object wrapper must not have id "
                "(duplicate ID)"
            )
        if mxcell.get("value") and "%" in (mxcell.get("value") or ""):
            raise ValueError(
                f"{prefix}use outer object label for placeholders, not mxCell value"
            )


def validate_mxlibrary_file(path: Path) -> None:
    raw = path.read_text(encoding="utf-8")
    match = re.search(r"<mxlibrary>(.*)</mxlibrary>", raw, re.DOTALL)
    if not match:
        raise ValueError(f"{path}: missing <mxlibrary> wrapper")
    try:
        entries = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON in mxlibrary: {exc}") from exc
    if not entries:
        raise ValueError(f"{path}: empty library")
    for index, entry in enumerate(entries):
        title = entry.get("title", f"entry[{index}]")
        for key in ("xml", "w", "h"):
            if key not in entry:
                raise ValueError(f"{path} entry {title}: missing {key}")
        graph_xml = decompress_drawio_xml(entry["xml"])
        validate_drawio_graph_xml(graph_xml, context=title)


def validate_drawio_file(path: Path) -> None:
    raw = path.read_text(encoding="utf-8")
    for match in re.finditer(
        r"<mxGraphModel[^>]*>(.*?)</mxGraphModel>", raw, re.DOTALL
    ):
        validate_drawio_graph_xml(
            f"<mxGraphModel>{match.group(1)}</mxGraphModel>",
            context=path.name,
        )
