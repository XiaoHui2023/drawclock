from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from migrate import reload_drawio_inputs
from pipeline import drawio_to_clock_tree, write_clock_tree_json


def _add_library_arg(parser: argparse.ArgumentParser, help_text: str) -> None:
    parser.add_argument(
        "-l",
        "--library",
        type=str,
        metavar="FILE",
        required=True,
        help=help_text,
    )


def _add_run_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "run",
        help="extract clock-tree JSON from draw.io files",
        description="从 draw.io 时钟树图提取 clock-tree JSON。",
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
        help="输出 JSON 文件路径；未指定时打印到标准输出",
    )
    _add_library_arg(parser, "drawclock 器件库 XML")
    parser.set_defaults(command=_run)


def _add_reload_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "reload",
        help="refresh draw.io files with the current library",
        description="用新器件库刷新旧 draw.io 图中的器件库图形样式。",
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        metavar="PATH",
        required=True,
        help="旧 .drawio / .drawio.svg，或含 *.drawio.svg 的目录",
    )
    _add_library_arg(parser, "新器件库 drawclock.xml")
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        metavar="PATH",
        required=True,
        help="输出 .drawio / .drawio.svg 路径，或批量输出目录",
    )
    parser.set_defaults(command=_reload)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drawclock",
        description="从 draw.io 时钟树图生成 clock-tree JSON，或用新器件库刷新旧图。",
    )
    subparsers = parser.add_subparsers(dest="subcommand", metavar="COMMAND", required=True)
    _add_run_parser(subparsers)
    _add_reload_parser(subparsers)
    return parser


def _run(args: argparse.Namespace) -> int:
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


def _reload(args: argparse.Namespace) -> int:
    try:
        written = reload_drawio_inputs(args.input, args.library, args.output)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    for out_path in written:
        print(f"已写入 {out_path}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.command(args)


if __name__ == "__main__":
    raise SystemExit(main())
