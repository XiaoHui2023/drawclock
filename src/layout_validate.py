from __future__ import annotations

from typing import Any

from drawio_layout import LayoutDocument, VertexLayout


def validate_layout_matches_config(
    layout: LayoutDocument,
    config: dict[str, dict[str, Any]],
) -> None:
    errors: list[str] = []
    layout_names = {vertex.name for vertex in layout.vertices}
    config_device_names: set[str] = set()
    config_from_names: set[str] = set()

    for name, item in config.items():
        if item.get("kind") == "from":
            config_from_names.add(name)
            continue
        config_device_names.add(name)

    config_names = config_device_names | config_from_names
    missing_in_layout = sorted(config_names - layout_names)
    if missing_in_layout:
        errors.append(f"布局 JSON 缺少器件或连线: {', '.join(missing_in_layout)}")

    extra_in_layout = sorted(layout_names - config_names)
    if extra_in_layout:
        errors.append(f"布局 JSON 存在配置中未出现的名称: {', '.join(extra_in_layout)}")

    by_name: dict[str, VertexLayout] = {}
    for vertex in layout.vertices:
        prior = by_name.get(vertex.name)
        if prior is not None and vertex.drawclock_type != "from":
            errors.append(f"布局中器件名 {vertex.name} 重复")
            continue
        if prior is None:
            by_name[vertex.name] = vertex
    for name, item in config.items():
        vertex = by_name.get(name)
        if vertex is None:
            continue
        if item.get("kind") == "from":
            if vertex.drawclock_type != "from":
                errors.append(f"{name} 在配置中为 from，但布局类型为 {vertex.drawclock_type}")
            continue
        expected_kind = item.get("kind", "")
        if vertex.drawclock_type != expected_kind:
            errors.append(
                f"{name} 的类型不一致: 配置 {expected_kind}，布局 {vertex.drawclock_type}"
            )

    if errors:
        raise ValueError("\n".join(errors))
