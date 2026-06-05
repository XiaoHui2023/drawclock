from __future__ import annotations

import re
from dataclasses import dataclass

from device_model import DeviceState, MUX_KIND_RE, device_output_count, out_port_index

SOURCE_REF_RE = re.compile(r"^(.+)\[(\d+)\]$")


@dataclass(frozen=True)
class WireEndpoints:
    left: str | None
    targets: tuple[str, ...]


def build_wire_endpoints(
    devices: dict[str, DeviceState],
    wire_by_name: dict[str, list[str]],
) -> dict[str, WireEndpoints]:
    device_names = {s.name for s in devices.values() if s.kind != "wire"}
    out: dict[str, WireEndpoints] = {}
    for wire_name, cell_ids in wire_by_name.items():
        sources: list[str] = []
        targets: list[str] = []
        for cell_id in cell_ids:
            state = devices.get(cell_id)
            if state is None:
                continue
            left = state.bindings.get("left")
            if left and left not in sources:
                sources.append(left)
            for peer in state.wire_targets:
                if peer not in targets:
                    targets.append(peer)
        left_peer = sources[0] if len(sources) == 1 else None
        resolved_targets = tuple(
            peer for peer in targets if peer in device_names
        )
        out[wire_name] = WireEndpoints(left=left_peer, targets=resolved_targets)
    return out


def _is_wire(peer: str, wire_names: set[str]) -> bool:
    return peer in wire_names


def resolve_input_peer(
    peer: str,
    *,
    wire_names: set[str],
    wire_endpoints: dict[str, WireEndpoints],
) -> str | None:
    if not _is_wire(peer, wire_names):
        return peer
    left = wire_endpoints[peer].left
    if left is None or _is_wire(left, wire_names):
        return None
    return left


def wire_left_out_ports(
    devices: dict[str, DeviceState],
    wire_by_name: dict[str, list[str]],
) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for wire_name, cell_ids in wire_by_name.items():
        port: str | None = None
        for cell_id in cell_ids:
            state = devices.get(cell_id)
            if state is not None and state.wire_left_out_port:
                port = state.wire_left_out_port
                break
        out[wire_name] = port
    return out


def output_counts_by_name(devices: dict[str, DeviceState]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for state in devices.values():
        if state.kind == "wire":
            continue
        count = device_output_count(state.kind)
        if count:
            counts[state.name] = count
    return counts


def format_upstream_source(
    peer: str,
    *,
    direct_out_port: str | None,
    wire_names: set[str],
    wire_endpoints: dict[str, WireEndpoints],
    wire_out_ports: dict[str, str | None],
    output_counts: dict[str, int],
) -> str | None:
    out_port = direct_out_port
    if _is_wire(peer, wire_names):
        out_port = wire_out_ports.get(peer) or out_port
        peer = resolve_input_peer(
            peer,
            wire_names=wire_names,
            wire_endpoints=wire_endpoints,
        )
    if peer is None:
        return None
    count = output_counts.get(peer, 1)
    index = out_port_index(out_port) if out_port else None
    if count <= 1 or index is None:
        return peer
    if index >= count:
        raise ValueError(f"上游器件 {peer} 的输出序号 [{index}] 超出 output_count={count}")
    return f"{peer}[{index}]"


def parse_source_ref(ref: str) -> tuple[str, int | None]:
    match = SOURCE_REF_RE.match(ref)
    if not match:
        return ref, None
    return match.group(1), int(match.group(2))


def resolve_output_peers(
    peers: list[str],
    *,
    wire_names: set[str],
    wire_endpoints: dict[str, WireEndpoints],
) -> list[str]:
    out: list[str] = []
    for peer in peers:
        if _is_wire(peer, wire_names):
            for target in wire_endpoints[peer].targets:
                if target not in out:
                    out.append(target)
        elif peer not in out:
            out.append(peer)
    return out


def mux_source_entry(state: DeviceState) -> dict[str, str]:
    source: dict[str, str] = {}
    mux_match = MUX_KIND_RE.match(state.kind)
    if not mux_match:
        return source
    num_inputs = int(mux_match.group(1))
    for index in range(num_inputs):
        port = f"in{index}"
        peer = state.bindings.get(port)
        if not peer:
            continue
        source[str(index)] = peer
    return source
