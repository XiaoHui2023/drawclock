from __future__ import annotations

import re
from dataclasses import dataclass, field

MUX_KIND_RE = re.compile(r"^mux([2-6])$")
PLL_EXPORT_KINDS = frozenset({"pll", "pll2"})

MULTI_OUTPUT_COUNTS: dict[str, int] = {
    "pll2": 2,
    "div_gate": 3,
    "clk_phase_sel": 3,
    "inv_mux": 2,
}

DUAL_INPUT_GATE_KINDS = frozenset({"and", "nand", "or", "nor", "xor", "xnor"})

THROUGH_DEVICE_KINDS = frozenset(
    {
        "gate",
        "div",
        "div_n",
        "dto",
        "dto_n",
        "inv",
        "async",
        "occ_clk_cell",
        "gen_cell",
        "bist_clk_cell",
        "occ_bist_clk_cell",
        "buffer",
    }
)


def device_output_count(kind: str) -> int:
    return MULTI_OUTPUT_COUNTS.get(kind, 0)


def is_multi_output_kind(kind: str) -> bool:
    return device_output_count(kind) > 1


def out_port_index(port: str) -> int | None:
    if port.startswith("out") and port[3:].isdigit():
        return int(port[3:])
    return None


@dataclass
class DeviceState:
    kind: str
    name: str
    freq: str | None = None
    pll_kind: str | None = None
    mux_labels: dict[str, str] = field(default_factory=dict)
    points: tuple[tuple[float, float], ...] = ()
    bindings: dict[str, str] = field(default_factory=dict)
    wire_targets: list[str] = field(default_factory=list)
    out_targets: list[str] = field(default_factory=list)
    out_bindings: dict[str, list[str]] = field(default_factory=dict)
    source_out_ports: dict[str, str] = field(default_factory=dict)
    wire_left_out_port: str | None = None
