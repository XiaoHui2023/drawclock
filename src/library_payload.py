from __future__ import annotations

import base64
import urllib.parse
import zlib


def decompress_diagram_payload(data: str) -> str:
    infl = zlib.decompressobj(wbits=-15)
    raw = infl.decompress(base64.b64decode(data)) + infl.flush()
    return urllib.parse.unquote(raw.decode("utf-8"))


def compress_diagram_payload(model_xml: str) -> str:
    """Encode mxGraphModel XML the way draw.io stores compressed diagrams."""
    quoted = urllib.parse.quote(model_xml)
    compressor = zlib.compressobj(level=9, wbits=-15)
    raw = compressor.compress(quoted.encode("utf-8")) + compressor.flush()
    return base64.b64encode(raw).decode("ascii")
