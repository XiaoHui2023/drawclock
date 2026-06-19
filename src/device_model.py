from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DeviceState:
  kind: str
  name: str
  object_attrs: dict[str, str] = field(default_factory=dict)
  points: tuple[tuple[float, float], ...] = ()
  bindings: dict[str, str] = field(default_factory=dict)
  from_targets: list[str] = field(default_factory=list)
  out_targets: list[str] = field(default_factory=list)
  out_bindings: dict[str, list[str]] = field(default_factory=dict)
  source_out_ports: dict[str, str] = field(default_factory=dict)
