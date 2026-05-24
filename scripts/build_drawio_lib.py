"""Generate draw.io library XML for drawclock components.

Implementation lives under scripts/drawio_lib/ (one file per component in components/).
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from drawio_lib.build import main, verify_outputs
from drawio_lib.validate import validate_drawio_graph_xml
from drawio_lib.xml_io import decompress_drawio_xml

# Backward-compatible names for tests and old imports.
ROOT = Path(__file__).resolve().parents[1]
LIB_DIR = ROOT / "drawio-lib"

__all__ = [
    "decompress_drawio_xml",
    "main",
    "validate_drawio_graph_xml",
    "verify_outputs",
]

if __name__ == "__main__":
    main()
