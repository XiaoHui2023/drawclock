from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from verify_librsvg_output import verify_librsvg_output


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_gate_rejects_browser_only_foreign_object_source(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "source.svg",
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<foreignObject width="10" height="10"/></svg>',
    )
    flat = _write(tmp_path / "flat.svg", '<svg xmlns="http://www.w3.org/2000/svg"/>')
    with pytest.raises(ValueError, match="browser-only"):
        verify_librsvg_output(source, flat)


def test_gate_rejects_flattened_output_that_lost_components(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "source.svg",
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<g class="component"><svg class="component-graphic"><path d="M0 0L1 1"/></svg></g>'
        '<polyline class="edge" points="0,0 1,1"/></svg>',
    )
    flat = _write(
        tmp_path / "flat.svg",
        '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0H1"/></svg>',
    )
    with pytest.raises(ValueError, match="lost rendered content"):
        verify_librsvg_output(source, flat)


def test_gate_accepts_independently_painted_component_and_edge(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "source.svg",
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<g class="component"><svg class="component-graphic"><path d="M0 0L1 1"/></svg></g>'
        '<polyline class="edge" points="0,0 1,1"/></svg>',
    )
    flat = _write(
        tmp_path / "flat.svg",
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<path d="M0 0H1"/><path d="M0 0H1"/><path d="M0 0H1"/>'
        '</svg>',
    )
    assert verify_librsvg_output(source, flat)["painted_paths"] == 3
