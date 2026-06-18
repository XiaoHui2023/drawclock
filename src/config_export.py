from __future__ import annotations

from typing import Any

from device_model import DeviceState, MUX_KIND_RE, PLL_EXPORT_KINDS, device_output_count
from drawio_library import DEFAULT_PLL_KIND
from wire_resolve import (
    build_wire_endpoints,
    format_upstream_source,
    mux_source_entry,
    output_counts_by_name,
    wire_left_out_ports,
)


def export_kind(drawclock_type: str) -> str:
    if MUX_KIND_RE.match(drawclock_type):
        return "mux"
    if drawclock_type == "pll2":
        return "pll"
    return drawclock_type


def devices_to_config(
    devices: dict[str, DeviceState],
    wire_by_name: dict[str, list[str]],
) -> list[dict[str, Any]]:
    wire_endpoints = build_wire_endpoints(devices, wire_by_name)
    wire_names = set(wire_by_name.keys())
    wire_out_ports = wire_left_out_ports(devices, wire_by_name)
    output_counts = output_counts_by_name(devices)
    entries: list[dict[str, Any]] = []

    for state in devices.values():
        if state.kind == "wire":
            continue
        entries.append(
            _device_entry(
                state,
                wire_names=wire_names,
                wire_endpoints=wire_endpoints,
                wire_out_ports=wire_out_ports,
                output_counts=output_counts,
            )
        )

    entries.sort(key=lambda item: item["name"])
    return entries


def entries_to_clock_tree(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """将带 name 的列表记录转为以 name 为键、值不含 name 的对象。"""
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
    wire_names: set[str],
    wire_endpoints: dict,
    wire_out_ports: dict[str, str | None],
    output_counts: dict[str, int],
) -> str | None:
    return format_upstream_source(
        peer,
        direct_out_port=direct_out_port,
        wire_names=wire_names,
        wire_endpoints=wire_endpoints,
        wire_out_ports=wire_out_ports,
        output_counts=output_counts,
    )


def _device_entry(
    state: DeviceState,
    *,
    wire_names: set[str],
    wire_endpoints: dict,
    wire_out_ports: dict[str, str | None],
    output_counts: dict[str, int],
) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": state.name, "kind": export_kind(state.kind)}
    if state.kind == "clock" and state.freq:
        entry["freq"] = state.freq

    if MUX_KIND_RE.match(state.kind):
        raw_source = mux_source_entry(state)
        if raw_source:
            mux_match = MUX_KIND_RE.match(state.kind)
            assert mux_match is not None
            num_inputs = int(mux_match.group(1))
            entry["source"] = {}
            for index in range(num_inputs):
                port = f"in{index}"
                peer = state.bindings.get(port)
                if not peer:
                    continue
                resolved = _format_source(
                    peer,
                    direct_out_port=state.source_out_ports.get(port),
                    wire_names=wire_names,
                    wire_endpoints=wire_endpoints,
                    wire_out_ports=wire_out_ports,
                    output_counts=output_counts,
                )
                entry["source"][str(index)] = resolved or peer
        return entry

    if state.kind in PLL_EXPORT_KINDS:
        raw_kind = state.pll_kind or DEFAULT_PLL_KIND
        entry["pll_kind"] = raw_kind.lower()
        count = device_output_count(state.kind)
        if count > 1:
            entry["output_count"] = count
        if "left" in state.bindings:
            resolved = _format_source(
                state.bindings["left"],
                direct_out_port=state.source_out_ports.get("left"),
                wire_names=wire_names,
                wire_endpoints=wire_endpoints,
                wire_out_ports=wire_out_ports,
                output_counts=output_counts,
            )
            if resolved:
                entry["source"] = resolved
        return entry

    if state.kind == "source":
        return entry

    if state.kind == "clock":
        if "left" in state.bindings:
            resolved = _format_source(
                state.bindings["left"],
                direct_out_port=state.source_out_ports.get("left"),
                wire_names=wire_names,
                wire_endpoints=wire_endpoints,
                wire_out_ports=wire_out_ports,
                output_counts=output_counts,
            )
            if resolved:
                entry["source"] = resolved
        return entry

    if "left" in state.bindings:
        resolved = _format_source(
            state.bindings["left"],
            direct_out_port=state.source_out_ports.get("left"),
            wire_names=wire_names,
            wire_endpoints=wire_endpoints,
            wire_out_ports=wire_out_ports,
            output_counts=output_counts,
        )
        if resolved:
            entry["source"] = resolved
    count = device_output_count(state.kind)
    if count > 1 and state.kind not in PLL_EXPORT_KINDS:
        entry["output_count"] = count
    return entry
