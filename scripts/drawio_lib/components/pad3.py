import sys

from drawio_lib.components.multi_input_pad_component import MultiInputPadComponent
from drawio_lib.components.mux_component import bind_module


_COMPONENT = MultiInputPadComponent(
    num_inputs=3,
    title="pad3",
    tags="pad input aggregate three input drawclock",
)

bind_module(sys.modules[__name__], _COMPONENT)
