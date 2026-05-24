from __future__ import annotations

from drawio_graph import GraphCell, ParsedDiagram, edge_attachment
from device_model import DeviceState, MUX_KIND_RE


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
            mux_labels=dict(cell.mux_labels),
            points=cell.points,
        )

    wire_cells = [
        c for c in diagram.cells.values() if not c.is_edge and c.drawclock_type == "wire"
    ]
    wire_by_name: dict[str, list[str]] = {}
    for cell in wire_cells:
        wire_by_name.setdefault(cell.name, []).append(cell.cell_id)

    for edge in diagram.cells.values():
        if not edge.is_edge or not edge.source_id or not edge.target_id:
            continue
        src = diagram.cells.get(edge.source_id)
        tgt = diagram.cells.get(edge.target_id)
        if not src or not tgt or src.is_edge or tgt.is_edge:
            continue
        exit_xy = edge_attachment(edge.style, end="exit")
        entry_xy = edge_attachment(edge.style, end="entry")
        _bind_endpoint(devices, wire_by_name, src, exit_xy, tgt.name, outgoing=True)
        _bind_endpoint(devices, wire_by_name, tgt, entry_xy, src.name, outgoing=False)

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
) -> None:
    if cell.drawclock_type == "wire":
        port = resolve_port(cell, xy)
        if port is None:
            port = "left" if not outgoing else "right"
        devices.setdefault(
            cell.cell_id,
            DeviceState(kind="wire", name=cell.name, points=cell.points),
        )
        devices[cell.cell_id].bindings[port] = peer_name
        return

    state = devices.get(cell.cell_id)
    if state is None:
        return
    port = resolve_port(cell, xy)
    if port is None:
        port = "right" if outgoing else "left"
    if port in state.bindings:
        raise ValueError(
            f"器件 {state.name} 的端口 {port} 已有连接 {state.bindings[port]}，不能再接 {peer_name}"
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

    for state in devices.values():
        if state.kind == "wire":
            peers = list(state.bindings.values())
            if not peers:
                errors.append(f"连线 {state.name} 的图形未连接任何器件")
            elif len(peers) > 2:
                errors.append(f"连线 {state.name} 的一个图形连接了超过 2 个端口")
            for peer in peers:
                if peer not in device_names:
                    errors.append(f"连线 {state.name} 连接到未知器件 {peer}")
            continue

        required = _required_ports(state.kind)
        missing = required - set(state.bindings)
        extra = set(state.bindings) - required
        if missing:
            errors.append(f"器件 {state.name} 未连接的端口: {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"器件 {state.name} 存在未知端口连接: {', '.join(sorted(extra))}")
        for peer in state.bindings.values():
            if peer not in device_names and peer not in wire_names:
                errors.append(f"器件 {state.name} 连接到未知对象 {peer}")

    for wire_name, cell_ids in wire_by_name.items():
        merged: list[str] = []
        for cell_id in cell_ids:
            state = devices.get(cell_id)
            if state is None:
                continue
            for peer in state.bindings.values():
                if peer not in merged:
                    merged.append(peer)
        if len(merged) not in (1, 2):
            errors.append(
                f"连线名 {wire_name} 合并后应对接 1 或 2 个器件，当前为 {len(merged)} 个"
            )

    if errors:
        raise ValueError("\n".join(errors))


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
        return {"right"}
    if kind == "wire":
        return {"left", "right"}
    return {"left", "right"}
