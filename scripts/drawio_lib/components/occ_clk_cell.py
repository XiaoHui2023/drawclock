import sys

from drawio_lib.components.colored_cell_shared import register_colored_cell
from drawio_lib.components.simple_shapes import occ_clk_cell_body

register_colored_cell(
    sys.modules[__name__],
    title="occ_clk_cell",
    fill="#b3d9ff",
    tags="occ_clk_cell cell clock drawclock",
    body_svg=occ_clk_cell_body,
)
