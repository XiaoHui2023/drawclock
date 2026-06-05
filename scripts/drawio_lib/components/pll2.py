import sys

from drawio_lib.components.pll2_component import Pll2Component, bind_module

_COMPONENT = Pll2Component()

bind_module(sys.modules[__name__], _COMPONENT)
