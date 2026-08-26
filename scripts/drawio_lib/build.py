from __future__ import annotations

import json
import sys

from drawio_lib.components.registry import (
    ALL,
    library_entry,
    verify_geometry,
    write_image_outputs,
)
from drawio_lib.paths import IMAGES_DIR, LIBRARY_DIR
from drawio_lib.validate import validate_mxlibrary_file
from drawio_lib.xml_io import decompress_drawio_xml


def build_library() -> None:
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    expected: set[str] = set()
    for spec in ALL:
        entry = library_entry(spec)
        title = str(entry["title"])
        filename = f"{title}.xml"
        expected.add(filename.casefold())
        content = (
            "<mxlibrary>"
            + json.dumps([entry], ensure_ascii=False)
            + "</mxlibrary>\n"
        )
        (LIBRARY_DIR / filename).write_text(content, encoding="utf-8")
    for path in LIBRARY_DIR.glob("*.xml"):
        if path.name.casefold() not in expected:
            path.unlink()


def build_images() -> None:
    for spec in ALL:
        write_image_outputs(spec, IMAGES_DIR)


def verify_outputs() -> None:
    import re

    for spec in ALL:
        verify_geometry(spec)

    titles = {spec.module.TITLE: spec.module for spec in ALL}
    library_files = sorted(LIBRARY_DIR.glob("*.xml"), key=lambda path: path.name.casefold())
    if len(library_files) != len(ALL):
        raise ValueError(
            f"expected {len(ALL)} component files, found {len(library_files)}"
        )
    for path in library_files:
        validate_mxlibrary_file(path)
        raw = path.read_text(encoding="utf-8")
        match = re.search(r"<mxlibrary>(.*)</mxlibrary>", raw, re.DOTALL)
        assert match
        entry = json.loads(match.group(1))[0]
        title = entry["title"]
        graph_xml = decompress_drawio_xml(entry["xml"])
        mod = titles.get(title)
        if mod is None:
            raise ValueError(f"unexpected component title {title}: {path}")
        mod.verify_library_graph(graph_xml)

    print("check OK: XML valid, draw.io library rules passed, component geometry verified")


def main() -> None:
    build_library()
    build_images()
    for spec in ALL:
        print(f"wrote drawio-lib/drawclock/{spec.module.TITLE}.xml")
    for spec in ALL:
        if hasattr(spec.module, "preview_svg"):
            print(f"wrote drawio-lib/images/{spec.module.TITLE}.svg")
    try:
        verify_outputs()
    except ValueError as exc:
        print(f"check FAILED: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
