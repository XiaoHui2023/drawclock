from __future__ import annotations

from drawio_graph import GraphCell, ParsedDiagram, edge_attachment
from device_model import DeviceState, MUX_KIND_RE
from wire_resolve import WireEndpoints, build_wire_endpoints


def build_device_states(diagram: ParsedDiagram) -> tuple[dict[str, DeviceState], dict[str, list[str]]]:
    devices: dict[str, DeviceState] = {}
    for cell in diagram.cells.values():
        if cell.is_edge or not cell.drawclock_type:
            continue
        if cell.drawclock_type == "wire":
            continue
        devices[cell.cell_id] = DeviceState(
            kind=cell.drawclock_type,
            name=cell.name,
            freq=cell.freq,
            pll_kind=cell.pll_kind,
            mux_labels=dict(cell.mux_labels),
            points=cell.points,
        )

    wire_cells = [
        c for c in diagram.cells.values() if not c.is_edge and c.drawclock_type == "wire"
    ]
    wire_by_name: dict[str, list[str]] = {}
    for cell in wire_cells:
        wire_by_name.setdefault(cell.name, []).append(cell.cell_id)
        if cell.cell_id not in devices:
            devices[cell.cell_id] = DeviceState(
                kind="wire",
                name=cell.name,
                points=cell.points,
            )

    wire_names = set(wire_by_name.keys())
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
        _bind_endpoint(
            devices,
            wire_by_name,
            src,
            exit_xy,
            tgt.name,
            outgoing=True,
            wire_names=wire_names,
        )
        _bind_endpoint(
            devices,
            wire_by_name,
            tgt,
            entry_xy,
            src.name,
            outgoing=False,
            wire_names=wire_names,
        )

    validate_topology(devices, wire_by_name)
    return devices, wire_by_name


def _bind_endpoint(
    devices: dict[str, DeviceState],
    wire_by_name: dict[str, list[str]],
    cell: GraphCell,
    xy: tuple[float, float] | None,
    peer_name: str,
    *,
    outgoing: bool,
    wire_names: set[str],
) -> None:
    if cell.drawclock_type == "wire":
        port = resolve_port(cell, xy)
        if port is None:
            port = "left" if not outgoing else "right"
        state = devices.setdefault(
            cell.cell_id,
            DeviceState(kind="wire", name=cell.name, points=cell.points),
        )
        if port == "left":
            if "left" in state.bindings:
                raise ValueError(
                    f"连线 {cell.name} 左端已有连接 {state.bindings['left']}，"
                    f"不能再接 {peer_name}"
                )
            state.bindings["left"] = peer_name
        else:
            if peer_name not in state.wire_targets:
                state.wire_targets.append(peer_name)
        return

    state = devices.get(cell.cell_id)
    if state is None:
        return
    port = resolve_port(cell, xy)
    if port is None:
        port = "right" if outgoing else "left"
    if state.kind == "source" and port == "right":
        if peer_name not in state.out_targets:
            state.out_targets.append(peer_name)
        return
    if state.kind == "pll" and port == "right":
        if peer_name not in state.out_targets:
            state.out_targets.append(peer_name)
        return

    if port in state.bindings:
        existing = state.bindings[port]
        if not outgoing and (
            (existing in wire_names and peer_name not in wire_names)
            or (existing not in wire_names and peer_name in wire_names)
        ):
            if peer_name in wire_names:
                state.bindings[port] = peer_name
            return
        raise ValueError(
            f"器件 {state.name} 的端口 {port} 已有连接 {existing}，不能再接 {peer_name}"
        )
    state.bindings[port] = peer_name


def resolve_port(cell: GraphCell, xy: tuple[float, float] | None) -> str | None:
    if not cell.points:
        return None
    if xy is None:
        return None
    best_idx = 0
    best_dist = float("inf")
    for idx, point in enumerate(cell.points):
        dist = (point[0] - xy[0]) ** 2 + (point[1] - xy[1]) ** 2
        if dist < best_dist:
            best_dist = dist
            best_idx = idx
    if best_dist > 0.04:
        return None
    return port_key_for_index(cell, best_idx)


def port_key_for_index(cell: GraphCell, index: int) -> str:
    kind = cell.drawclock_type or ""
    mux_match = MUX_KIND_RE.match(kind)
    if mux_match:
        num_inputs = int(mux_match.group(1))
        if index < num_inputs:
            return f"in{index}"
        return "out"
    if kind == "wire":
        if index == 0:
            return "left"
        return "right"
    if kind == "clock":
        return "left"
    if kind == "pll":
        if index == 0:
            return "left"
        return "right"
    if kind == "source":
        return "right"
    if index == 0:
        return "left"
    return "right"


def validate_topology(
    devices: dict[str, DeviceState],
    wire_by_name: dict[str, list[str]],
) -> None:
    errors: list[str] = []
    errors.extend(_duplicate_device_name_errors(devices))
    device_names = {s.name for s in devices.values() if s.kind != "wire"}
    wire_names = set(wire_by_name.keys())
    wire_endpoints = build_wire_endpoints(devices, wire_by_name)

    for wire_name, endpoints in wire_endpoints.items():
        errors.extend(_wire_endpoint_errors(wire_name, endpoints, device_names))

    for state in devices.values():
        if state.kind == "wire":
            continue

        required = _required_ports(state.kind)
        missing = required - set(state.bindings)
        extra = set(state.bindings) - required
        if state.kind == "pll":
            if "left" not in state.bindings:
                errors.append(f"器件 {state.name} 的输入端口未连接")
            if not state.out_targets and not _output_blocked_by_open_wire(
                state, wire_names, wire_endpoints
            ):
                errors.append(f"器件 {state.name} 的输出端口未连接")
            extra = extra | (set(state.bindings) - required)
        elif state.kind == "source":
            if not state.out_targets and not _output_blocked_by_open_wire(
                state, wire_names, wire_endpoints
            ):
                errors.append(f"器件 {state.name} 的输出端口未连接")
            extra = extra | (set(state.bindings) - required)
        elif missing:
            errors.append(f"器件 {state.name} 未连接的端口: {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"器件 {state.name} 存在未知端口连接: {', '.join(sorted(extra))}")
        for peer in state.bindings.values():
            if peer not in device_names and peer not in wire_names:
                errors.append(f"器件 {state.name} 连接到未知对象 {peer}")
        for peer in state.out_targets:
            if peer not in device_names and peer not in wire_names:
                errors.append(f"器件 {state.name} 连接到未知对象 {peer}")

    for wire_name, cell_ids in wire_by_name.items():
        merged_sources: list[str] = []
        for cell_id in cell_ids:
            state = devices.get(cell_id)
            if state is None:
                continue
            left = state.bindings.get("left")
            if left and left not in merged_sources:
                merged_sources.append(left)
        if len(merged_sources) > 1:
            errors.append(
                f"连线名 {wire_name} 左端合并后只能接一个器件，当前为 {len(merged_sources)} 个"
            )

    if errors:
        raise ValueError("\n".join(errors))


def _wire_endpoint_errors(
    wire_name: str,
    endpoints: WireEndpoints,
    device_names: set[str],
) -> list[str]:
    left = endpoints.left
    targets = list(endpoints.targets)
    errors: list[str] = []
    for peer in ([left] if left else []) + targets:
        if peer not in device_names:
            errors.append(f"连线 {wire_name} 连接到未知器件 {peer}")

    if not left and not targets:
        errors.append(f"连线 {wire_name} 两端均未连接器件")
        return errors
    if left and not targets:
        errors.append(f"连线 {wire_name} 左端接了器件 {left}，右端未连接任何器件")
        return errors
    if targets and not left:
        joined = "、".join(targets)
        errors.append(f"连线 {wire_name} 左端未接上游器件（右端接了 {joined}）")
    return errors


def _output_blocked_by_open_wire(
    state: DeviceState,
    wire_names: set[str],
    wire_endpoints: dict[str, WireEndpoints],
) -> bool:
    for peer in state.out_targets:
        if peer in wire_names and not wire_endpoints[peer].targets:
            return True
    return False


def _duplicate_device_name_errors(devices: dict[str, DeviceState]) -> list[str]:
    first_kind: dict[str, str] = {}
    errors: list[str] = []
    for state in devices.values():
        if state.kind == "wire":
            continue
        prior = first_kind.get(state.name)
        if prior is not None:
            errors.append(
                f"器件名 {state.name} 重复（{prior} 与 {state.kind}），除 wire 外名称须唯一"
            )
        else:
            first_kind[state.name] = state.kind
    return errors


def _required_ports(kind: str) -> set[str]:
    mux_match = MUX_KIND_RE.match(kind)
    if mux_match:
        n = int(mux_match.group(1))
        return {*(f"in{i}" for i in range(n)), "out"}
    if kind == "clock":
        return {"left"}
    if kind == "pll":
        return {"left"}
    if kind == "source":
        return set()
    if kind == "wire":
        return {"left", "right"}
    return {"left", "right"}
