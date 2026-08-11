from __future__ import annotations

import shutil
import subprocess
import tempfile
import math
import re
from pathlib import Path

from drawio_graph import edge_attachment
from drawio_build import junction_points
from drawio_layout import LayoutDocument
from drawio_ports import abs_port_xy, port_anchors

# draw.io places an html=1 label's content origin 2 px right and 7 px below
# mxGeometry.  The component library deliberately applies the inverse offset
# to its graphic layer.  Native SVG previews must reproduce the outer offset,
# otherwise the visible symbol and the mathematically routed ports diverge.
HTML_LABEL_CONTENT_OFFSET_X = 2.0
HTML_LABEL_CONTENT_OFFSET_Y = 7.0


def build_preview_svg(
    document: LayoutDocument,
    *,
    title: str = "drawclock",
    crossing_style: str = "gap",
) -> str:
    if not document.vertices:
        raise ValueError("布局中没有器件")
    by_id = {vertex.cell_id: vertex for vertex in document.vertices}
    pad = 45.0
    min_x = min(vertex.x for vertex in document.vertices) - pad
    min_y = min(vertex.y for vertex in document.vertices) - pad
    max_x = max(vertex.x + vertex.width for vertex in document.vertices) + pad
    max_y = max(vertex.y + vertex.height for vertex in document.vertices) + pad
    width = max_x - min_x
    height = max_y - min_y
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xhtml="http://www.w3.org/1999/xhtml" '
            f'viewBox="{min_x:g} {min_y:g} {width:g} {height:g}" '
            f'width="{width:g}" height="{height:g}">'
        ),
        "<style>.edge-gap{fill:none;stroke:#fff;stroke-width:6;stroke-linejoin:round}.edge{fill:none;stroke:#20252b;stroke-width:1.6;stroke-linejoin:round;stroke-linecap:square}</style>",
        f'<rect x="{min_x:g}" y="{min_y:g}" width="{width:g}" height="{height:g}" fill="#ffffff"/>',
        f'<text x="{min_x + 8:g}" y="{min_y + 18:g}" font-family="Arial,sans-serif" font-size="12" fill="#68707a">{_escape(title)}</text>',
    ]
    for edge in document.edges:
        source = by_id[edge.source_id]
        target = by_id[edge.target_id]
        exit_xy = edge_attachment(edge.style, end="exit")
        entry_xy = edge_attachment(edge.style, end="entry")
        if exit_xy is None:
            source_ports = port_anchors(source.style, source.drawclock_type)
            exit_xy = source_ports.get("right") or source_ports.get("out")
        if entry_xy is None:
            target_ports = port_anchors(target.style, target.drawclock_type)
            entry_xy = target_ports.get("left") or next(iter(target_ports.values()))
        assert exit_xy is not None and entry_xy is not None
        start = (
            source.x + source.width * exit_xy[0],
            source.y + source.height * exit_xy[1],
        )
        end = (
            target.x + target.width * entry_xy[0],
            target.y + target.height * entry_xy[1],
        )
        points = [start, *edge.waypoints, end]
        serialized = " ".join(f"{x:g},{y:g}" for x, y in points)
        # Arc and sharp remain exact in draw.io.  The standalone renderer uses
        # an unambiguous break because it does not invoke draw.io's line router.
        if crossing_style != "none":
            lines.append(f'<polyline class="edge-gap" points="{serialized}"/>')
        lines.append(f'<polyline class="edge" points="{serialized}"/>')
    for x, y in junction_points(document):
        lines.append(f'<circle cx="{x:g}" cy="{y:g}" r="3" fill="#000000"/>')
    for vertex in document.vertices:
        label = vertex.object_attrs.get("label", "")
        if label:
            label_x = vertex.x + HTML_LABEL_CONTENT_OFFSET_X
            label_y = vertex.y + HTML_LABEL_CONTENT_OFFSET_Y
            lines.append(
                f'<foreignObject x="{label_x:g}" y="{label_y:g}" '
                f'width="{vertex.width:g}" height="{vertex.height:g}" overflow="visible">'
                '<div xmlns="http://www.w3.org/1999/xhtml" style="width:100%;height:100%;overflow:visible">'
                f"{label}</div></foreignObject>"
            )
        else:
            lines.append(
                f'<rect x="{vertex.x:g}" y="{vertex.y:g}" width="{vertex.width:g}" '
                f'height="{vertex.height:g}" fill="#f8fafc" stroke="#20252b"/>'
            )
            lines.append(
                f'<text x="{vertex.x + vertex.width / 2:g}" y="{vertex.y + vertex.height / 2:g}" '
                'text-anchor="middle" dominant-baseline="middle" font-family="Arial,sans-serif" font-size="9">'
                f'{_escape(vertex.name)}</text>'
            )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def write_preview_svg(
    document: LayoutDocument,
    output_path: str | Path,
    *,
    title: str = "drawclock",
    crossing_style: str = "gap",
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        build_preview_svg(document, title=title, crossing_style=crossing_style),
        encoding="utf-8",
    )
    return output


def write_preview(
    document: LayoutDocument,
    output_path: str | Path,
    *,
    preview_format: str = "auto",
    title: str = "drawclock",
    crossing_style: str = "gap",
    max_raster_size: int = 16384,
) -> Path:
    """Write SVG directly or rasterize it to PNG in a real browser."""
    output = Path(output_path)
    resolved_format = preview_format
    if resolved_format == "auto":
        resolved_format = output.suffix.lower().lstrip(".")
    if resolved_format not in {"svg", "png"}:
        raise ValueError("preview format must be svg or png")
    if resolved_format == "svg":
        return write_preview_svg(
            document, output, title=title, crossing_style=crossing_style
        )
    if output.suffix.lower() != ".png":
        raise ValueError("PNG preview output must use a .png suffix")
    if max_raster_size < 256:
        raise ValueError("preview max size must be at least 256")
    browser_candidates = (
        shutil.which("msedge"),
        shutil.which("chrome"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/microsoft-edge",
        "/usr/bin/google-chrome",
    )
    browser = next(
        (Path(item) for item in browser_candidates if item and Path(item).is_file()),
        None,
    )
    if browser is None:
        raise ValueError("PNG preview requires Microsoft Edge or Google Chrome")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="drawclock-preview-") as temp_dir:
        svg_path = Path(temp_dir) / "preview.svg"
        write_preview_svg(
            document, svg_path, title=title, crossing_style=crossing_style
        )
        source = svg_path.read_text(encoding="utf-8")
        size = re.search(
            r'<svg[^>]+width="([0-9.]+)"[^>]+height="([0-9.]+)"', source
        )
        if size is None:
            raise ValueError("generated SVG is missing width/height")
        width, height = (float(value) for value in size.groups())
        scale = min(1.0, max_raster_size / max(width, height))
        target_width = max(1, math.ceil(width * scale))
        target_height = max(1, math.ceil(height * scale))
        page_path = Path(temp_dir) / "preview.html"
        page_path.write_text(
            "<!doctype html><meta charset=utf-8>"
            "<style>html,body{margin:0;padding:0;overflow:hidden;background:white}"
            f"body>svg{{display:block;width:{target_width}px;height:{target_height}px}}</style>"
            + source,
            encoding="utf-8",
        )
        subprocess.run(
            [
                str(browser),
                "--headless",
                "--disable-gpu",
                "--hide-scrollbars",
                f"--window-size={target_width},{target_height}",
                f"--screenshot={output}",
                page_path.as_uri(),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
    return output


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
