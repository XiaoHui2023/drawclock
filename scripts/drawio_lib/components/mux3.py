import sys

from drawio_lib.components.mux_component import MuxComponent, bind_module

_COMPONENT = MuxComponent(
    num_inputs=3,
    title="mux3",
    tags="mux3 mux clock drawclock",
)

bind_module(sys.modules[__name__], _COMPONENT)
