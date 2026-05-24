from __future__ import annotations

from dataclasses import dataclass

from drawio_lib.components import (
    clock,
    div,
    dto,
    gate,
    inv,
    mux2,
    mux3,
    mux4,
    mux5,
    mux6,
    pll,
    wire,
)


@dataclass(frozen=True)
class ComponentSpec:
    """One draw.io library shape and its checks."""

    module: object


def library_entry(spec: ComponentSpec) -> dict[str, object]:
    return spec.module.library_entry()


def verify_geometry(spec: ComponentSpec) -> None:
    spec.module.verify_geometry()


def write_image_outputs(spec: ComponentSpec, images_dir) -> None:
    if hasattr(spec.module, "preview_svg"):
        images_dir.mkdir(parents=True, exist_ok=True)
        path = images_dir / f"{spec.module.TITLE}.svg"
        path.write_text(spec.module.preview_svg(), encoding="utf-8")


ALL: tuple[ComponentSpec, ...] = (
    ComponentSpec(mux2),
    ComponentSpec(mux3),
    ComponentSpec(mux4),
    ComponentSpec(mux5),
    ComponentSpec(mux6),
    ComponentSpec(gate),
    ComponentSpec(div),
    ComponentSpec(dto),
    ComponentSpec(inv),
    ComponentSpec(pll),
    ComponentSpec(clock),
    ComponentSpec(wire),
)
