from __future__ import annotations

from typing import Any


def validate_config(entries: list[dict[str, Any]]) -> None:
    errors: list[str] = []
    seen_devices: set[str] = set()
    wire_names: set[str] = set()
    for item in entries:
        name = item["name"]
        if "connections" in item:
            wire_names.add(name)
            continue
        if name in seen_devices:
            errors.append(f"器件名 {name} 重复，除 wire 外名称须唯一")
        else:
            seen_devices.add(name)
    device_names = seen_devices

    for item in entries:
        name = item["name"]
        if "connections" in item:
            conns = item["connections"]
            if not isinstance(conns, list):
                errors.append(f"连线 {name} 的 connections 必须是列表")
                continue
            if len(conns) not in (1, 2):
                errors.append(f"连线 {name} 的 connections 长度须为 1 或 2，当前为 {len(conns)}")
            for peer in conns:
                if peer not in device_names:
                    errors.append(f"连线 {name} 连接到未知器件 {peer}")
            continue

        refs = _referenced_peers(item)
        for peer in refs:
            if peer not in device_names and peer not in wire_names:
                errors.append(f"器件 {name} 连接到未知对象 {peer}")

        if isinstance(item.get("source"), dict):
            _validate_mux(name, item, errors)
            continue

        if "freq" in item:
            if "source" not in item:
                errors.append(f"器件 {name} 的输入端口未连接")
            if "target" in item:
                errors.append(f"器件 {name} 不应有 target")
            continue

        if "target" in item and "source" not in item:
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
        peers.extend(source.values())
    elif isinstance(source, str):
        peers.append(source)
    target = item.get("target")
    if isinstance(target, str):
        peers.append(target)
    return peers


def _validate_mux(name: str, item: dict[str, Any], errors: list[str]) -> None:
    source = item.get("source")
    if not isinstance(source, dict) or not source:
        errors.append(f"器件 {name} 的 mux 输入未全部连接")
    if "target" not in item:
        errors.append(f"器件 {name} 的输出端口未连接")
