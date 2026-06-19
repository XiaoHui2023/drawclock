from __future__ import annotations

from pathlib import Path

from device_model import DeviceState
from drawio_graph import GraphCell, ParsedDiagram, edge_attachment
from from_resolve import FromEndpoints, build_from_endpoints
from library_ports import (
  is_input_port,
  is_output_port,
  resolve_port,
  topology_for_type,
)


def build_device_states(
  diagram: ParsedDiagram,
  *,
  library_path: str | Path,
) -> tuple[dict[str, DeviceState], dict[str, list[str]]]:
  devices: dict[str, DeviceState] = {}
  for cell in diagram.cells.values():
    if cell.is_edge or not cell.drawclock_type:
      continue
    if cell.drawclock_type == "from":
      continue
    devices[cell.cell_id] = DeviceState(
      kind=cell.drawclock_type,
      name=cell.name,
      object_attrs=_exportable_attrs(cell),
      points=cell.points,
    )

  from_cells = [
    c for c in diagram.cells.values() if not c.is_edge and c.drawclock_type == "from"
  ]
  from_by_name: dict[str, list[str]] = {}
  for cell in from_cells:
    from_by_name.setdefault(cell.name, []).append(cell.cell_id)
    if cell.cell_id not in devices:
      devices[cell.cell_id] = DeviceState(
        kind="from",
        name=cell.name,
        points=cell.points,
      )

  from_names = set(from_by_name.keys())
  for edge in diagram.cells.values():
    if not edge.is_edge or not edge.source_id or not edge.target_id:
      continue
    src = diagram.cells.get(edge.source_id)
    tgt = diagram.cells.get(edge.target_id)
    if not src or not tgt or src.is_edge or tgt.is_edge:
      continue
    if not src.drawclock_type or not tgt.drawclock_type:
      continue
    exit_xy = edge_attachment(edge.style, end="exit")
    entry_xy = edge_attachment(edge.style, end="entry")
    src_exit_port = resolve_port(src.points, exit_xy)
    _bind_endpoint(
      devices,
      from_by_name,
      src,
      exit_xy,
      tgt.name,
      outgoing=True,
      from_names=from_names,
      library_path=library_path,
    )
    _bind_endpoint(
      devices,
      from_by_name,
      tgt,
      entry_xy,
      src.name,
      outgoing=False,
      from_names=from_names,
      upstream_out_port=src_exit_port,
      library_path=library_path,
    )

  validate_topology(devices, from_by_name, library_path=library_path)
  return devices, from_by_name


def _exportable_attrs(cell: GraphCell) -> dict[str, str]:
  skip = {"name", "label", "placeholders", "id", "_name"}
  return {
    key: value.strip()
    for key, value in cell.object_attrs.items()
    if key not in skip and value is not None and str(value).strip()
  }


def _bind_endpoint(
  devices: dict[str, DeviceState],
  from_by_name: dict[str, list[str]],
  cell: GraphCell,
  xy: tuple[float, float] | None,
  peer_name: str,
  *,
  outgoing: bool,
  from_names: set[str],
  upstream_out_port: str | None = None,
  library_path: str | Path,
) -> None:
  if cell.drawclock_type == "from":
    if not outgoing:
      raise ValueError(f"from {cell.name} 无输入端口，不能从 {peer_name} 接入")
    port = resolve_port(cell.points, xy)
    if port is None:
      port = "right"
    topology = topology_for_type("from", library_path=library_path)
    if port not in topology.outputs:
      raise ValueError(f"from {cell.name} 仅有输出端口，不能从 {port} 引出")
    state = devices.setdefault(
      cell.cell_id,
      DeviceState(kind="from", name=cell.name, points=cell.points),
    )
    if peer_name not in state.from_targets:
      state.from_targets.append(peer_name)
    return

  state = devices.get(cell.cell_id)
  if state is None:
    return
  port = resolve_port(cell.points, xy)
  topology = topology_for_type(cell.drawclock_type or "", library_path=library_path)
  if port is None:
    if outgoing and topology.outputs:
      port = topology.outputs[0]
    elif not outgoing and topology.inputs:
      port = topology.inputs[0]
    else:
      return

  if outgoing and is_output_port(port, topology):
    if peer_name not in state.out_targets:
      state.out_targets.append(peer_name)
    state.out_bindings.setdefault(port, [])
    if peer_name not in state.out_bindings[port]:
      state.out_bindings[port].append(peer_name)
    return

  if not outgoing and is_input_port(port, topology):
    if port in state.bindings:
      existing = state.bindings[port]
      if (
        (existing in from_names and peer_name not in from_names)
        or (existing not in from_names and peer_name in from_names)
      ):
        if peer_name in from_names:
          state.bindings[port] = peer_name
          if upstream_out_port:
            state.source_out_ports[port] = upstream_out_port
        return
      raise ValueError(
        f"器件 {state.name} 的端口 {port} 已有连接 {existing}，不能再接 {peer_name}"
      )
    state.bindings[port] = peer_name
    if upstream_out_port:
      state.source_out_ports[port] = upstream_out_port


def validate_topology(
  devices: dict[str, DeviceState],
  from_by_name: dict[str, list[str]],
  *,
  library_path: str | Path,
) -> None:
  errors: list[str] = []
  errors.extend(_duplicate_device_name_errors(devices))
  device_names = {s.name for s in devices.values() if s.kind != "from"}
  clock_names = {s.name for s in devices.values() if s.kind == "clock"}
  from_names = set(from_by_name.keys())
  from_endpoints = build_from_endpoints(devices, from_by_name, library_path=library_path)

  for from_name in from_names:
    if from_name not in clock_names:
      errors.append(f"from {from_name} 未找到同名 clock")

  for from_name, endpoints in from_endpoints.items():
    errors.extend(_from_endpoint_errors(from_name, endpoints, device_names))

  for state in devices.values():
    if state.kind == "from":
      continue
    topology = topology_for_type(state.kind, library_path=library_path)
    missing = set(topology.inputs) - set(state.bindings)
    if missing:
      errors.append(f"器件 {state.name} 未连接的端口: {', '.join(sorted(missing))}")

  for state in devices.values():
    if state.kind == "from":
      continue
    topology = topology_for_type(state.kind, library_path=library_path)
    if not topology.outputs:
      continue
    if topology.output_count == 1:
      port = topology.outputs[0]
      if not state.out_bindings.get(port) and not _output_blocked_by_open_from(
        state, from_names, from_endpoints
      ):
        errors.append(f"器件 {state.name} 的输出端口未连接")
      continue
    for port in topology.outputs:
      if not state.out_bindings.get(port) and not _output_blocked_by_open_from(
        state, from_names, from_endpoints
      ):
        errors.append(f"器件 {state.name} 的输出端口 {port} 未连接")

  for state in devices.values():
    if state.kind == "from":
      continue
    for peer in state.bindings.values():
      if peer not in device_names and peer not in from_names:
        errors.append(f"器件 {state.name} 连接到未知对象 {peer}")
    for peer in state.out_targets:
      if peer not in device_names and peer not in from_names:
        errors.append(f"器件 {state.name} 连接到未知对象 {peer}")

  if errors:
    raise ValueError("\n".join(errors))


def _from_endpoint_errors(
  from_name: str,
  endpoints: FromEndpoints,
  device_names: set[str],
) -> list[str]:
  targets = list(endpoints.targets)
  errors: list[str] = []
  for peer in targets:
    if peer not in device_names:
      errors.append(f"from {from_name} 连接到未知器件 {peer}")
  if not targets:
    errors.append(f"from {from_name} 右端未连接任何器件")
  return errors


def _output_blocked_by_open_from(
  state: DeviceState,
  from_names: set[str],
  from_endpoints: dict[str, FromEndpoints],
) -> bool:
  for peer in state.out_targets:
    if peer in from_names and not from_endpoints[peer].targets:
      return True
  return False


def _duplicate_device_name_errors(devices: dict[str, DeviceState]) -> list[str]:
  first_kind: dict[str, str] = {}
  errors: list[str] = []
  for state in devices.values():
    if state.kind == "from":
      continue
    prior = first_kind.get(state.name)
    if prior is not None:
      errors.append(
        f"器件名 {state.name} 重复（{prior} 与 {state.kind}），除 from 外名称须唯一"
      )
    else:
      first_kind[state.name] = state.kind
  return errors
