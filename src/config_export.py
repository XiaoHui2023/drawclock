from __future__ import annotations

from typing import Any

from device_model import DeviceState
from from_resolve import (
  build_from_endpoints,
  format_upstream_source,
  from_input_out_ports,
  output_counts_by_name,
)
from library_ports import PortTopology, connection_dict_key, topology_for_type


def devices_to_config(
  devices: dict[str, DeviceState],
  from_by_name: dict[str, list[str]],
  *,
  library_path: str,
) -> list[dict[str, Any]]:
  from_endpoints = build_from_endpoints(devices, from_by_name, library_path=library_path)
  from_names = set(from_by_name.keys())
  from_out_ports = from_input_out_ports(
    devices, from_by_name, library_path=library_path
  )
  output_counts = output_counts_by_name(devices, library_path=library_path)
  entries: list[dict[str, Any]] = []

  for state in devices.values():
    if state.kind == "from":
      continue
    entries.append(
      _device_entry(
        state,
        library_path=library_path,
        from_names=from_names,
        from_endpoints=from_endpoints,
        from_out_ports=from_out_ports,
        output_counts=output_counts,
      )
    )

  entries.sort(key=lambda item: item["name"])
  return entries


def entries_to_clock_tree(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
  tree: dict[str, dict[str, Any]] = {}
  for item in entries:
    name = item["name"]
    if name in tree:
      raise ValueError(f"器件名 {name} 重复")
    tree[name] = {k: v for k, v in item.items() if k != "name"}
  return tree


def _format_source(
  peer: str,
  *,
  direct_out_port: str | None,
  from_names: set[str],
  from_endpoints: dict,
  from_out_ports: dict[str, str | None],
  output_counts: dict[str, int],
) -> str | None:
  return format_upstream_source(
    peer,
    direct_out_port=direct_out_port,
    from_names=from_names,
    from_endpoints=from_endpoints,
    from_out_ports=from_out_ports,
    output_counts=output_counts,
  )


def _device_entry(
  state: DeviceState,
  *,
  library_path: str,
  from_names: set[str],
  from_endpoints: dict,
  from_out_ports: dict[str, str | None],
  output_counts: dict[str, int],
) -> dict[str, Any]:
  topology = topology_for_type(state.kind, library_path=library_path)
  entry: dict[str, Any] = {"name": state.name, "kind": state.kind, **dict(state.object_attrs)}

  source = _source_field(
    state,
    topology,
    from_names=from_names,
    from_endpoints=from_endpoints,
    from_out_ports=from_out_ports,
    output_counts=output_counts,
  )
  if source is not None:
    entry["source"] = source

  target = _target_field(state, topology)
  if target is not None:
    entry["target"] = target

  return entry


def _source_field(
  state: DeviceState,
  topology: PortTopology,
  *,
  from_names: set[str],
  from_endpoints: dict,
  from_out_ports: dict[str, str | None],
  output_counts: dict[str, int],
) -> str | dict[str, str] | None:
  if not topology.inputs:
    return None

  resolved: dict[str, str] = {}
  for port in topology.inputs:
    peer = state.bindings.get(port)
    if not peer:
      continue
    upstream = _format_source(
      peer,
      direct_out_port=state.source_out_ports.get(port),
      from_names=from_names,
      from_endpoints=from_endpoints,
      from_out_ports=from_out_ports,
      output_counts=output_counts,
    )
    resolved[connection_dict_key(port)] = upstream or peer

  if not resolved:
    return None
  if len(topology.inputs) == 1:
    return resolved[connection_dict_key(topology.inputs[0])]
  return resolved


def _target_field(
  state: DeviceState,
  topology: PortTopology,
) -> dict[str, str] | None:
  if len(topology.outputs) <= 1:
    return None

  resolved: dict[str, str] = {}
  for port in topology.outputs:
    peers = state.out_bindings.get(port, [])
    if peers:
      resolved[connection_dict_key(port)] = peers[0]

  return resolved or None
