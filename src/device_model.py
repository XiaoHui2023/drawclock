from __future__ import annotations

import re
from dataclasses import dataclass, field

MUX_KIND_RE = re.compile(r"^mux([2-6])$")
PLL_EXPORT_KINDS = frozenset({"pll", "pll2"})


def device_output_count(kind: str) -> int:
    if kind == "pll2":
        return 2
    if kind == "pll":
        return 1
    return 0


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
