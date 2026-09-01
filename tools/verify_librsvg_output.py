from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


SVG_NS = "http://www.w3.org/2000/svg"
HTML_NS = "http://www.w3.org/1999/xhtml"
FORBIDDEN = {"foreignObject", "script", "iframe", "audio", "video", "canvas"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _classes(element: ET.Element) -> set[str]:
    return set(element.get("class", "").split())


def verify_librsvg_output(source_path: Path, flattened_path: Path) -> dict[str, int]:
    source = ET.parse(source_path).getroot()
    flattened = ET.parse(flattened_path).getroot()
    if source.tag != f"{{{SVG_NS}}}svg":
        raise ValueError("source root is not SVG")
    for element in source.iter():
        tag = _local(element.tag)
        if tag in FORBIDDEN or element.tag.startswith(f"{{{HTML_NS}}}"):
            raise ValueError(f"source contains browser-only content: {tag}")
        for raw_key, value in element.attrib.items():
            key = _local(raw_key)
            if key.lower().startswith("on"):
                raise ValueError(f"source contains an event handler: {key}")
            if "url(" in value.lower() or "@import" in value.lower():
                raise ValueError("source contains an external CSS resource")
            if key == "href" and not (value.startswith("#") or value.startswith("data:")):
                raise ValueError("source contains an external resource")
        if tag == "style" and (
            "url(" in (element.text or "").lower()
            or "@import" in (element.text or "").lower()
        ):
            raise ValueError("source contains an external CSS resource")

    components = [element for element in source.iter() if "component" in _classes(element)]
    graphics = [
        element for element in source.iter()
        if _local(element.tag) == "svg" and "component-graphic" in _classes(element)
    ]
    edges = [element for element in source.iter() if "edge" in _classes(element)]
    if not components or len(graphics) != len(components):
        raise ValueError("source does not have exactly one native graphic per component")

    painted_paths = sum(1 for element in flattened.iter() if _local(element.tag) == "path")
    minimum_paths = len(graphics) + len(edges) + 1
    if painted_paths < minimum_paths:
        raise ValueError(
            "librsvg output lost rendered content: "
            f"paths={painted_paths}, minimum={minimum_paths}"
        )
    return {
        "components": len(components),
        "graphics": len(graphics),
        "edges": len(edges),
        "painted_paths": painted_paths,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("flattened", type=Path)
    args = parser.parse_args()
    result = verify_librsvg_output(args.source, args.flattened)
    print(" ".join(f"{key}={value}" for key, value in result.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
