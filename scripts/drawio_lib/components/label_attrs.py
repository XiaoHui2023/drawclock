from __future__ import annotations

ATTR_NAME = "name"

INSTANCE_NAME_GAP_PX = 0
INSTANCE_NAME_GAP_LOOSE_PX = 4
LABEL_FONT_PX = 11


def verify_label_placeholders(html: str, *, title: str) -> None:
    if f"%{ATTR_NAME}%</text>" in html:
        raise ValueError(f"{title} instance name must not be SVG text")
    if 'preserveAspectRatio="none"' not in html:
        raise ValueError(f"{title} body SVG must stretch with the shape for port alignment")


def base_object_attrs(*, name: str) -> list[tuple[str, str]]:
    return [(ATTR_NAME, name)]
