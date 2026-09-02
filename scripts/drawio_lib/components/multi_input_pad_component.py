from __future__ import annotations

from dataclasses import dataclass

from drawio_lib.components.label_attrs import INSTANCE_NAME_GAP_LOOSE_PX, LABEL_FONT_PX
from drawio_lib.components.label_html import name_block, shell_close, shell_open, stretch_body_layer
from drawio_lib.components.mux_component import FILL, LABEL_INSET_X, STROKE, MuxComponent


@dataclass
class MultiInputPadComponent(MuxComponent):
    """A hollow rectangular input pad with N labeled inputs and one output."""

    @property
    def json_kind(self) -> str:
        return self.title

    def _body(self) -> str:
        return (
            f'<rect x="{self._t.x}" y="{self._t.y}" width="{self._t.w}" '
            f'height="{self._t.h}" fill="{FILL}" stroke="{STROKE}" '
            f'stroke-width="2"/>'
        )

    def label_html(self) -> str:
        overlays = tuple(
            (self._t.x + LABEL_INSET_X, port.trap.cell_y, str(index))
            for index, port in enumerate(self._g.inputs)
        ) + ((self._t.x + self._t.w - LABEL_INSET_X, self._g.out.trap.cell_y, "C"),)
        return (
            f"{shell_open(self.w, self.h)}"
            f"{stretch_body_layer(self._body(), view_w=self.w, view_h=self.graphic_h, overlays=overlays)}"
            f"{name_block(self._g.mux_h, design_cell_h=self.h, gap_px=INSTANCE_NAME_GAP_LOOSE_PX)}"
            f"{shell_close()}"
        )

    def preview_svg(self) -> str:
        name_y = self._g.mux_h + INSTANCE_NAME_GAP_LOOSE_PX + 7
        ports = []
        labels = []
        for index, port in enumerate(self._g.inputs):
            ports.append(
                f'  <circle cx="{port.trap.cell_x}" cy="{port.trap.cell_y}" r="2.5" fill="#c00"/>'
            )
            labels.append(
                f'  <text x="{self._t.x + LABEL_INSET_X}" y="{port.trap.cell_y}" '
                f'font-size="{LABEL_FONT_PX}" fill="{STROKE}">{index}</text>'
            )
        ports.append(
            f'  <circle cx="{self._g.out.trap.cell_x}" cy="{self._g.out.trap.cell_y}" r="2.5" fill="#090"/>'
        )
        labels.append(
            f'  <text x="{self._t.x + self._t.w - LABEL_INSET_X}" y="{self._g.out.trap.cell_y}" '
            f'font-size="{LABEL_FONT_PX}" fill="{STROKE}" text-anchor="end">C</text>'
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}">\n  {self._body()}\n'
            + "\n".join(ports + labels)
            + f'\n  <text x="{self.w // 2}" y="{name_y}" font-size="{LABEL_FONT_PX}" '
            f'fill="{STROKE}" text-anchor="middle">{self.title}</text>\n</svg>\n'
        )

    def verify_geometry(self) -> None:
        super().verify_geometry()
        html = self.label_html()
        if "<rect " not in html or "<polygon " in html or 'fill="none"' not in html:
            raise ValueError(f"{self.title}: multi-input pad must be a hollow rectangle")
        for label in (*map(str, range(self.num_inputs)), "C"):
            if f">{label}</span>" not in html:
                raise ValueError(f"{self.title}: missing port label {label}")
