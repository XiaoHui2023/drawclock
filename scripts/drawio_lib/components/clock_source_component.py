from __future__ import annotations

from dataclasses import dataclass

from drawio_lib.components.internal_kind import STYLE_SOURCE_KIND, variant_style_suffix
from drawio_lib.components.simple_component import SimpleComponent

SOURCE_MAJOR_KIND = "source"


@dataclass
class ClockSourceComponent(SimpleComponent):
    """Clock-source family; kind metadata lives in mxCell style for JSON export."""

    @property
    def json_kind(self) -> str:
        return SOURCE_MAJOR_KIND

    def cell_style(self) -> str:
        return (
            f"{super().cell_style()}"
            f"{variant_style_suffix(STYLE_SOURCE_KIND, self.drawclock_type)}"
        )
