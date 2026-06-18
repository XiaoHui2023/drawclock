import sys

from drawio_lib.components.async_marker_component import AsyncMarkerComponent, bind_module

_COMPONENT = AsyncMarkerComponent()

bind_module(sys.modules[__name__], _COMPONENT)
