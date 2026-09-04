from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from auto_layout import load_clock_tree  # noqa: E402
from elk_layout import generate_elk_layout  # noqa: E402
from layout_preview import write_preview_svg  # noqa: E402


EXAMPLES = (
    "01-linear",
    "02-branch-tree",
    "03-mux-dag",
    "04-dual-pll",
    "05-dense-cross-root",
    "06-simple-16-clocks",
    "07-medium-64-clocks",
    "12-dual-from-reuse",
    "13-label-clearance-weave",
    "14-crossing-weave-128-clocks",
    "16-multi-from-clusters",
    "17-terminal-fanout-order",
    "18-asymmetric-merge-columns",
    "19-dispersed-root-fanout",
    "20-asymmetric-merge-route-bulge",
    "21-layout-column-preference",
    "22-terminal-frequency-table",
    "23-middle-column-low-use-sources",
    "24-single-source-rendering-alias",
    "25-mixed-root-port-order-torture",
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
    library = ROOT / "drawio-lib" / "drawclock"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name in EXAMPLES:
        config_path = source_dir / f"{name}.json"
        config = load_clock_tree(config_path)
        started = time.perf_counter()
        document, report = generate_elk_layout(
            config,
            library_path=library,
            profile_name=args.profile,
        )
        generated = time.perf_counter()
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
