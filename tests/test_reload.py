from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from drawio_decode import decompress_diagram_payload
from drawio_library import bake_label_placeholders, load_library_shapes
from drawio_ports import port_anchors
from migrate import migrate_mxfile_xml, reload_drawio_file

LIBRARY = ROOT / "drawio-lib" / "drawclock.xml"
SHAPES = load_library_shapes(LIBRARY)
COMPRESSED_FIXTURE = ROOT / "tests" / "fixtures" / "mini-tree-compressed.drawio"


@pytest.mark.parametrize(
    ("fig", "edge_id"),
        [
            ("fig1", "12"),
            ("fig2", "24"),
            ("fig2", "25"),
        ],
)
def test_example_out_reload_preserves_input_waypoints(fig: str, edge_id: str) -> None:
    """example.bat 第 4 步产物须保留输入图航点；改 example 后须跑 example.bat 或本文件。"""
    source = ROOT / "example" / f"{fig}.drawio"
    out = ROOT / "example" / "out" / f"{fig}-reloaded.drawio"
    if not source.is_file():
        pytest.skip("先运行 scripts/build_example_demo.py")
    if not out.is_file():
        pytest.skip("先运行 example.bat（含 reload 步骤）")
    orig = source.read_text(encoding="utf-8")
    text = out.read_text(encoding="utf-8")
    assert _edge_waypoints(orig, edge_id) == _edge_waypoints(text, edge_id)
    if fig == "fig2" and edge_id in ("25", "26"):
        assert len(_edge_waypoints(orig, edge_id)) == 2


def _diagram_payload(mxfile_text: str) -> str:
    diagram = ET.fromstring(mxfile_text).find("diagram")
    assert diagram is not None
    model = diagram.find("mxGraphModel")
    if model is not None:
        return ET.tostring(model, encoding="unicode")
    payload = (diagram.text or "").strip()
    assert payload and not payload.startswith("<")
    return decompress_diagram_payload(payload)


def test_migrate_preserves_compressed_diagram_format() -> None:
    inp = COMPRESSED_FIXTURE.read_text(encoding="utf-8")
    out = migrate_mxfile_xml(inp, LIBRARY)
    assert "<mxGraphModel" not in out
    model_xml = _diagram_payload(out)
    assert "drawclockType=pll" in model_xml
    assert "html=1" in model_xml


def test_reload_compressed_fixture_output_stays_compressed(tmp_path: Path) -> None:
    out = tmp_path / "mini-reloaded.drawio"
    reload_drawio_file(COMPRESSED_FIXTURE, LIBRARY, out)
    text = out.read_text(encoding="utf-8")
    assert "<mxGraphModel" not in text
    assert "drawclockType=pll" in _diagram_payload(text)


def test_reload_compressed_drawio_svg_output_stays_compressed(tmp_path: Path) -> None:
    source = ROOT / "test.drawio.svg"
    if not source.is_file():
        pytest.skip("需要仓库根目录 test.drawio.svg")
    orig = source.read_text(encoding="utf-8")
    if "drawclockType=" not in orig:
        pytest.skip("test.drawio.svg 不含器件库图形")
    out = tmp_path / "reloaded.drawio"
    reload_drawio_file(source, LIBRARY, out)
    text = out.read_text(encoding="utf-8")
    assert "<mxGraphModel" not in text
    assert "drawclockType=" in _diagram_payload(text)


def test_reload_uncompressed_fixture_stays_uncompressed(tmp_path: Path) -> None:
    source = ROOT / "tests" / "fixtures" / "mini-tree.drawio"
    out = tmp_path / "mini-reloaded.drawio"
    reload_drawio_file(source, LIBRARY, out)
    text = out.read_text(encoding="utf-8")
    assert "<mxGraphModel" in text


def test_reload_preserves_example_edge_waypoints(tmp_path: Path) -> None:
    source = ROOT / "example" / "fig2.drawio"
    if not source.is_file():
        pytest.skip("先运行 scripts/build_example_demo.py")
    out = tmp_path / "fig2-reloaded.drawio"
    reload_drawio_file(source, LIBRARY, out)
    orig = source.read_text(encoding="utf-8")
    text = out.read_text(encoding="utf-8")
    for edge_id in ("24", "25"):
        assert _edge_waypoints(orig, edge_id) == _edge_waypoints(text, edge_id)
        assert len(_edge_waypoints(orig, edge_id)) == 2, f"edge {edge_id} 应有 2 个航点（pll_main 汇流柱）"
    assert _edge_waypoints(orig, "24") == ((170, 140), (170, 80))
    assert _edge_waypoints(orig, "25") == ((170, 140), (170, 200))
    assert "exitPerimeter=0" in _edge_style(text, "24")


def test_reload_preserves_fig1_cross_wire_waypoints(tmp_path: Path) -> None:
    source = ROOT / "example" / "fig1.drawio"
    if not source.is_file():
        pytest.skip("先运行 scripts/build_example_demo.py")
    out = tmp_path / "fig1-reloaded.drawio"
    reload_drawio_file(source, LIBRARY, out)
    orig = source.read_text(encoding="utf-8")
    text = out.read_text(encoding="utf-8")
    assert _edge_waypoints(orig, "12") == _edge_waypoints(text, "12")
    assert len(_edge_waypoints(orig, "12")) >= 2


def _mxfile_searchable(xml_text: str) -> str:
    if "<mxGraphModel" in xml_text:
        return xml_text
    return _diagram_payload(xml_text)


def _edge_waypoints(xml_text: str, cell_id: str) -> tuple[tuple[int, int], ...]:
    chunk = _edge_chunk(_mxfile_searchable(xml_text), cell_id)
    if chunk is None:
        return ()
    points: list[tuple[int, int]] = []
    for match in re.finditer(r'<mxPoint x="(\d+)" y="(\d+)"', chunk):
        points.append((int(match.group(1)), int(match.group(2))))
    return tuple(points)


def _edge_chunk(xml_text: str, cell_id: str) -> str | None:
    marker = f'id="{cell_id}"'
    start = xml_text.find(marker)
    if start < 0:
        return None
    end = xml_text.find("</mxCell>", start)
    return xml_text[start:end] if end >= 0 else None


def _edge_style(xml_text: str, cell_id: str) -> str | None:
    text = _mxfile_searchable(xml_text)
    marker = f'id="{cell_id}" style="'
    start = text.find(marker)
    if start < 0:
        return None
    start += len(marker)
    end = text.find('"', start)
    return text[start:end] if end >= 0 else None


@pytest.mark.parametrize("fig", ["fig1", "fig2"])
def test_example_out_reload_stays_compressed(fig: str) -> None:
    out = ROOT / "example" / "out" / f"{fig}-reloaded.drawio"
    if not out.is_file():
        pytest.skip("先运行 example.bat（含 reload 步骤）")
    text = out.read_text(encoding="utf-8")
    assert "<mxGraphModel" not in text
    assert "drawclockType=" in _diagram_payload(text)


def test_reload_preserves_geometry_and_upgrades_style(tmp_path: Path) -> None:
    source = ROOT / "example" / "fig2.drawio"
    if not source.is_file():
        pytest.skip("先运行 scripts/build_example_demo.py")
    out = tmp_path / "fig2-reloaded.drawio"
    reload_drawio_file(source, LIBRARY, out)
    text = out.read_text(encoding="utf-8")
    assert "<mxGraphModel" not in text
    inner = _mxfile_searchable(text)
    assert 'name="pll_main"' in inner
    assert 'x="36"' in inner
    assert "overflow=visible" in inner
    assert "resizable=0" in inner
    assert "html=1" in inner
    gate = re.search(
        r'name="gate0"[^>]*>[\s\S]*?<mxGeometry x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"',
        inner,
    )
    assert gate is not None
    assert gate.group(1) == "180"
    assert gate.group(2) == "50"
    assert gate.group(3) == str(SHAPES["gate"].w)
    assert gate.group(4) == str(SHAPES["gate"].h)


def test_reload_keeps_placeholder_template_for_edit(tmp_path: Path) -> None:
    inp = ROOT / "tests" / "fixtures" / "mini-tree.drawio"
    out = tmp_path / "out.drawio"
    reload_drawio_file(inp, LIBRARY, out)
    inner = html.unescape(_mxfile_searchable(out.read_text(encoding="utf-8")))
    assert 'placeholders="1"' in inner
    assert "%name%" in inner
    assert "%pll_kind%" in inner
    assert 'name="pll0"' in inner


def test_reload_replaces_stale_baked_label_viewbox(tmp_path: Path) -> None:
    gate = SHAPES["gate"]
    stale_w = gate.w + 40
    stale_label = bake_label_placeholders(
        gate.label.replace(f"0 0 {gate.w} {gate.h}", f"0 0 {stale_w} {gate.h}"),
        {"name": "g1"},
    )
    obj = ET.Element(
        "object",
        {"name": "g1", "placeholders": "0", "id": "10", "label": stale_label},
    )
    mxcell = ET.SubElement(
        obj,
        "mxCell",
        {
            "style": "drawclockType=gate;html=1;",
            "vertex": "1",
            "parent": "1",
        },
    )
    geom = ET.SubElement(mxcell, "mxGeometry", {"as": "geometry"})
    geom.set("x", "0")
    geom.set("y", "0")
    geom.set("width", str(stale_w))
    geom.set("height", str(gate.h))
    root = ET.Element("root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
    root.append(obj)
    model = ET.Element("mxGraphModel")
    model.append(root)
    diagram = ET.Element("diagram")
    diagram.append(model)
    mxfile = ET.Element("mxfile")
    mxfile.append(diagram)
    inp = tmp_path / "stale-label.drawio"
    inp.write_text(ET.tostring(mxfile, encoding="unicode"), encoding="utf-8")
    out = tmp_path / "out.drawio"
    reload_drawio_file(inp, LIBRARY, out)
    inner = html.unescape(_mxfile_searchable(out.read_text(encoding="utf-8")))
    assert f'viewBox="0 0 {gate.w} {gate.h}"' in inner
    assert f'viewBox="0 0 {stale_w} {gate.h}"' not in inner
    assert f'width="{gate.w}"' in inner
    assert "%name%" in inner
    assert 'placeholders="1"' in inner


def test_reload_realigns_edge_ports_after_geometry_change(tmp_path: Path) -> None:
    gate = SHAPES["gate"]
    pll = SHAPES["pll"]
    stale_w = max(gate.w - 40, 40)
    pll_out = port_anchors(pll.style, "pll")["right"]
    gate_in = port_anchors(gate.style, "gate")["left"]
    inp = tmp_path / "edge-misaligned.drawio"
    inp.write_text(
        f"""<mxfile><diagram><mxGraphModel><root>
        <mxCell id="0"/><mxCell id="1" parent="0"/>
        <object name="pll0" placeholders="0" id="10">
          <mxCell style="{pll.style}" vertex="1" parent="1">
            <mxGeometry x="40" y="40" width="{pll.w}" height="{pll.h}" as="geometry"/>
          </mxCell>
        </object>
        <object name="gate0" placeholders="0" id="11">
          <mxCell style="{gate.style}" vertex="1" parent="1">
            <mxGeometry x="200" y="40" width="{stale_w}" height="{gate.h}" as="geometry"/>
          </mxCell>
        </object>
        <mxCell id="20" style="exitX=1;exitY=0.5;entryX=0;entryY=0.5;edgeStyle=none;html=1;" edge="1" parent="1" source="10" target="11">
          <mxGeometry relative="1" as="geometry"/>
        </mxCell>
        </root></mxGraphModel></diagram></mxfile>""",
        encoding="utf-8",
    )
    out = tmp_path / "out.drawio"
    reload_drawio_file(inp, LIBRARY, out)
    inner = html.unescape(_mxfile_searchable(out.read_text(encoding="utf-8")))
    edge = re.search(r'id="20" style="([^"]*)"', inner)
    assert edge is not None
    style = edge.group(1).replace(" ", "")
    exit_part = style.split("entryX", 1)[0]
    assert f"exitX={pll_out[0]}" in exit_part or f"exitX={pll_out[0]:g}" in exit_part
    assert "exitX=1" not in exit_part
    assert f"entryX={gate_in[0]}" in style or f"entryX={gate_in[0]:g}" in style


def test_reload_applies_library_width_from_narrow_fixture(tmp_path: Path) -> None:
    narrow_w = SHAPES["gate"].w + 40
    inp = tmp_path / "narrow.drawio"
    inp.write_text(
        f"""<mxfile><diagram><mxGraphModel><root>
        <mxCell id="0"/><mxCell id="1" parent="0"/>
        <object name="g" placeholders="0" id="10">
          <mxCell style="drawclockType=gate;html=1;" vertex="1" parent="1">
            <mxGeometry x="10" y="20" width="{narrow_w}" height="70" as="geometry"/>
          </mxCell>
        </object>
        </root></mxGraphModel></diagram></mxfile>""",
        encoding="utf-8",
    )
    out = tmp_path / "out.drawio"
    reload_drawio_file(inp, LIBRARY, out)
    inner = _mxfile_searchable(out.read_text(encoding="utf-8"))
    geom = re.search(
        r'name="g"[^>]*>[\s\S]*?<mxGeometry x="10" y="20" width="(\d+)" height="(\d+)"',
        inner,
    )
    assert geom is not None
    assert geom.group(1) == str(SHAPES["gate"].w)
    assert geom.group(2) == str(SHAPES["gate"].h)
    assert int(geom.group(1)) < narrow_w


def test_reload_keeps_non_library_vertex(tmp_path: Path) -> None:
    inp = tmp_path / "mixed.drawio"
    inp.write_text(
        """<mxfile>
  <diagram>
    <mxGraphModel>
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <object name="n1" placeholders="0" id="10">
          <mxCell style="drawclockType=pll;points=[[1,0.5,0,0,0]];" vertex="1" parent="1">
            <mxGeometry x="10" y="20" width="80" height="90" as="geometry"/>
          </mxCell>
        </object>
        <mxCell id="99" value="note" style="text;html=1;" vertex="1" parent="1">
          <mxGeometry x="200" y="30" width="60" height="20" as="geometry"/>
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
""",
        encoding="utf-8",
    )
    out = tmp_path / "out.drawio"
    reload_drawio_file(inp, LIBRARY, out)
    text = out.read_text(encoding="utf-8")
    assert 'value="note"' in text
    assert 'x="200"' in text
    assert "overflow=visible" in text
    assert "resizable=0" in text


def test_migrate_rejects_unknown_library_type() -> None:
    bad = """<mxfile><diagram><mxGraphModel><root>
        <mxCell id="0"/><mxCell id="1" parent="0"/>
        <object name="x" id="2"><mxCell style="drawclockType=not_a_type;" vertex="1" parent="1">
        <mxGeometry x="0" y="0" width="10" height="10" as="geometry"/></mxCell></object>
        </root></mxGraphModel></diagram></mxfile>"""
    try:
        migrate_mxfile_xml(bad, LIBRARY)
    except ValueError as exc:
        assert "不在新器件库" in str(exc)
    else:
        raise AssertionError("expected ValueError")
