from __future__ import annotations

from pathlib import Path

from device_model import DeviceState
from drawio_graph import GraphCell, ParsedDiagram, edge_attachment, edge_is_undirected
from from_resolve import FromEndpoints, build_from_endpoints
from library_ports import (
  PortTopology,
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
    if (
      edge_is_undirected(edge.style)
      and _undirected_edge_orientation(
        src, tgt, exit_xy, entry_xy, library_path=library_path
      )
      == "reversed"
    ):
      upstream_out_port = resolve_port(tgt.points, entry_xy)
      _bind_endpoint(
        devices,
        from_by_name,
        tgt,
        entry_xy,
        src.name,
        outgoing=True,
        from_names=from_names,
        library_path=library_path,
      )
      _bind_endpoint(
        devices,
        from_by_name,
        src,
        exit_xy,
        tgt.name,
        outgoing=False,
        from_names=from_names,
        upstream_out_port=upstream_out_port,
        library_path=library_path,
      )
    else:
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

  validate_topology(
    devices,
    from_by_name,
    library_path=library_path,
    diagram=diagram,
  )
  return devices, from_by_name


def _undirected_edge_orientation(
  src: GraphCell,
  tgt: GraphCell,
  exit_xy: tuple[float, float] | None,
  entry_xy: tuple[float, float] | None,
  *,
  library_path: str | Path,
) -> str | None:
  if not src.drawclock_type or not tgt.drawclock_type:
    return None
  src_port = resolve_port(src.points, exit_xy)
  tgt_port = resolve_port(tgt.points, entry_xy)
  if src_port is None or tgt_port is None:
    return None
  src_topo = topology_for_type(src.drawclock_type, library_path=library_path)
  tgt_topo = topology_for_type(tgt.drawclock_type, library_path=library_path)
  if is_output_port(src_port, src_topo) and is_input_port(tgt_port, tgt_topo):
    return "normal"
  if is_input_port(src_port, src_topo) and is_output_port(tgt_port, tgt_topo):
    return "reversed"
  return None


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
      raise ValueError(
        f"连线方向错误：{peer_name} → from {cell.name}。"
        f"from 只能向右连出到下游，不能接受连线；"
        f"跨图时钟靠与 clock 同名对应，不是把其它器件连到 from"
      )
    port = resolve_port(cell.points, xy)
    if port is None:
      port = "right"
    topology = topology_for_type("from", library_path=library_path)
    if port not in topology.outputs:
      raise ValueError(
        f"from {cell.name} 只能从右侧（right）连出，"
        f"当前连线挂在 {port} 侧"
      )
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
  diagram: ParsedDiagram | None = None,
) -> None:
  errors: list[str] = []
  errors.extend(_duplicate_device_name_errors(devices))
  device_names = {s.name for s in devices.values() if s.kind != "from"}
  clock_names = {s.name for s in devices.values() if s.kind == "clock"}
  from_names = set(from_by_name.keys())
  from_endpoints = build_from_endpoints(devices, from_by_name, library_path=library_path)
  name_to_cell = _name_to_cell_id(devices)

  for from_name in from_names:
    if from_name not in clock_names:
      errors.append(
        f"from {from_name} 未找到同名 clock"
        f"（全部输入图中须有一个 name 相同的 clock 器件）"
      )

  for from_name, endpoints in from_endpoints.items():
    errors.extend(_from_endpoint_errors(from_name, endpoints, device_names))

  for state in devices.values():
    if state.kind == "from":
      continue
    topology = topology_for_type(state.kind, library_path=library_path)
    missing_inputs = set(topology.inputs) - set(state.bindings)
    if missing_inputs:
      block = [f"器件 {state.name} 未连接的输入端口: {', '.join(sorted(missing_inputs))}"]
      cell_id = name_to_cell.get(state.name)
      if diagram is not None and cell_id is not None:
        block.extend(
          _diagnose_missing_inputs(
            state,
            cell_id,
            missing_inputs,
            diagram,
            library_path=library_path,
          )
        )
      errors.append("\n".join(block))

  for state in devices.values():
    if state.kind == "from":
      continue
    topology = topology_for_type(state.kind, library_path=library_path)
    if _total_port_count(topology) != 1 or not topology.outputs:
      continue
    port = topology.outputs[0]
    if state.out_bindings.get(port):
      continue
    block = [f"器件 {state.name} 的输出端口 {port} 未连接"]
    cell_id = name_to_cell.get(state.name)
    if diagram is not None and cell_id is not None:
      block.extend(
        _diagnose_missing_outputs(
          state,
          cell_id,
          {port},
          diagram,
          library_path=library_path,
        )
      )
    errors.append("\n".join(block))

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


def _name_to_cell_id(devices: dict[str, DeviceState]) -> dict[str, str]:
  mapping: dict[str, str] = {}
  for cell_id, state in devices.items():
    if state.kind == "from":
      continue
    mapping[state.name] = cell_id
  return mapping


def _edge_endpoints(
  edge: GraphCell,
  diagram: ParsedDiagram,
) -> tuple[GraphCell | None, GraphCell | None]:
  src = diagram.cells.get(edge.source_id or "")
  tgt = diagram.cells.get(edge.target_id or "")
  if src is not None and src.is_edge:
    src = None
  if tgt is not None and tgt.is_edge:
    tgt = None
  return src, tgt


def _peer_label(cell: GraphCell | None, fallback_id: str | None) -> str:
  if cell is None:
    return fallback_id or "?"
  return cell.name or cell.drawclock_type or cell.cell_id


def _diagnose_missing_inputs(
  state: DeviceState,
  cell_id: str,
  missing: set[str],
  diagram: ParsedDiagram,
  *,
  library_path: str | Path,
) -> list[str]:
  hints: list[str] = []
  topology = topology_for_type(state.kind, library_path=library_path)
  missing_sorted = sorted(missing)
  explained_ports: set[str] = set()
  still_missing_noted: set[str] = set()
  incoming: list[GraphCell] = []
  outgoing: list[GraphCell] = []

  for edge in diagram.cells.values():
    if not edge.is_edge:
      continue
    if edge.target_id == cell_id:
      incoming.append(edge)
    elif edge.source_id == cell_id:
      outgoing.append(edge)

  for edge in incoming:
    src, tgt = _edge_endpoints(edge, diagram)
    src_name = _peer_label(src, edge.source_id)
    tgt_name = _peer_label(tgt, edge.target_id)
    prefix = f"  · 连线 {src_name}→{tgt_name}"

    if src is None or tgt is None:
      hints.append(f"{prefix}：source 或 target 缺失，已忽略")
      continue

    if not src.drawclock_type or not tgt.drawclock_type:
      bad = "source" if not src.drawclock_type else "target"
      hints.append(f"{prefix}：{bad} 端不是 drawclock 器件，已忽略")
      continue

    entry_xy = edge_attachment(edge.style, end="entry")
    resolved = resolve_port(state.points, entry_xy)

    if entry_xy is None:
      hints.append(f"{prefix}：缺少 entry 端口附着")
      continue

    if resolved and is_output_port(resolved, topology):
      hints.append(
        f"{prefix}：entry 误接输出口 {resolved}，应接入 {', '.join(missing_sorted)}"
      )
      continue

    if resolved and is_input_port(resolved, topology) and resolved not in missing:
      hints.append(
        f"{prefix}：{resolved} 已接入，尚缺 {', '.join(missing_sorted)}"
      )
      still_missing_noted.update(missing)
      continue

    if resolved is None:
      hints.append(
        f"{prefix}：entry 未对齐到器件端口；可 drawclock reload 或重画连线"
      )

  for edge in outgoing:
    src, tgt = _edge_endpoints(edge, diagram)
    if src is None or tgt is None:
      continue
    tgt_name = _peer_label(tgt, edge.target_id)
    exit_xy = edge_attachment(edge.style, end="exit")
    resolved = resolve_port(state.points, exit_xy)
    if resolved and is_input_port(resolved, topology) and resolved in missing:
      if not (
        edge_is_undirected(edge.style)
        and src is not None
        and tgt is not None
        and _undirected_edge_orientation(
          src,
          tgt,
          exit_xy,
          edge_attachment(edge.style, end="entry"),
          library_path=library_path,
        )
        == "reversed"
      ):
        hints.append(
          f"  · {resolved}：连线 {state.name}→{tgt_name} 方向反了，"
          f"应为 {tgt_name}→{state.name}"
        )
      explained_ports.add(resolved)

  for port in missing_sorted:
    if port in explained_ports:
      continue
    if port in still_missing_noted and len(missing) == 1:
      continue
    hints.append(f"  · {port}：无入线指向 {state.name}")

  if not incoming and not outgoing and not hints:
    hints.append(f"  · 未发现指向 {state.name} 的连线")

  return hints


def _diagnose_missing_outputs(
  state: DeviceState,
  cell_id: str,
  missing: set[str],
  diagram: ParsedDiagram,
  *,
  library_path: str | Path,
) -> list[str]:
  hints: list[str] = []
  topology = topology_for_type(state.kind, library_path=library_path)
  incoming: list[GraphCell] = []
  outgoing: list[GraphCell] = []

  for edge in diagram.cells.values():
    if not edge.is_edge:
      continue
    if edge.target_id == cell_id:
      incoming.append(edge)
    elif edge.source_id == cell_id:
      outgoing.append(edge)

  explained = False

  for edge in outgoing:
    src, tgt = _edge_endpoints(edge, diagram)
    tgt_name = _peer_label(tgt, edge.target_id)
    prefix = f"  · 连线 {state.name}→{tgt_name}"
    exit_xy = edge_attachment(edge.style, end="exit")
    resolved = resolve_port(state.points, exit_xy)

    if exit_xy is None:
      hints.append(f"{prefix}：缺少 exit 端口附着")
      explained = True
      continue

    if resolved and is_input_port(resolved, topology):
      hints.append(
        f"{prefix}：exit 落在输入口 {resolved}，不会登记输出；"
        f"应从 {state.name} 指向下游"
      )
      explained = True
      continue

    if resolved and is_output_port(resolved, topology) and resolved not in missing:
      hints.append(
        f"{prefix}：exit 落在 {resolved}，不是缺失的 {', '.join(sorted(missing))}"
      )
      explained = True
      continue

    if resolved is None:
      hints.append(
        f"{prefix}：exit 未对齐到器件端口；可 drawclock reload 或重画连线"
      )
      explained = True

  for edge in incoming:
    src, tgt = _edge_endpoints(edge, diagram)
    src_name = _peer_label(src, edge.source_id)
    entry_xy = edge_attachment(edge.style, end="entry")
    resolved = resolve_port(state.points, entry_xy)
    if resolved and is_output_port(resolved, topology) and resolved in missing:
      if not (
        edge_is_undirected(edge.style)
        and src is not None
        and tgt is not None
        and _undirected_edge_orientation(
          src,
          tgt,
          edge_attachment(edge.style, end="exit"),
          entry_xy,
          library_path=library_path,
        )
        == "reversed"
      ):
        hints.append(
          f"  · 连线 {src_name}→{state.name}：方向反了（entry 在 {resolved}）；"
          f"应改为 {state.name}→{src_name}"
        )
      explained = True

  if not outgoing and not explained:
    hints.append(f"  · 未发现从 {state.name} 指出的连线")

  return hints


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
    errors.append(
      f"from {from_name} 未连到任何下游器件"
      f"（应从 from 向右拖线到目标器件；与 clock 的对应靠同名）"
    )
  return errors


def _total_port_count(topology: PortTopology) -> int:
  return len(topology.inputs) + len(topology.outputs)


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
