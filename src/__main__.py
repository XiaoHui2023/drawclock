from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipeline import decode_to_drawio, encode_drawio_paths, parse_drawio_paths


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drawclock",
        description="draw.io 时钟树图与 JSON 的双向转换。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    encode = sub.add_parser("encode", help="draw.io → 时钟树 JSON（可选布局 JSON）")
    encode.add_argument(
        "-i",
        "--input",
        type=str,
        metavar="FILE",
        nargs="+",
        required=True,
        help="一个或多个 .drawio.svg / .drawio 源文件",
    )
    encode.add_argument(
        "-o",
        "--output",
        type=str,
        metavar="DIR",
        help="输出目录；未指定时 JSON 写入标准输出",
    )
    encode.add_argument(
        "--layout",
        action="store_true",
        help="同时输出 drawio-layout.json（坐标、连线、样式与对象属性）",
    )

    decode = sub.add_parser("decode", help="JSON → draw.io（需配置、布局与器件库）")
    decode.add_argument(
        "--config",
        type=str,
        metavar="FILE",
        required=True,
        help="时钟树配置 JSON（clock-tree.json）",
    )
    decode.add_argument(
        "--layout",
        type=str,
        metavar="FILE",
        required=True,
        help="画布布局 JSON（drawio-layout.json）",
    )
    decode.add_argument(
        "--library",
        type=str,
        metavar="FILE",
        required=True,
        help="drawclock 器件库（drawio-lib/drawclock.xml）",
    )
    decode.add_argument(
        "-o",
        "--output",
        type=str,
        metavar="FILE",
        required=True,
        help="输出的 .drawio 文件路径",
    )

    return parser


def _run_encode(args: argparse.Namespace) -> int:
    out_dir = Path(args.output) if args.output else None
    if out_dir is None and args.layout:
        print("使用 --layout 时必须指定 -o 输出目录。", file=sys.stderr)
        return 1
    try:
        if out_dir is None:
            config = parse_drawio_paths(args.input).config
            print(json.dumps(config, ensure_ascii=False, indent=2))
            return 0
        config_path, layout_path = encode_drawio_paths(
            args.input,
            out_dir,
            include_layout=args.layout,
        )
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if config_path is not None:
        print(f"已写入 {config_path}", file=sys.stderr)
    if layout_path is not None:
        print(f"已写入 {layout_path}", file=sys.stderr)
    return 0


def _run_decode(args: argparse.Namespace) -> int:
    try:
        out_path = decode_to_drawio(
            args.config,
            args.layout,
            args.library,
            args.output,
        )
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"已写入 {out_path}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "encode":
        return _run_encode(args)
    if args.command == "decode":
        return _run_decode(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
