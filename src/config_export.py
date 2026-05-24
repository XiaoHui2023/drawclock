from __future__ import annotations

from typing import Any

from device_model import DeviceState, MUX_KIND_RE


def export_kind(drawclock_type: str) -> str:
    if MUX_KIND_RE.match(drawclock_type):
        return "mux"
    return drawclock_type


def devices_to_config(
    devices: dict[str, DeviceState],
    wire_by_name: dict[str, list[str]],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen_wire_names: set[str] = set()

    for state in devices.values():
        if state.kind == "wire":
            continue
        entries.append(_device_entry(state))

    for wire_name, cell_ids in sorted(wire_by_name.items()):
        if wire_name in seen_wire_names:
            continue
        seen_wire_names.add(wire_name)
        connections: list[str] = []
        for cell_id in cell_ids:
            state = devices.get(cell_id)
            if state is None:
                continue
            for peer in state.bindings.values():
                if peer not in connections:
                    connections.append(peer)
        entries.append(
            {"name": wire_name, "kind": "wire", "connections": connections}
        )

    entries.sort(key=lambda item: (item.get("connections") is None, item["name"]))
    return entries


def _device_entry(state: DeviceState) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": state.name, "kind": export_kind(state.kind)}
    if state.kind == "clock" and state.freq:
        entry["freq"] = state.freq

    if MUX_KIND_RE.match(state.kind):
        source: dict[str, str] = {}
        for key, peer in sorted(state.bindings.items()):
            if key.startswith("in"):
                source[key] = peer
        if source:
            entry["source"] = source
        if "out" in state.bindings:
            entry["target"] = state.bindings["out"]
        return entry

    if state.kind == "pll":
        if "right" in state.bindings:
            entry["target"] = state.bindings["right"]
        return entry

    if state.kind == "clock":
        if "left" in state.bindings:
            entry["source"] = state.bindings["left"]
        return entry

    if "left" in state.bindings:
        entry["source"] = state.bindings["left"]
    if "right" in state.bindings:
        entry["target"] = state.bindings["right"]
    return entry
