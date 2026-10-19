from __future__ import annotations

import json
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from elk_layout import generate_elk_layout
from layout_preview import build_preview_svg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import svg_quality_system as quality
from run_frozen_example import _assert_data_table

NS = {"s": "http://www.w3.org/2000/svg"}


@pytest.mark.parametrize("mutation", [None, "value", "column", "index"])
def test_array_quality_reads_actual_multiline_values_and_rejects_corruption(tmp_path, mutation):
    config = {"root\nlong": {"kind": "gate"},
              "sink": {"kind": "clock", "source": "rootlong", "table_values": ["100\nMHz", "50", "10", "1"]}}
    source = tmp_path / "input.json"
    source.write_text(json.dumps(config), encoding="utf8")
    document, _ = generate_elk_layout(config, library_path=ROOT / "drawio-lib/drawclock")
    svg = ET.fromstring(build_preview_svg(document))
    table = svg.find("s:g[@class='data-table']", NS)
    if mutation == "value":
        table.find("s:text[@class='table-value']/s:tspan", NS).text = "999"
    elif mutation == "column":
        table.remove(table.findall("s:text[@class='table-heading']", NS)[-1])
    elif mutation == "index":
        table.find("s:text[@class='table-value']", NS).set("data-table-field", "table_values[2]")
    output = tmp_path / "output.svg"
    ET.ElementTree(svg).write(output, encoding="utf-8")
    failures = quality._artifact_metric_witnesses(source, output)["frequency_column_visibility"]
    assert bool(failures) == (mutation is not None), failures
    if mutation is None:
        _assert_data_table(output, source)
    else:
        with pytest.raises(SystemExit):
            _assert_data_table(output, source)


def test_empty_array_next_to_unconfigured_terminal_does_not_invent_legacy_columns(tmp_path):
    config = {"root": {"kind": "gate"},
              "a": {"kind": "clock", "source": "root", "table_values": []},
              "b": {"kind": "clock", "source": "root"}}
    source = tmp_path / "input.json"
    source.write_text(json.dumps(config), encoding="utf8")
    document, _ = generate_elk_layout(config, library_path=ROOT / "drawio-lib/drawclock")
    output = tmp_path / "output.svg"
    output.write_text(build_preview_svg(document), encoding="utf8")
    assert not quality._artifact_metric_witnesses(source, output)["frequency_column_visibility"]
    _assert_data_table(output, source)
