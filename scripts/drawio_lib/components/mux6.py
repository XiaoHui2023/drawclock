import sys

from drawio_lib.components.mux_component import MuxComponent, bind_module

_COMPONENT = MuxComponent(
    num_inputs=6,
    title="mux6",
    tags="mux6 mux clock drawclock",
)

bind_module(sys.modules[__name__], _COMPONENT)
