from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
RELOAD = ROOT / "reload"
for path in (SRC, RELOAD):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from migrate import migrate_mxfile_xml, reload_drawio_file  # noqa: E402

LIBRARY = ROOT / "drawio-lib" / "drawclock.xml"


@pytest.mark.parametrize(
    ("fig", "edge_id"),
    [
        ("fig1", "12"),
        ("fig2", "25"),
        ("fig2", "26"),
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


def test_reload_preserves_example_edge_waypoints(tmp_path: Path) -> None:
    source = ROOT / "example" / "fig2.drawio"
    if not source.is_file():
        pytest.skip("先运行 scripts/build_example_demo.py")
    out = tmp_path / "fig2-reloaded.drawio"
    reload_drawio_file(source, LIBRARY, out)
    orig = source.read_text(encoding="utf-8")
    text = out.read_text(encoding="utf-8")
    for edge_id in ("25", "26"):
        assert _edge_waypoints(orig, edge_id) == _edge_waypoints(text, edge_id)
        assert len(_edge_waypoints(orig, edge_id)) == 2, f"edge {edge_id} 应有 2 个航点（pll_main 汇流柱）"
    assert _edge_waypoints(orig, "25") == ((170, 140), (170, 80))
    assert _edge_waypoints(orig, "26") == ((170, 140), (170, 200))
    assert "exitPerimeter=0" in _edge_style(text, "25")


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


def _edge_waypoints(xml_text: str, cell_id: str) -> tuple[tuple[int, int], ...]:
    chunk = _edge_chunk(xml_text, cell_id)
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
    marker = f'id="{cell_id}" style="'
    start = xml_text.find(marker)
    if start < 0:
        return None
    start += len(marker)
    end = xml_text.find('"', start)
    return xml_text[start:end] if end >= 0 else None


def test_reload_preserves_geometry_and_upgrades_style(tmp_path: Path) -> None:
    source = ROOT / "example" / "fig2.drawio"
    if not source.is_file():
        pytest.skip("先运行 scripts/build_example_demo.py")
    out = tmp_path / "fig2-reloaded.drawio"
    reload_drawio_file(source, LIBRARY, out)
    text = out.read_text(encoding="utf-8")
    assert 'name="pll_main"' in text
    assert 'x="-80"' in text
    assert "overflow=fill" in text
    assert "html=1" in text
    gate = re.search(
        r'name="gate0"[^>]*>[\s\S]*?<mxGeometry x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"',
        text,
    )
    assert gate is not None
    assert gate.group(1) == "180"
    assert gate.group(2) == "50"


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
    assert "overflow=fill" in text


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
