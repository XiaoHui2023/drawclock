from __future__ import annotations

from dataclasses import dataclass

from drawio_lib.components.internal_kind import STYLE_INV_KIND, variant_style_suffix
from drawio_lib.components.simple_component import SimpleComponent

INV_MAJOR_KIND = "inv"


@dataclass
class InvComponent(SimpleComponent):
    """Inverter family; kind metadata lives in mxCell style for JSON export."""

    @property
    def json_kind(self) -> str:
        return INV_MAJOR_KIND

    def cell_style(self) -> str:
        return (
            f"{super().cell_style()}"
            f"{variant_style_suffix(STYLE_INV_KIND, self.drawclock_type)}"
        )
