from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from auto_layout import (
    generate_layout,
    load_clock_tree,
    load_component_hints,
    write_generated_drawio,
)
from drawio_layout import CROSSING_STYLES, apply_crossing_style
from layout_preview import write_preview
from elk_layout import elk_layout_available, generate_elk_layout
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


def _configure_drawio_to_json_parser(parser: argparse.ArgumentParser) -> None:
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
    parser.set_defaults(command=_drawio_to_json)


def _register_hidden_aliases(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    parser: argparse.ArgumentParser,
    aliases: tuple[str, ...],
) -> None:
    # argparse has no public hidden-alias API. Register compatibility spellings
    # in the parser map without adding them to the root help choices.
    for alias in aliases:
        subparsers._name_parser_map[alias] = parser


def _add_drawio_to_json_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "extract",
        help="extract clock-tree JSON from draw.io files",
        description="从 draw.io 时钟树图提取 clock-tree JSON。",
    )
    _configure_drawio_to_json_parser(parser)
    _register_hidden_aliases(subparsers, parser, ("drawio-to-json", "run"))


def _add_json_to_drawio_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "draw",
        help="generate an automatically laid-out draw.io diagram from clock-tree JSON",
        description="从 clock-tree JSON 和现有器件库自动生成从左到右的 draw.io 时钟图。",
    )
    parser.add_argument("-i", "--input", required=True, metavar="FILE", help="clock-tree JSON")
    parser.add_argument("-o", "--output", required=True, metavar="FILE", help="输出 .drawio")
    _add_library_arg(parser, "drawclock 器件库 XML")
    parser.add_argument("--hints", metavar="FILE", help="version 1 component-hints JSON")
    parser.add_argument(
        "--profile",
        choices=("compact", "balanced", "readable"),
        default="readable",
        help="布局密度，默认 readable",
    )
    parser.add_argument(
        "--engine",
        choices=("auto", "elk", "native"),
        default="auto",
        help="自动布局引擎；auto 优先使用 ELK，依赖不可用时回退 native",
    )
    parser.add_argument(
        "--candidates", type=int, default=6, metavar="N", help="评估 1..6 个确定性候选"
    )
    parser.add_argument(
        "--crossing-style",
        choices=CROSSING_STYLES,
        default="arc",
        help="连线跨线风格（默认：arc）",
    )
    parser.add_argument("--preview", metavar="FILE", help="同时输出 SVG 或 PNG 预览")
    parser.add_argument(
        "--preview-format",
        choices=("auto", "svg", "png"),
        default="auto",
        help="预览格式；auto 根据 --preview 的 .svg/.png 后缀判断",
    )
    parser.add_argument(
        "--preview-max-size",
        type=int,
        default=16384,
        metavar="PX",
        help="PNG 最长边像素上限（默认：16384）",
    )
    parser.set_defaults(command=_json_to_drawio)
    _register_hidden_aliases(subparsers, parser, ("json-to-drawio",))


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
        description="在 clock-tree JSON 与 draw.io 时钟图之间转换、自动布局，或刷新旧图。",
    )
    subparsers = parser.add_subparsers(dest="subcommand", metavar="COMMAND", required=True)
    _add_drawio_to_json_parser(subparsers)
    _add_json_to_drawio_parser(subparsers)
    _add_reload_parser(subparsers)
    return parser


def _drawio_to_json(args: argparse.Namespace) -> int:
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


def _json_to_drawio(args: argparse.Namespace) -> int:
    output = Path(args.output)
    try:
        config = load_clock_tree(args.input)
        hints = load_component_hints(args.hints)
        if args.engine == "elk" or (args.engine == "auto" and elk_layout_available()):
            document, _ = generate_elk_layout(
                config,
                library_path=args.library,
                component_hints=hints,
                profile_name=args.profile,
            )
        else:
            document, _ = generate_layout(
                config,
                library_path=args.library,
                component_hints=hints,
                profile_name=args.profile,
                candidate_limit=args.candidates,
            )
        apply_crossing_style(document, args.crossing_style)
        write_generated_drawio(document, output)
        if args.preview:
            write_preview(
                document,
                args.preview,
                preview_format=args.preview_format,
                title=Path(args.input).stem,
                crossing_style=args.crossing_style,
                max_raster_size=args.preview_max_size,
            )
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"已写入 {output}", file=sys.stderr)
    if args.preview:
        print(f"已写入 {args.preview}", file=sys.stderr)
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
