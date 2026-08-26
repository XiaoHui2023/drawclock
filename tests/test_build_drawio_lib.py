from __future__ import annotations

import importlib.util
import json
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "build_drawio_lib",
    ROOT / "scripts" / "build_drawio_lib.py",
)
_build = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_build)

from drawio_lib.components.registry import ALL
from drawio_lib.validate import validate_mxlibrary_file


LIBRARY_DIR = ROOT / "drawio-lib" / "drawclock"


def test_generated_library_passes_validation() -> None:
    _build.verify_outputs()


def test_generated_library_has_exactly_one_file_and_entry_per_component() -> None:
    files = sorted(LIBRARY_DIR.glob("*.xml"))
    expected_titles = {spec.module.TITLE for spec in ALL}
    assert len(files) == len(expected_titles)
    actual_titles: set[str] = set()
    for path in files:
        text = path.read_text(encoding="utf-8").strip()
        assert text.startswith("<mxlibrary>")
        assert text.endswith("</mxlibrary>")
        entries = json.loads(text[len("<mxlibrary>") : -len("</mxlibrary>")])
        assert len(entries) == 1
        actual_titles.add(entries[0]["title"])
    assert actual_titles == expected_titles


@pytest.mark.parametrize("entry_count", [0, 2])
def test_validate_rejects_non_single_component_library(
    tmp_path: Path, entry_count: int,
) -> None:
    source = LIBRARY_DIR / "source.xml"
    text = source.read_text(encoding="utf-8").strip()
    entry = json.loads(text[len("<mxlibrary>") : -len("</mxlibrary>")])[0]
    path = tmp_path / "invalid.xml"
    path.write_text(
        "<mxlibrary>" + json.dumps([entry] * entry_count) + "</mxlibrary>",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="empty library|exactly one component"):
        validate_mxlibrary_file(path)


def test_validate_rejects_duplicate_id() -> None:
    bad = (
        "<mxGraphModel><root>"
        '<mxCell id="0"/><mxCell id="1" parent="0"/>'
        '<object id="2" label="x">'
        '<mxCell id="2" vertex="1" parent="1">'
        '<mxGeometry width="10" height="10" as="geometry"/>'
        "</mxCell></object>"
        "</root></mxGraphModel>"
    )
    with pytest.raises(ValueError, match="duplicate ID"):
        _build.validate_drawio_graph_xml(bad)


def test_validate_rejects_object_inside_mxcell() -> None:
    bad = (
        "<mxGraphModel><root>"
        '<mxCell id="0"/><mxCell id="1" parent="0"/>'
        '<mxCell id="2" vertex="1" parent="1">'
        '<mxGeometry width="10" height="10" as="geometry"/>'
        '<object label="x" instance_name="a" component_type="mux2" placeholders="1"/>'
        "</mxCell>"
        "</root></mxGraphModel>"
    )
    with pytest.raises(ValueError, match="could not add object for object"):
        _build.validate_drawio_graph_xml(bad)


def test_validate_rejects_unescaped_label() -> None:
    bad = (
        "<mxGraphModel><root>"
        '<mxCell id="0"/><mxCell id="1" parent="0"/>'
        '<object id="2" label="<b>x</b>" instance_name="a" '
        'component_type="mux2" placeholders="1">'
        '<mxCell vertex="1" parent="1">'
        '<mxGeometry width="10" height="10" as="geometry"/>'
        "</mxCell></object>"
        "</root></mxGraphModel>"
    )
    with pytest.raises(ValueError, match="XML-escaped"):
        _build.validate_drawio_graph_xml(bad)
