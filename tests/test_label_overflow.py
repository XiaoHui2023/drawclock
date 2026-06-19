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
        "div_n",
        "dto",
        "dto_n",
        "inv",
        "occ_clk_cell",
        "pll",
        "clock",
        "from",
        "mux2",
        "mux6",
    ],
)
def test_mxcell_uses_visible_overflow_and_fixed_size(module_name: str) -> None:
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


def test_fill_overflow_rejected() -> None:
    gate = importlib.import_module("drawio_lib.components.gate")
    html = gate.label_html()
    bad_style = gate.cell_style().replace("overflow=visible", "overflow=fill")
    with pytest.raises(ValueError, match="overflow=fill"):
        verify_label_overflow_policy(
            html,
            bad_style,
            title="gate",
            design_cell_w=gate.W,
            design_cell_h=gate.H,
        )


def test_resizable_required() -> None:
    gate = importlib.import_module("drawio_lib.components.gate")
    html = gate.label_html()
    bad_style = gate.cell_style().replace("resizable=0;", "")
    with pytest.raises(ValueError, match="resizable=0"):
        verify_label_overflow_policy(
            html,
            bad_style,
            title="gate",
            design_cell_w=gate.W,
            design_cell_h=gate.H,
        )


def test_percent_shell_rejected() -> None:
    gate = importlib.import_module("drawio_lib.components.gate")
    html = gate.label_html().replace(
        f"display:block;width:{gate.W}px;height:{gate.H}px;",
        "display:block;width:100%;height:100%;",
    )
    with pytest.raises(ValueError, match="fixed"):
        verify_label_stretch_policy(
            html,
            title="gate",
            design_cell_w=gate.W,
            design_cell_h=gate.H,
        )
