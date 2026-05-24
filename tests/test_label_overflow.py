from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from drawio_lib.components.label_overflow import (
    verify_label_overflow_policy,
    verify_label_stretch_policy,
    verify_mxcell_label_style,
    verify_no_degenerate_label_tricks,
)


@pytest.mark.parametrize(
    "module_name",
    [
        "gate",
        "div",
        "dto",
        "inv",
        "pll",
        "clock",
        "wire",
        "mux2",
        "mux6",
    ],
)
def test_mxcell_uses_fill_overflow(module_name: str) -> None:
    mod = importlib.import_module(f"drawio_lib.components.{module_name}")
    style = mod.cell_style()
    html = mod.label_html()
    verify_label_overflow_policy(
        html,
        style,
        title=module_name,
        design_cell_w=mod.W,
        design_cell_h=mod.H,
    )
    verify_mxcell_label_style(style, title=module_name)
    verify_no_degenerate_label_tricks(html, title=module_name)


def test_middle_vertical_align_rejected() -> None:
    gate = importlib.import_module("drawio_lib.components.gate")
    bad = gate.cell_style().replace("verticalAlign=top", "verticalAlign=middle")
    with pytest.raises(ValueError, match="verticalAlign=top"):
        verify_mxcell_label_style(bad, title="gate")


def test_visible_overflow_rejected() -> None:
    gate = importlib.import_module("drawio_lib.components.gate")
    html = gate.label_html()
    bad_style = gate.cell_style().replace("overflow=fill", "overflow=visible")
    with pytest.raises(ValueError, match="overflow=visible"):
        verify_label_overflow_policy(
            html,
            bad_style,
            title="gate",
            design_cell_w=gate.W,
            design_cell_h=gate.H,
        )


def test_min_width_shell_rejected() -> None:
    gate = importlib.import_module("drawio_lib.components.gate")
    html = gate.label_html().replace(
        "display:block;width:100%;height:100%;",
        "display:block;width:100%;height:100%;min-width:80px;min-height:86px;",
    )
    with pytest.raises(ValueError, match="min-width/min-height"):
        verify_label_stretch_policy(
            html,
            title="gate",
            design_cell_w=gate.W,
            design_cell_h=gate.H,
        )
