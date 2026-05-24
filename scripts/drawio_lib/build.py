from __future__ import annotations

import json
import sys

from drawio_lib.components.registry import (
    ALL,
    library_entry,
    verify_geometry,
    write_image_outputs,
)
from drawio_lib.paths import IMAGES_DIR, LIBRARY_FILE, LIB_DIR
from drawio_lib.validate import validate_mxlibrary_file
from drawio_lib.xml_io import decompress_drawio_xml


def build_library() -> None:
    entries = [library_entry(spec) for spec in ALL]
    content = f"<mxlibrary>{json.dumps(entries, ensure_ascii=False)}</mxlibrary>\n"
    LIB_DIR.mkdir(parents=True, exist_ok=True)
    LIBRARY_FILE.write_text(content, encoding="utf-8")


def build_images() -> None:
    for spec in ALL:
        write_image_outputs(spec, IMAGES_DIR)


def verify_outputs() -> None:
    import re

    for spec in ALL:
        verify_geometry(spec)

    validate_mxlibrary_file(LIBRARY_FILE)

    raw = LIBRARY_FILE.read_text(encoding="utf-8")
    match = re.search(r"<mxlibrary>(.*)</mxlibrary>", raw, re.DOTALL)
    assert match
    titles = {spec.module.TITLE: spec.module for spec in ALL}
    for index, entry in enumerate(json.loads(match.group(1))):
        title = entry.get("title", f"entry[{index}]")
        graph_xml = decompress_drawio_xml(entry["xml"])
        mod = titles.get(title)
        if mod is not None:
            mod.verify_library_graph(graph_xml)

    print("check OK: XML valid, draw.io library rules passed, component geometry verified")


def main() -> None:
    build_library()
    build_images()
    print(f"wrote {LIBRARY_FILE.relative_to(LIBRARY_FILE.parents[2])}")
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
