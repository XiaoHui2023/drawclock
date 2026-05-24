from __future__ import annotations

import importlib.util
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


def test_generated_library_passes_validation() -> None:
    _build.verify_outputs()


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
