from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from auto_layout import (  # noqa: E402
    generate_layout,
    load_clock_tree,
    load_component_hints,
    write_generated_drawio,
)
from elk_layout import generate_elk_layout  # noqa: E402
from layout_preview import write_preview_svg  # noqa: E402


EXAMPLES = (
    ("01-linear", None),
    ("02-branch-tree", None),
    ("03-mux-dag", None),
    ("04-dual-pll", "04-dual-pll.hints.json"),
    ("05-dense-cross-root", "05-dense-cross-root.hints.json"),
    ("06-simple-16-clocks", "06-simple-16-clocks.hints.json"),
    ("07-medium-64-clocks", "07-medium-64-clocks.hints.json"),
    ("08-stress-512-clocks", "08-stress-512-clocks.hints.json"),
    ("09-stress-1024-clocks", "09-stress-1024-clocks.hints.json"),
    ("10-stress-2048-clocks", "10-stress-2048-clocks.hints.json"),
    ("11-stress-4096-clocks", "11-stress-4096-clocks.hints.json"),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成全部 JSON 自动布局示例。")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "example" / "generated",
    )
    parser.add_argument(
        "--profile",
        choices=("compact", "balanced", "readable"),
        default="readable",
    )
    args = parser.parse_args(argv)

    source_dir = ROOT / "example" / "auto-layout"
    library = ROOT / "drawio-lib" / "drawclock.xml"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, hints_name in EXAMPLES:
        config_path = source_dir / f"{name}.json"
        hints_path = source_dir / hints_name if hints_name else None
        config = load_clock_tree(config_path)
        hints = load_component_hints(hints_path)
        started = time.perf_counter()
        if name.startswith(("06-", "07-", "08-", "09-", "10-", "11-")):
            document, report = generate_elk_layout(
                config,
                library_path=library,
                component_hints=hints,
                profile_name=args.profile,
            )
        else:
            document, report = generate_layout(
                config,
                library_path=library,
                component_hints=hints,
                profile_name=args.profile,
            )
        generated = time.perf_counter()
        write_generated_drawio(
            document, args.output_dir / f"{name}.drawio"
        )
        write_preview_svg(
            document,
            args.output_dir / f"{name}.svg",
            title=name,
        )
        finished = time.perf_counter()
        print(
            f"{name}: engine={report.get('engine', 'native-layered')} "
            f"generate={generated - started:.4f}s "
            f"write={finished - generated:.4f}s total={finished - started:.4f}s"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
