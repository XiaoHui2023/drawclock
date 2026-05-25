from __future__ import annotations

from typing import Any


def validate_config(entries: list[dict[str, Any]]) -> None:
    errors: list[str] = []
    seen_devices: set[str] = set()
    for item in entries:
        name = item["name"]
        kind = item.get("kind")
        if kind == "wire":
            errors.append("clock-tree.json 不应包含 kind 为 wire 的记录")
            continue
        if name in seen_devices:
            errors.append(f"器件名 {name} 重复")
        else:
            seen_devices.add(name)
    device_names = seen_devices

    for item in entries:
        name = item["name"]
        kind = item.get("kind")
        if kind == "wire":
            continue

        refs = _referenced_peers(item)
        for peer in refs:
            if peer not in device_names:
                errors.append(f"器件 {name} 连接到未知器件 {peer}")

        if isinstance(item.get("source"), dict):
            _validate_mux(name, item, errors)
            continue

        if kind in ("pll", "source"):
            if "target" in item:
                errors.append(f"器件 {name} 应使用 targets 而非 target")
            targets = item.get("targets")
            if not isinstance(targets, list) or not targets:
                errors.append(f"器件 {name} 的输出端口未连接")
            continue

        if "freq" in item:
            if "source" not in item:
                errors.append(f"器件 {name} 的输入端口未连接")
            if "target" in item:
                errors.append(f"器件 {name} 不应有 target")
            continue

        if "source" in item and "target" not in item:
            errors.append(f"器件 {name} 的输出端口未连接")
            continue

        if "source" not in item:
            errors.append(f"器件 {name} 的输入端口未连接")
        if "target" not in item:
            errors.append(f"器件 {name} 的输出端口未连接")

    if errors:
        raise ValueError("\n".join(errors))


def _referenced_peers(item: dict[str, Any]) -> list[str]:
    peers: list[str] = []
    source = item.get("source")
    if isinstance(source, dict):
        peers.extend(v for v in source.values() if isinstance(v, str))
    elif isinstance(source, str):
        peers.append(source)
    target = item.get("target")
    if isinstance(target, str):
        peers.append(target)
    targets = item.get("targets")
    if isinstance(targets, list):
        peers.extend(t for t in targets if isinstance(t, str))
    return peers


def _validate_mux(name: str, item: dict[str, Any], errors: list[str]) -> None:
    source = item.get("source")
    if not isinstance(source, dict) or not source:
        errors.append(f"器件 {name} 的 mux 输入未全部连接")
    if "target" not in item:
        errors.append(f"器件 {name} 的输出端口未连接")
