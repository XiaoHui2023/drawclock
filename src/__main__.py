from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipeline import drawio_to_clock_tree, write_clock_tree_json


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drawclock",
        description="从 draw.io 时钟树图提取 clock-tree.json（仅器件库图形参与逻辑与校验）。",
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        metavar="FILE",
        nargs="+",
        required=True,
        help="一个或多个 .drawio.svg / .drawio 源文件",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        metavar="FILE",
        help="输出的 JSON 文件路径；未指定时打印到标准输出",
    )
    parser.add_argument(
        "-l",
        "--library",
        type=str,
        metavar="FILE",
        required=True,
        help="drawclock 器件库 XML",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    out_path = Path(args.output) if args.output else None
    try:
        config = drawio_to_clock_tree(args.input, library_path=args.library)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if out_path is None:
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0
    try:
        written = write_clock_tree_json(config, out_path)
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if written is not None:
        print(f"已写入 {written}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
