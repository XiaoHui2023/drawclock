from __future__ import annotations

import re
from dataclasses import dataclass, field

MUX_KIND_RE = re.compile(r"^mux([2-6])$")


@dataclass
class DeviceState:
    kind: str
    name: str
    freq: str | None = None
    mux_labels: dict[str, str] = field(default_factory=dict)
    points: tuple[tuple[float, float], ...] = ()
    bindings: dict[str, str] = field(default_factory=dict)
    wire_targets: list[str] = field(default_factory=list)
    out_targets: list[str] = field(default_factory=list)
