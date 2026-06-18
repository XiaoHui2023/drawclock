from __future__ import annotations

from typing import Any

from device_attrs_validate import collect_device_attr_errors
from wire_resolve import parse_source_ref


def validate_config(config: dict[str, dict[str, Any]]) -> None:
    errors: list[str] = []
    errors.extend(collect_device_attr_errors(config))
    device_names = set(config.keys())

    for name, item in config.items():
        kind = item.get("kind")
        if kind == "wire":
            errors.append("clock-tree.json 不应包含 kind 为 wire 的记录")
            continue

        if "target" in item or "targets" in item:
            errors.append(f"器件 {name} 不应包含 target 或 targets")

        refs = _referenced_peers(item)
        for peer in refs:
            base, index = parse_source_ref(peer)
            if base not in device_names:
                errors.append(f"器件 {name} 连接到未知器件 {peer}")
                continue
            if index is not None:
                upstream = config[base]
                if upstream.get("kind") != "pll":
                    errors.append(f"器件 {name} 的 source {peer} 指向非 pll 器件 {base}")
                    continue
                output_count = upstream.get("output_count", 1)
                if index >= output_count:
                    errors.append(
                        f"器件 {name} 的 source {peer} 超出 {base} 的 output_count={output_count}"
                    )

        if isinstance(item.get("source"), dict):
            _validate_mux(name, item, errors)
            continue

        if kind == "source":
            continue

        if kind == "pll":
            if not item.get("source"):
                errors.append(f"器件 {name} 的输入端口未连接")
            output_count = item.get("output_count")
            if output_count is not None and (
                not isinstance(output_count, int) or output_count <= 1
            ):
                errors.append(f"器件 {name} 的 output_count 应为大于 1 的整数")
            continue

        if "freq" in item or kind in ("gate", "div", "cell", "dto", "inv", "clock"):
            if not item.get("source"):
                errors.append(f"器件 {name} 的输入端口未连接")

    if errors:
        raise ValueError("\n".join(errors))


def _referenced_peers(item: dict[str, Any]) -> list[str]:
    peers: list[str] = []
    source = item.get("source")
    if isinstance(source, dict):
        peers.extend(v for v in source.values() if isinstance(v, str))
    elif isinstance(source, str):
        peers.append(source)
    return peers


def _validate_mux(name: str, item: dict[str, Any], errors: list[str]) -> None:
    source = item.get("source")
    if not isinstance(source, dict) or not source:
        errors.append(f"器件 {name} 的 mux 输入未全部连接")
