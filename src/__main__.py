from __future__ import annotations

import argparse
import sys
from pathlib import Path

from auto_layout import load_clock_tree
from drawio_layout import CROSSING_STYLES, apply_crossing_style
from elk_layout import generate_elk_layout
from layout_preview import write_preview_svg


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
        metavar="FILE",
        help="draw.io 器件库 XML",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        metavar="FILE",
        help="输出 SVG 文件；后缀不影响内容格式",
    )
    parser.add_argument(
        "--crossing-style",
        choices=CROSSING_STYLES,
        default="arc",
        help="连线跨线风格（默认：arc）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    output = Path(args.output)
    try:
        config = load_clock_tree(args.input)
        document, _ = generate_elk_layout(config, library_path=args.library)
        apply_crossing_style(document, args.crossing_style)
        write_preview_svg(
            document,
            output,
            title=Path(args.input).stem,
            crossing_style=args.crossing_style,
        )
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"已写入 {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
