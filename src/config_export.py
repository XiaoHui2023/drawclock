from __future__ import annotations

from typing import Any

from device_model import DeviceState, MUX_KIND_RE
from wire_resolve import (
    build_wire_endpoints,
    mux_source_entry,
    resolve_input_peer,
    resolve_output_peers,
)


def export_kind(drawclock_type: str) -> str:
    if MUX_KIND_RE.match(drawclock_type):
        return "mux"
    return drawclock_type


def devices_to_config(
    devices: dict[str, DeviceState],
    wire_by_name: dict[str, list[str]],
) -> list[dict[str, Any]]:
    wire_endpoints = build_wire_endpoints(devices, wire_by_name)
    wire_names = set(wire_by_name.keys())
    entries: list[dict[str, Any]] = []

    for state in devices.values():
        if state.kind == "wire":
            continue
        entries.append(_device_entry(state, wire_names=wire_names, wire_endpoints=wire_endpoints))

    entries.sort(key=lambda item: item["name"])
    return entries


def _device_entry(
    state: DeviceState,
    *,
    wire_names: set[str],
    wire_endpoints: dict,
) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": state.name, "kind": export_kind(state.kind)}
    if state.kind == "clock" and state.freq:
        entry["freq"] = state.freq

    if MUX_KIND_RE.match(state.kind):
        raw_source = mux_source_entry(state)
        if raw_source:
            entry["source"] = {
                key: resolve_input_peer(
                    peer,
                    wire_names=wire_names,
                    wire_endpoints=wire_endpoints,
                )
                or peer
                for key, peer in sorted(raw_source.items())
            }
        if "out" in state.bindings:
            out_peer = state.bindings["out"]
            resolved = resolve_output_peers(
                [out_peer],
                wire_names=wire_names,
                wire_endpoints=wire_endpoints,
            )
            if len(resolved) == 1:
                entry["target"] = resolved[0]
        return entry

    if state.kind in ("pll", "source"):
        targets = resolve_output_peers(
            list(state.out_targets),
            wire_names=wire_names,
            wire_endpoints=wire_endpoints,
        )
        if targets:
            entry["targets"] = targets
        return entry

    if state.kind == "clock":
        if "left" in state.bindings:
            resolved = resolve_input_peer(
                state.bindings["left"],
                wire_names=wire_names,
                wire_endpoints=wire_endpoints,
            )
            if resolved:
                entry["source"] = resolved
        return entry

    if "left" in state.bindings:
        resolved = resolve_input_peer(
            state.bindings["left"],
            wire_names=wire_names,
            wire_endpoints=wire_endpoints,
        )
        if resolved:
            entry["source"] = resolved
    if "right" in state.bindings:
        resolved = resolve_output_peers(
            [state.bindings["right"]],
            wire_names=wire_names,
            wire_endpoints=wire_endpoints,
        )
        if len(resolved) == 1:
            entry["target"] = resolved[0]
    return entry
