from __future__ import annotations

from typing import Any


FREQUENCY_FIELDS = ("func_freq", "scan_freq", "bist_freq")


def collect_device_attr_errors(config: dict[str, dict[str, Any]]) -> list[str]:
    """收集各器件属性格式问题，供 validate_config 合并上报。"""
    errors: list[str] = []
    for name, item in config.items():
        kind = item.get("kind")
        if not isinstance(kind, str) or not kind.strip():
            errors.append(f"器件 {name} 缺少 kind")
        layout_column = item.get("layout_column")
        if layout_column is not None and (
            isinstance(layout_column, bool)
            or not isinstance(layout_column, int)
        ):
            errors.append(
                f"器件 {name} 的 layout_column 必须是整数"
            )
        for field in FREQUENCY_FIELDS:
            value = item.get(field)
            if field in item and (
                value is None
                or isinstance(value, bool)
                or not isinstance(value, (str, int, float))
            ):
                errors.append(
                    f"器件 {name} 的 {field} 必须是字符串或数字"
                )
    return errors


def validate_device_attrs(config: dict[str, dict[str, Any]]) -> None:
    """校验 clock-tree 条目中各器件属性；有问题时抛出 ValueError。"""
    errors = collect_device_attr_errors(config)
    if errors:
        raise ValueError("\n".join(errors))
