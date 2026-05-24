from __future__ import annotations

import base64
import urllib.parse
import xml.etree.ElementTree as ET
import zlib


def xml_attr(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def compress_drawio_xml(text: str) -> str:
    """Encode XML the same way draw.io exports mxlibrary entries."""
    quoted = urllib.parse.quote(text, safe="()*-._~").encode("utf-8")
    compressor = zlib.compressobj(level=9, wbits=-15)
    payload = compressor.compress(quoted) + compressor.flush()
    return base64.b64encode(payload).decode("ascii")


def decompress_drawio_xml(data: str) -> str:
    infl = zlib.decompressobj(wbits=-15)
    return urllib.parse.unquote(infl.decompress(base64.b64decode(data)) + infl.flush())


def graph_root(model_root: ET.Element) -> ET.Element:
    if model_root.tag == "mxGraphModel":
        inner = model_root.find("root")
        return inner if inner is not None else model_root
    return model_root
