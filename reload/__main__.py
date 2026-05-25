from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from migrate import reload_drawio_file  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drawclock-reload",
        description=(
            "用新器件库刷新旧 draw.io 图中的器件库图形样式；"
            "保留坐标、对象属性与非器件库内容。"
        ),
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        metavar="FILE",
        required=True,
        help="旧 .drawio / .drawio.svg",
    )
    parser.add_argument(
        "-l",
        "--library",
        type=str,
        metavar="FILE",
        required=True,
        help="新器件库 drawclock.xml",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        metavar="FILE",
        required=True,
        help="输出的 .drawio 路径",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        out_path = reload_drawio_file(args.input, args.library, args.output)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"已写入 {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
