import sys

from drawio_lib.components.colored_cell_shared import register_colored_cell
from drawio_lib.components.simple_shapes import bist_clk_cell_body

register_colored_cell(
    sys.modules[__name__],
    title="bist_clk_cell",
    fill="#b3ffb3",
    tags="bist_clk_cell cell clock drawclock",
    body_svg=bist_clk_cell_body,
)
