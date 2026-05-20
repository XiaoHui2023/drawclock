from __future__ import annotations

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drawio-to-clock-tree",
        description="从 draw.io 图生成时钟树相关输出。",
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        metavar="FILE",
        required=True,
        help="draw.io 源文件路径（.drawio 或 .xml）",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        metavar="DIR",
        help="输出目录；未指定时写入当前工作目录",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    # TODO: 接入解析与生成逻辑
    print(f"输入: {args.input}", file=sys.stderr)
    if args.output:
        print(f"输出目录: {args.output}", file=sys.stderr)
    print("主流程尚未实现。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
