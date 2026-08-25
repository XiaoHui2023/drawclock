from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from drawio_lib.components.registry import ALL
_BROWSER_CANDIDATES = [
    shutil.which(name)
    for name in ("msedge", "microsoft-edge", "google-chrome", "chromium")
]
_BROWSER_CANDIDATES.extend(
    [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
)
BROWSER = next(
    (Path(candidate) for candidate in _BROWSER_CANDIDATES if candidate and Path(candidate).is_file()),
    None,
)
PORT_TOLERANCE_PX = 0.03


def _edge_dump_dom(page: Path) -> str:
    assert BROWSER is not None
    sandbox_args = (
        ["--no-sandbox"]
        if os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() == 0
        else []
    )
    completed = subprocess.run(
        [
            str(BROWSER), "--headless", "--disable-gpu", *sandbox_args,
            "--dump-dom", page.as_uri(),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    return completed.stdout


def _result_json(dump: str) -> object:
    match = re.search(r'<pre id="result">(.*?)</pre>', dump, re.S)
    assert match is not None, "Edge DOM dump is missing the geometry probe result"
    return json.loads(html.unescape(match.group(1)))


def _geometry_probe_script(metadata: list[dict[str, object]]) -> str:
    return r"""
      const specs = __METADATA__;
      const result = specs.map(spec => {
        const svg = document.getElementById(spec.id).querySelector('svg');
        const geoms = [...svg.querySelectorAll(
          'path,polygon,polyline,line,circle,ellipse,rect'
        )];
        const samples = [];
        for (const geom of geoms) {
          if (!geom.getTotalLength || !geom.getPointAtLength) continue;
          const length = geom.getTotalLength();
          const count = Math.max(2, Math.ceil(length / 0.01));
          for (let i = 0; i <= count; i++) {
            const point = geom.getPointAtLength(length * i / count);
            samples.push([point.x, point.y]);
          }
        }
        return {
          title: spec.title,
          ports: spec.ports.map(port => {
            const sameY = samples.filter(p => Math.abs(p[1] - port.y) <= 0.03);
            if (!sameY.length) return {...port, contactX: null};
            const xs = sameY.map(p => p[0]);
            const contactX = port.x <= spec.w / 2 ? Math.min(...xs) : Math.max(...xs);
            return {...port, contactX};
          })
        };
      });
      const pre = document.createElement('pre');
      pre.id = 'result';
      pre.textContent = JSON.stringify(result);
      document.body.replaceChildren(pre);
    """.replace("__METADATA__", json.dumps(metadata, ensure_ascii=False))


def _probe_cards(
    tmp_path: Path,
    cards: list[str],
    metadata: list[dict[str, object]],
    *,
    name: str,
) -> object:
    page = tmp_path / name
    page.write_text(
        "<!doctype html><meta charset=utf-8><body>"
        + "".join(cards)
        + f"<script>{_geometry_probe_script(metadata)}</script>",
        encoding="utf-8",
    )
    return _result_json(_edge_dump_dom(page))


@pytest.mark.skipif(BROWSER is None, reason="headless browser is unavailable")
def test_every_declared_port_hits_actual_visible_svg_geometry(tmp_path: Path) -> None:
    """Independent oracle: browser path geometry, not component port objects."""
    cards: list[str] = []
    metadata: list[dict[str, object]] = []
    expected_port_count = 0
    for index, spec in enumerate(ALL):
        mod = spec.module
        points = mod._parse_points(mod.cell_style())
        expected_port_count += len(points)
        card_id = f"component-{index}"
        cards.append(
            f'<div id="{card_id}" style="position:relative;width:{mod.W}px;'
            f'height:{mod.H}px;margin:20px">{mod.label_html()}</div>'
        )
        metadata.append(
            {
                "id": card_id,
                "title": mod.TITLE,
                "w": mod.W,
                "ports": [
                    {"index": port_index, "x": point[0] * mod.W, "y": point[1] * mod.H}
                    for port_index, point in enumerate(points)
                ],
            }
        )
    result = _probe_cards(
        tmp_path, cards, metadata, name="visible-port-probe.html"
    )
    checked = 0
    for component in result:
        for port in component["ports"]:
            checked += 1
            assert port["contactX"] is not None, (
                f'{component["title"]} port {port["index"]}: declared point has no '
                "visible SVG geometry on its horizontal connection axis"
            )
            assert abs(port["contactX"] - port["x"]) <= PORT_TOLERANCE_PX, (
                f'{component["title"]} port {port["index"]}: declared x={port["x"]:.4f}, '
                f'visible contact x={port["contactX"]:.4f}'
            )
    assert checked == expected_port_count == 57


@pytest.mark.skipif(BROWSER is None, reason="headless browser is unavailable")
def test_probe_rejects_historical_gate_center_anchor_fault(tmp_path: Path) -> None:
    """Seeded fault: the bubble centre is not its external wire contact."""
    gate = next(spec.module for spec in ALL if spec.module.TITLE == "gate")
    points = gate._parse_points(gate.cell_style())
    output = points[-1]
    wrong_x = output[0] * gate.W - 1.0
    result = _probe_cards(
        tmp_path,
        [f'<div id="gate" style="width:{gate.W}px;height:{gate.H}px">{gate.label_html()}</div>'],
        [{"id": "gate", "title": "gate-mutant", "w": gate.W,
          "ports": [{"index": 1, "x": wrong_x, "y": output[1] * gate.H}]}],
        name="gate-center-anchor-mutant.html",
    )
    port = result[0]["ports"][0]
    assert abs(port["contactX"] - port["x"]) > PORT_TOLERANCE_PX


@pytest.mark.skipif(BROWSER is None, reason="headless browser is unavailable")
def test_probe_rejects_pll_input_without_visible_contact_lead(tmp_path: Path) -> None:
    """Seeded fault: a declared PLL input may not terminate in an empty notch."""
    pll = next(spec.module for spec in ALL if spec.module.TITLE == "pll")
    point = pll._parse_points(pll.cell_style())[0]
    broken_html = re.sub(
        r'<path d="M 2 30 L 8 30"[^>]*/>', "", pll.label_html(), count=1
    )
    assert broken_html != pll.label_html()
    result = _probe_cards(
        tmp_path,
        [f'<div id="pll" style="width:{pll.W}px;height:{pll.H}px">{broken_html}</div>'],
        [{"id": "pll", "title": "pll-no-lead-mutant", "w": pll.W,
          "ports": [{"index": 0, "x": point[0] * pll.W, "y": point[1] * pll.H}]}],
        name="pll-no-input-lead-mutant.html",
    )
    port = result[0]["ports"][0]
    assert port["contactX"] is None or abs(port["contactX"] - port["x"]) > PORT_TOLERANCE_PX


@pytest.mark.skipif(BROWSER is None, reason="headless browser is unavailable")
@pytest.mark.parametrize("target_title", ["pll", "clock"])
def test_browser_ctm_maps_edge_endpoints_to_visible_gate_and_clock_contacts(
    tmp_path: Path, target_title: str,
) -> None:
    """Final-render oracle: outer edge points and nested SVG contacts share screen CTM."""
    gate = next(spec.module for spec in ALL if spec.module.TITLE == "gate")
    clock = next(spec.module for spec in ALL if spec.module.TITLE == target_title)
    gate_point = gate._parse_points(gate.cell_style())[-1]
    clock_point = clock._parse_points(clock.cell_style())[0]
    gate_x, gate_y = 100.0, 100.0
    clock_x = 220.0
    clock_y = gate_y + gate_point[1] * gate.H - clock_point[1] * clock.H
    end_x = clock_x + clock_point[0] * clock.W
    end_y = clock_y + clock_point[1] * clock.H
    start_x = gate_x + gate_point[0] * gate.W
    start_y = gate_y + gate_point[1] * gate.H
    page = tmp_path / "final-ctm-probe.html"
    page.write_text(
        f'''<!doctype html><meta charset="utf-8">
<svg id="outer" xmlns="http://www.w3.org/2000/svg" width="400" height="260">
  <polyline id="edge" points="{start_x},{start_y} {end_x},{end_y}" fill="none" stroke="black"/>
  <foreignObject x="{gate_x}" y="{gate_y}" width="{gate.W + 2}" height="{gate.H + 7}" overflow="visible">
    <div xmlns="http://www.w3.org/1999/xhtml" style="position:relative;left:2px;top:7px;width:{gate.W}px;height:{gate.H}px;overflow:visible">{gate.label_html()}</div>
  </foreignObject>
  <foreignObject x="{clock_x}" y="{clock_y}" width="{clock.W + 2}" height="{clock.H + 7}" overflow="visible">
    <div xmlns="http://www.w3.org/1999/xhtml" style="position:relative;left:2px;top:7px;width:{clock.W}px;height:{clock.H}px;overflow:visible">{clock.label_html()}</div>
  </foreignObject>
</svg>
<script>
  const edge = document.getElementById('edge');
  const svgs = [...document.querySelectorAll('foreignObject svg')];
  const matrix = edge.getScreenCTM();
  const edgePoint = index => {{
    const p = edge.points.getItem(index).matrixTransform(matrix);
    return [p.x, p.y];
  }};
  const localToScreen = (svg, x, y) => {{
    const p = new DOMPoint(x, y).matrixTransform(svg.getScreenCTM());
    return [p.x, p.y];
  }};
  const result = {{
    edgeStart: edgePoint(0), edgeEnd: edgePoint(1),
    gateContact: localToScreen(svgs[0], {gate_point[0] * gate.W}, {gate_point[1] * gate.H}),
    clockContact: localToScreen(svgs[1], {clock_point[0] * clock.W}, {clock_point[1] * clock.H})
  }};
  const pre = document.createElement('pre'); pre.id = 'result';
  pre.textContent = JSON.stringify(result); document.body.replaceChildren(pre);
</script>''',
        encoding="utf-8",
    )
    result = _result_json(_edge_dump_dom(page))
    assert result["edgeStart"] == pytest.approx(result["gateContact"], abs=0.01)
    assert result["edgeEnd"] == pytest.approx(result["clockContact"], abs=0.01)
