from __future__ import annotations

from dataclasses import dataclass

from drawio_lib.components import (
    and_gate,
    async_marker,
    bist_clk_cell,
    buffer,
    clk_phase_sel,
    clock,
    div,
    div_gate,
    div_n,
    dto,
    dto_n,
    gate,
    gen_cell,
    inv,
    inv_mux,
    mux2,
    mux3,
    mux4,
    mux5,
    mux6,
    nand,
    nor,
    occ_bist_clk_cell,
    occ_clk_cell,
    or_gate,
    pll,
    pll2,
    source,
    wire,
    xnor,
    xor_gate,
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
    ComponentSpec(div_n),
    ComponentSpec(div_gate),
    ComponentSpec(dto),
    ComponentSpec(dto_n),
    ComponentSpec(inv),
    ComponentSpec(inv_mux),
    ComponentSpec(clk_phase_sel),
    ComponentSpec(occ_clk_cell),
    ComponentSpec(gen_cell),
    ComponentSpec(bist_clk_cell),
    ComponentSpec(occ_bist_clk_cell),
    ComponentSpec(async_marker),
    ComponentSpec(and_gate),
    ComponentSpec(nand),
    ComponentSpec(buffer),
    ComponentSpec(or_gate),
    ComponentSpec(xnor),
    ComponentSpec(nor),
    ComponentSpec(xor_gate),
    ComponentSpec(pll),
    ComponentSpec(pll2),
    ComponentSpec(source),
    ComponentSpec(clock),
    ComponentSpec(wire),
)
