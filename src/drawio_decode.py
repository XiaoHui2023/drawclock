from __future__ import annotations

import base64
import html
import re
import urllib.parse
import xml.etree.ElementTree as ET
import zlib


def decompress_diagram_payload(data: str) -> str:
    infl = zlib.decompressobj(wbits=-15)
    raw = infl.decompress(base64.b64decode(data)) + infl.flush()
    return urllib.parse.unquote(raw.decode("utf-8"))


def extract_mxfile_xml(path: str) -> str:
    text = open(path, encoding="utf-8").read()
    lower = path.lower()
    if lower.endswith(".drawio.svg") or (lower.endswith(".svg") and "mxfile" in text):
        return _mxfile_from_svg(text)
    if lower.endswith(".drawio") or lower.endswith(".xml"):
        return _normalize_drawio_file(text)
    raise ValueError(f"不支持的输入格式: {path}")


def _mxfile_from_svg(svg_text: str) -> str:
    match = re.search(r'content="([^"]*)"', svg_text, flags=re.DOTALL)
    if not match:
        raise ValueError("SVG 中未找到 draw.io 的 content 属性")
    content = html.unescape(match.group(1))
    if "<mxfile" not in content:
        raise ValueError("content 中不是 mxfile 结构")
    return content


def _normalize_drawio_file(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("<mxfile"):
        return stripped
    if stripped.startswith("<mxGraphModel"):
        return f"<mxfile><diagram>{stripped}</diagram></mxfile>"
    raise ValueError("文件不是 mxfile 或 mxGraphModel")


def iter_diagram_models(mxfile_xml: str) -> list[ET.Element]:
    root = ET.fromstring(mxfile_xml)
    models: list[ET.Element] = []
    for diagram in root.findall("diagram"):
        child_model = diagram.find("mxGraphModel")
        if child_model is not None:
            models.append(child_model)
            continue
        payload = (diagram.text or "").strip()
        if not payload:
            continue
        if payload.startswith("<"):
            model = ET.fromstring(payload)
        else:
            model = ET.fromstring(decompress_diagram_payload(payload))
        if model.tag == "mxGraphModel":
            models.append(model)
        else:
            inner = model.find("mxGraphModel")
            if inner is not None:
                models.append(inner)
    if not models and root.tag == "mxGraphModel":
        models.append(root)
    return models
