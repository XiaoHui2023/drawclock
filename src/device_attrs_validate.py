from __future__ import annotations

from typing import Any

from css_color import parse_css_color


FREQUENCY_FIELDS = ("func_freq", "scan_freq", "bist_freq")
DESCRIPTION_FIELD = "description"
DESCRIPTION_COLOR_FIELD = "description_color"


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
        description = item.get(DESCRIPTION_FIELD)
        if DESCRIPTION_FIELD in item and not isinstance(description, str):
            errors.append(f"器件 {name} 的 description 必须是字符串")
        description_color = item.get(DESCRIPTION_COLOR_FIELD)
        if DESCRIPTION_COLOR_FIELD in item:
            if not isinstance(description_color, str):
                errors.append(f"器件 {name} 的 description_color 必须是字符串")
            elif not isinstance(description, str) or not description:
                errors.append(
                    f"器件 {name} 只有填写 description 后才能使用 description_color"
                )
            else:
                try:
                    parse_css_color(description_color)
                except ValueError as error:
                    errors.append(
                        f"器件 {name} 的 description_color 无效: {error}"
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
