from __future__ import annotations

import argparse
import sys
from pathlib import Path

from auto_layout import load_clock_tree
from drawio_layout import CROSSING_STYLES, apply_crossing_style
from elk_layout import generate_elk_layout
from layout_preview import write_preview_svg
from presentation import DrawingOptions, ALIGNMENTS, ANCHORS


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drawclock",
        description="从时钟连接配置和指定器件库生成从左到右的 SVG 时钟图。",
    )
    parser.add_argument(
        "-i", "--input", required=True, metavar="FILE", help="时钟连接配置文件"
    )
    parser.add_argument(
        "-l",
        "--library",
        required=True,
        action="append",
        nargs="+",
        metavar="PATH",
        help="一个或多个 draw.io 器件库 XML 或目录；可重复指定",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        metavar="FILE",
        help="输出 SVG 文件；后缀不影响内容格式",
    )
    parser.add_argument(
        "--title",
        help="SVG 元数据标题；默认使用输入文件名，不在画布中显示",
    )
    parser.add_argument(
        "--crossing-style",
        choices=CROSSING_STYLES,
        default="arc",
        help="连线跨线风格（默认：arc）",
    )
    parser.add_argument("--description-align", choices=ALIGNMENTS, default="left", help="注释文字对齐")
    parser.add_argument("--description-anchor", choices=ANCHORS, default="top-left", help="注释所在方位")
    parser.add_argument("--description-offset-x", type=float, default=0.0, help="注释水平偏移（像素）")
    parser.add_argument("--description-offset-y", type=float, default=0.0, help="注释垂直偏移（像素）")
    parser.add_argument("--horizontal-spacing", type=float, help="节点列之间的最小水平间距（像素）")
    parser.add_argument("--name-align", choices=ALIGNMENTS, default="center", help="多行节点名对齐")
    parser.add_argument("--frequency-headers", nargs="+", help="频率数组的各列表头；字符串可含换行")
    parser.add_argument("--frequency-align", choices=ALIGNMENTS, default="center", help="频率表文字对齐")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    output = Path(args.output)
    libraries = [path for group in args.library for path in group]
    try:
        config = load_clock_tree(args.input)
        options = DrawingOptions(
            description_align=args.description_align,
            description_anchor=args.description_anchor,
            description_offset_x=args.description_offset_x,
            description_offset_y=args.description_offset_y,
            horizontal_spacing=args.horizontal_spacing,
            name_align=args.name_align,
            frequency_headers=tuple(args.frequency_headers or ()),
            frequency_align=args.frequency_align,
        )
        document, _ = generate_elk_layout(config, library_path=libraries, options=options)
        apply_crossing_style(document, args.crossing_style)
        write_preview_svg(
            document,
            output,
            title=args.title if args.title is not None else "drawclock",
            crossing_style=args.crossing_style,
        )
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"已写入 {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
