from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from source_reference import parse_source_ref
from visual_geometry import estimated_label_width, visual_box


ROOT = Path(__file__).resolve().parents[1]
SVG = {"s": "http://www.w3.org/2000/svg"}


@pytest.mark.parametrize("name", ["root\nlong", "root\r\nlong", "root\n中间\n末行"])
def test_multiline_reference_preserves_identity_and_output(name):
    assert parse_source_ref(name) == (name, None)
    assert parse_source_ref(name + "[out]") == (name, "out")


def test_multiline_footprint_uses_widest_line_and_reserves_height():
    label = '<div style="font-size:10px"></div>'
    width = estimated_label_width("longest\nx", label, 10)
    assert width == estimated_label_width("longest", label, 10)
    assert width < estimated_label_width("longestx", label, 10)
    box = visual_box(name="longest\nx", label=label, x=0, y=0, width=10, height=30)
    assert box.bottom == 43


@pytest.mark.parametrize("name", ["root&\nlong<name>", "\nroot&\n\nlong<name>\n"])
def test_public_cli_renders_multiline_name_and_keeps_metadata_identity(tmp_path, name):
    config = {name: {"kind": "gate"}, "sink": {"kind": "clock", "source": name}}
    source = tmp_path / "input.json"
    source.write_text(json.dumps(config), encoding="utf-8")
    output = tmp_path / "result.svg"
    result = subprocess.run(
        [sys.executable, "src", "-i", str(source), "-l", "drawio-lib/drawclock", "-o", str(output)],
        cwd=ROOT, env={**os.environ, "PYTHONUTF8": "1"},
        capture_output=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    document = ET.parse(output).getroot()
    spans = document.findall(".//s:tspan", SVG)
    assert [span.text or "" for span in spans] == name.split("\n")
    assert len({span.get("y") for span in spans}) == len(name.split("\n"))
    assert len({span.get("x") for span in spans}) == 1
    assert float(spans[1].get("y")) - float(spans[0].get("y")) > 12
    assert "foreignObject" not in output.read_text(encoding="utf-8")
    assert any(name == value for element in document.iter() for value in element.attrib.values())
