from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import re

from device_model import DeviceState
from library_ports import out_port_index, topology_for_type

SOURCE_REF_RE = re.compile(r"^(.+)\[(\d+)\]$")


@dataclass(frozen=True)
class FromEndpoints:
  left: str | None
  left_out_port: str | None
  targets: tuple[str, ...]


def _clock_inputs(
  devices: dict[str, DeviceState],
  *,
  library_path: str | Path,
) -> tuple[dict[str, str | None], dict[str, str | None]]:
  inputs: dict[str, str | None] = {}
  out_ports: dict[str, str | None] = {}
  for state in devices.values():
    if state.kind != "clock":
      continue
    topology = topology_for_type(state.kind, library_path=library_path)
    for port in topology.inputs:
      inputs[state.name] = state.bindings.get(port)
      out_ports[state.name] = state.source_out_ports.get(port)
      break
  return inputs, out_ports


def build_from_endpoints(
  devices: dict[str, DeviceState],
  from_by_name: dict[str, list[str]],
  *,
  library_path: str | Path,
) -> dict[str, FromEndpoints]:
  device_names = {s.name for s in devices.values() if s.kind != "from"}
  clock_inputs, clock_out_ports = _clock_inputs(devices, library_path=library_path)
  out: dict[str, FromEndpoints] = {}
  for from_name, cell_ids in from_by_name.items():
    targets: list[str] = []
    for cell_id in cell_ids:
      state = devices.get(cell_id)
      if state is None:
        continue
      for peer in state.from_targets:
        if peer not in targets:
          targets.append(peer)
    resolved_targets = tuple(peer for peer in targets if peer in device_names)
    out[from_name] = FromEndpoints(
      left=clock_inputs.get(from_name),
      left_out_port=clock_out_ports.get(from_name),
      targets=resolved_targets,
    )
  return out


def _is_from(peer: str, from_names: set[str]) -> bool:
  return peer in from_names


def resolve_input_peer(
  peer: str,
  *,
  from_names: set[str],
  from_endpoints: dict[str, FromEndpoints],
) -> str | None:
  if not _is_from(peer, from_names):
    return peer
  left = from_endpoints[peer].left
  if left is None or _is_from(left, from_names):
    return None
  return left


def from_input_out_ports(
  devices: dict[str, DeviceState],
  from_by_name: dict[str, list[str]],
  *,
  library_path: str | Path,
) -> dict[str, str | None]:
  _, clock_out_ports = _clock_inputs(devices, library_path=library_path)
  return {from_name: clock_out_ports.get(from_name) for from_name in from_by_name}


def parse_source_ref(ref: str) -> tuple[str, int | None]:
  match = SOURCE_REF_RE.match(ref)
  if not match:
    return ref, None
  return match.group(1), int(match.group(2))


def output_counts_by_name(
  devices: dict[str, DeviceState],
  *,
  library_path: str | Path,
) -> dict[str, int]:
  counts: dict[str, int] = {}
  for state in devices.values():
    if state.kind == "from":
      continue
    topology = topology_for_type(state.kind, library_path=library_path)
    if topology.output_count > 1:
      counts[state.name] = topology.output_count
  return counts


def format_upstream_source(
  peer: str,
  *,
  direct_out_port: str | None,
  from_names: set[str],
  from_endpoints: dict[str, FromEndpoints],
  from_out_ports: dict[str, str | None],
  output_counts: dict[str, int],
) -> str | None:
  out_port = direct_out_port
  if _is_from(peer, from_names):
    out_port = from_out_ports.get(peer) or out_port
    peer = resolve_input_peer(
      peer,
      from_names=from_names,
      from_endpoints=from_endpoints,
    )
  if peer is None:
    return None
  count = output_counts.get(peer, 1)
  index = out_port_index(out_port) if out_port else None
  if count <= 1 or index is None:
    return peer
  if index >= count:
    raise ValueError(f"上游器件 {peer} 的输出序号 [{index}] 超出输出路数 {count}")
  return f"{peer}[{index}]"
