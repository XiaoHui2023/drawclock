from __future__ import annotations

from typing import Any

from drawio_layout import LayoutDocument, VertexLayout


def validate_layout_matches_config(
    layout: LayoutDocument,
    config: dict[str, dict[str, Any]],
) -> None:
    errors: list[str] = []
    logical_names = {
        vertex.logical_name or vertex.name for vertex in layout.vertices
    }
    config_names = set(config)
    root_names = {
        name for name, item in config.items() if not item.get("source")
    }
    missing_in_layout = sorted(config_names - logical_names)
    if missing_in_layout:
        errors.append(f"布局 JSON 缺少器件或连线: {', '.join(missing_in_layout)}")

    extra_in_layout = sorted(logical_names - config_names)
    if extra_in_layout:
        errors.append(f"布局 JSON 存在配置中未出现的名称: {', '.join(extra_in_layout)}")

    by_name: dict[str, VertexLayout] = {}
    for vertex in layout.vertices:
        logical_name = vertex.logical_name or vertex.name
        prior = by_name.get(logical_name)
        if vertex.logical_name is not None and logical_name not in root_names:
            errors.append(f"布局中非源器件 {logical_name} 存在显示副本")
            continue
        if prior is not None and logical_name not in root_names:
            errors.append(f"布局中器件名 {logical_name} 重复")
            continue
        if prior is None:
            by_name[logical_name] = vertex
    for name, item in config.items():
        vertex = by_name.get(name)
        if vertex is None:
            continue
        expected_kind = item.get("kind", "")
        layout_kind = vertex.object_attrs.get("kind") or vertex.drawclock_type
        if layout_kind != expected_kind:
            errors.append(
                f"{name} 的类型不一致: 配置 {expected_kind}，布局 {layout_kind}"
            )

    if errors:
        raise ValueError("\n".join(errors))
