from __future__ import annotations

from typing import Any

from device_model import DeviceState
from from_resolve import (
  build_from_endpoints,
  format_upstream_source,
  from_input_out_ports,
  output_counts_by_name,
)
from library_ports import (
  PortTopology,
  connection_key_for_port,
  input_connection_keys,
  output_connection_keys,
  topology_for_type,
)


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
  input_keys_by_kind = _connection_keys_by_kind(devices, input_connection_keys, library_path)
  output_keys_by_kind = _connection_keys_by_kind(devices, output_connection_keys, library_path)
  output_keys_by_name = _keys_by_device_name(devices, output_keys_by_kind)
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
        input_keys_by_kind=input_keys_by_kind,
        output_keys_by_name=output_keys_by_name,
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


def _connection_keys_by_kind(
  devices: dict[str, DeviceState],
  loader,
  library_path: str,
) -> dict[str, dict[str, str]]:
  by_kind: dict[str, dict[str, str]] = {}
  for state in devices.values():
    if state.kind == "from":
      continue
    if state.kind not in by_kind:
      by_kind[state.kind] = loader(state.kind, library_path=library_path)
  return by_kind


def _keys_by_device_name(
  devices: dict[str, DeviceState],
  keys_by_kind: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
  return {
    state.name: keys_by_kind[state.kind]
    for state in devices.values()
    if state.kind != "from"
  }


def _format_source(
  peer: str,
  *,
  direct_out_port: str | None,
  from_names: set[str],
  from_endpoints: dict,
  from_out_ports: dict[str, str | None],
  output_counts: dict[str, int],
  output_keys_by_name: dict[str, dict[str, str]],
) -> str | None:
  return format_upstream_source(
    peer,
    direct_out_port=direct_out_port,
    from_names=from_names,
    from_endpoints=from_endpoints,
    from_out_ports=from_out_ports,
    output_counts=output_counts,
    output_keys_by_name=output_keys_by_name,
  )


def _device_entry(
  state: DeviceState,
  *,
  library_path: str,
  from_names: set[str],
  from_endpoints: dict,
  from_out_ports: dict[str, str | None],
  output_counts: dict[str, int],
  input_keys_by_kind: dict[str, dict[str, str]],
  output_keys_by_name: dict[str, dict[str, str]],
) -> dict[str, Any]:
  topology = topology_for_type(state.kind, library_path=library_path)
  entry: dict[str, Any] = {"name": state.name, **dict(state.object_attrs)}
  if "kind" not in entry:
    entry["kind"] = state.kind

  input_keys = input_keys_by_kind.get(state.kind, {})

  source = _source_field(
    state,
    topology,
    input_keys=input_keys,
    from_names=from_names,
    from_endpoints=from_endpoints,
    from_out_ports=from_out_ports,
    output_counts=output_counts,
    output_keys_by_name=output_keys_by_name,
  )
  if source is not None:
    entry["source"] = source

  return entry


def _source_field(
  state: DeviceState,
  topology: PortTopology,
  *,
  input_keys: dict[str, str],
  from_names: set[str],
  from_endpoints: dict,
  from_out_ports: dict[str, str | None],
  output_counts: dict[str, int],
  output_keys_by_name: dict[str, dict[str, str]],
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
      output_keys_by_name=output_keys_by_name,
    )
    key = connection_key_for_port(port, topology, port_keys=input_keys)
    resolved[key] = upstream or peer

  if not resolved:
    return None
  if len(topology.inputs) == 1:
    sole = topology.inputs[0]
    return resolved[connection_key_for_port(sole, topology, port_keys=input_keys)]
  return resolved
