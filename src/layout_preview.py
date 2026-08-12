from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
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
SUPPORTED_IMAGE_SUFFIXES = (".svg", ".png")


def _svg_num(value: float) -> str:
    """Serialize every layout coordinate without losing its 4-decimal contract."""
    return f"{float(value):.4f}".rstrip("0").rstrip(".") or "0"


def _runtime_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent / "runtime")
    roots.append(Path(__file__).resolve().parents[1] / ".runtime")
    return tuple(dict.fromkeys(roots))


def _browser_path() -> Path | None:
    executable = (
        "chrome-headless-shell.exe" if os.name == "nt" else "chrome-headless-shell"
    )
    browser_candidates = [os.environ.get("CHROME_PATH")]
    browser_candidates.extend(
        str(root / "headless-shell" / executable) for root in _runtime_roots()
    )
    browser_candidates.extend(
        (
            shutil.which("msedge"),
            shutil.which("microsoft-edge"),
            shutil.which("microsoft-edge-stable"),
            shutil.which("chrome"),
            shutil.which("google-chrome"),
            shutil.which("google-chrome-stable"),
            shutil.which("chromium"),
            shutil.which("chromium-browser"),
        )
    )
    return next(
        (Path(item) for item in browser_candidates if item and Path(item).is_file()),
        None,
    )


def validate_image_output(output_path: str | Path) -> str:
    """Validate the requested image format before layout work starts."""
    suffix = Path(output_path).suffix.lower()
    if suffix not in SUPPORTED_IMAGE_SUFFIXES:
        supported = ", ".join(SUPPORTED_IMAGE_SUFFIXES)
        raise ValueError(f"不支持输出格式 {suffix or '<无后缀>'}；支持：{supported}")
    if suffix == ".png" and _browser_path() is None:
        raise ValueError("PNG 渲染运行时不可用；发布包应包含 runtime/headless-shell")
    return suffix[1:]


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
            f'viewBox="{_svg_num(min_x)} {_svg_num(min_y)} '
            f'{_svg_num(width)} {_svg_num(height)}" '
            f'width="{_svg_num(width)}" height="{_svg_num(height)}">'
        ),
        "<style>.edge-gap{fill:none;stroke:#fff;stroke-width:6;stroke-linejoin:round}.edge{fill:none;stroke:#20252b;stroke-width:1.6;stroke-linejoin:round;stroke-linecap:square}</style>",
        f'<rect x="{_svg_num(min_x)}" y="{_svg_num(min_y)}" '
        f'width="{_svg_num(width)}" height="{_svg_num(height)}" fill="#ffffff"/>',
        f'<text x="{_svg_num(min_x + 8)}" y="{_svg_num(min_y + 18)}" '
        f'font-family="Arial,sans-serif" font-size="12" fill="#68707a">{_escape(title)}</text>',
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
        serialized = " ".join(
            f"{_svg_num(x)},{_svg_num(y)}" for x, y in points
        )
        # Arc and sharp remain exact in draw.io.  The standalone renderer uses
        # an unambiguous break because it does not invoke draw.io's line router.
        if crossing_style != "none":
            lines.append(f'<polyline class="edge-gap" points="{serialized}"/>')
        lines.append(f'<polyline class="edge" points="{serialized}"/>')
    for x, y in junction_points(document):
        lines.append(
            f'<circle cx="{_svg_num(x)}" cy="{_svg_num(y)}" '
            'r="3" fill="#000000"/>'
        )
    for vertex in document.vertices:
        label = vertex.object_attrs.get("label", "")
        if label:
            # Keep the viewport on mxGeometry. Moving it would leave the
            # left-side contact outside the clip boundary. The HTML content
            # offset belongs inside the viewport and cancels the graphic's
            # inverse (-2,-7) offset exactly.
            lines.append(
                f'<foreignObject x="{_svg_num(vertex.x)}" y="{_svg_num(vertex.y)}" '
                f'width="{_svg_num(vertex.width + HTML_LABEL_CONTENT_OFFSET_X)}" '
                f'height="{_svg_num(vertex.height + HTML_LABEL_CONTENT_OFFSET_Y)}" overflow="visible">'
                '<div xmlns="http://www.w3.org/1999/xhtml" '
                f'style="position:relative;left:{HTML_LABEL_CONTENT_OFFSET_X:g}px;'
                f'top:{HTML_LABEL_CONTENT_OFFSET_Y:g}px;width:{vertex.width:g}px;'
                f'height:{vertex.height:g}px;overflow:visible">'
                f"{label}</div></foreignObject>"
            )
        else:
            lines.append(
                f'<rect x="{_svg_num(vertex.x)}" y="{_svg_num(vertex.y)}" '
                f'width="{_svg_num(vertex.width)}" height="{_svg_num(vertex.height)}" '
                'fill="#f8fafc" stroke="#20252b"/>'
            )
            lines.append(
                f'<text x="{_svg_num(vertex.x + vertex.width / 2)}" '
                f'y="{_svg_num(vertex.y + vertex.height / 2)}" '
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
    title: str = "drawclock",
    crossing_style: str = "gap",
) -> Path:
    """Write SVG directly or rasterize it to PNG in a real browser."""
    output = Path(output_path)
    resolved_format = validate_image_output(output)
    if resolved_format == "svg":
        return write_preview_svg(
            document, output, title=title, crossing_style=crossing_style
        )
    browser = _browser_path()
    assert browser is not None
    output.parent.mkdir(parents=True, exist_ok=True)
    screenshot_output = output.resolve()
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
        target_width = max(1, math.ceil(width))
        target_height = max(1, math.ceil(height))
        page_path = Path(temp_dir) / "preview.html"
        page_path.write_text(
            "<!doctype html><meta charset=utf-8>"
            "<style>html,body{margin:0;padding:0;overflow:hidden;background:white}"
            f"body>svg{{display:block;width:{target_width}px;height:{target_height}px}}</style>"
            + source,
            encoding="utf-8",
        )
        browser_args = [
            str(browser),
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--window-size={target_width},{target_height}",
            f"--screenshot={screenshot_output}",
            page_path.as_uri(),
        ]
        if os.name != "nt":
            # Linux frozen binaries are commonly exercised in CI containers;
            # Chrome's user-namespace sandbox is unavailable there.
            browser_args.insert(1, "--no-sandbox")
        subprocess.run(
            browser_args,
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
