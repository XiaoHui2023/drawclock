"""Exercise the release executable through its only public operation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "drawio-lib" / "drawclock.xml"
DRAW_EXAMPLE = ROOT / "example" / "draw.json"
LINEAR = ROOT / "example" / "auto-layout" / "01-linear.json"
DENSE = ROOT / "example" / "auto-layout" / "05-dense-cross-root.json"
STRESS = ROOT / "example" / "auto-layout" / "08-stress-512-clocks.json"
ASYMMETRIC = ROOT / "example" / "auto-layout" / "20-asymmetric-merge-route-bulge.json"
COLUMN_PREFERENCE = ROOT / "example" / "auto-layout" / "21-layout-column-preference.json"
SKILLS = ROOT / "skills"
SVG_NS = "http://www.w3.org/2000/svg"


def _binary_path() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).resolve()
    return ROOT / "dist" / ("drawclock.exe" if sys.platform == "win32" else "drawclock")


def _run(binary: Path, args: list[str], *, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    isolated_path = ROOT / "example" / "out" / "empty-path"
    isolated_path.mkdir(parents=True, exist_ok=True)
    env["PATH"] = str(isolated_path)
    completed = subprocess.run(
        [str(binary), *args], cwd=ROOT, env=env, text=True,
        encoding="utf-8", errors="replace", capture_output=True, check=False,
    )
    if (completed.returncode == 0) != expect_success:
        print(completed.stdout, file=sys.stderr)
        print(completed.stderr, file=sys.stderr)
        raise SystemExit(1)
    return completed


def _edge_count(config: dict[str, dict[str, object]]) -> int:
    count = 0
    for item in config.values():
        source = item.get("source")
        count += len(source) if isinstance(source, dict) else int(source is not None)
    return count


def _assert_svg(
    path: Path, *, nodes: int, edges: int, max_total_bends: int | None = None,
) -> None:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    if root.tag != f"{{{SVG_NS}}}svg":
        raise SystemExit(f"not SVG: {path}")
    rendered_edges = [
        element for element in list(root)
        if element.get("class") == "edge"
    ]
    rendered_nodes = root.findall(f"{{{SVG_NS}}}foreignObject")
    if len(rendered_nodes) < nodes or len(rendered_edges) != edges:
        raise SystemExit(
            f"unexpected SVG topology: {path} nodes={len(rendered_nodes)} edges={len(rendered_edges)}"
        )
    view_box = [float(value) for value in root.get("viewBox", "").split()]
    if len(view_box) != 4 or view_box[2] <= 0 or view_box[3] <= 0:
        raise SystemExit(f"invalid SVG bounds: {path}")
    total_bends = sum(
        max(0, len(element.get("points", "").split()) - 2)
        for element in rendered_edges
    )
    if max_total_bends is not None and total_bends > max_total_bends:
        raise SystemExit(
            f"avoidable frozen SVG bends: {path} "
            f"total={total_bends} maximum={max_total_bends}"
        )


def _draw(
    binary: Path, source: Path, output: Path, *extra: str,
    max_total_bends: int | None = None,
) -> None:
    _run(binary, ["-i", str(source), "-l", str(LIBRARY), "-o", str(output), *extra])
    config = json.loads(source.read_text(encoding="utf-8"))
    _assert_svg(
        output, nodes=len(config), edges=_edge_count(config),
        max_total_bends=max_total_bends,
    )


def _write_split_libraries(target: Path) -> tuple[Path, Path]:
    text = LIBRARY.read_text(encoding="utf-8").strip()
    entries = json.loads(text[len("<mxlibrary>") : -len("</mxlibrary>")])
    midpoint = len(entries) // 2
    first = target / "first.xml"
    second = target / "nested" / "second.xml"
    second.parent.mkdir(parents=True, exist_ok=True)
    for path, part in ((first, entries[:midpoint]), (second, entries[midpoint:])):
        path.write_text(
            "<mxlibrary>" + json.dumps(part, ensure_ascii=False) + "</mxlibrary>",
            encoding="utf-8",
        )
    return first, second.parent


def _named_node_xs(path: Path, names: tuple[str, ...]) -> dict[str, float]:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    x_by_name: dict[str, float] = {}
    for element in root.findall(f"{{{SVG_NS}}}foreignObject"):
        text_content = "".join(element.itertext())
        for name in names:
            if name in text_content:
                x_by_name[name] = float(element.get("x", "nan"))
    if set(x_by_name) != set(names):
        raise SystemExit(f"layout_column nodes are missing: {x_by_name}")
    return x_by_name


def _assert_named_nodes_same_x(path: Path, names: tuple[str, ...]) -> float:
    x_by_name = _named_node_xs(path, names)
    if len(set(x_by_name.values())) != 1:
        raise SystemExit(f"layout_column nodes are not co-column: {x_by_name}")
    return next(iter(x_by_name.values()))


def main() -> int:
    global ROOT, LIBRARY, DRAW_EXAMPLE, LINEAR, DENSE, STRESS, ASYMMETRIC
    global COLUMN_PREFERENCE, SKILLS
    binary = _binary_path()
    package_root = binary.parent
    if (package_root / "runtime" / "runtime-manifest.json").is_file():
        ROOT = package_root
        LIBRARY = ROOT / "drawio-lib" / "drawclock.xml"
        DRAW_EXAMPLE = ROOT / "example" / "draw.json"
        LINEAR = ROOT / "example" / "auto-layout" / "01-linear.json"
        DENSE = ROOT / "example" / "auto-layout" / "05-dense-cross-root.json"
        STRESS = ROOT / "example" / "auto-layout" / "08-stress-512-clocks.json"
        ASYMMETRIC = ROOT / "example" / "auto-layout" / "20-asymmetric-merge-route-bulge.json"
        COLUMN_PREFERENCE = ROOT / "example" / "auto-layout" / "21-layout-column-preference.json"
        SKILLS = ROOT / "skills"
    runtime = binary.parent / "runtime"
    required = (
        binary, LIBRARY, DRAW_EXAMPLE, LINEAR, DENSE, STRESS, ASYMMETRIC,
        COLUMN_PREFERENCE,
        runtime / "runtime-manifest.json",
        runtime / ("node/node.exe" if sys.platform == "win32" else "node/bin/node"),
        runtime / "elk" / "elk_layout.mjs",
        runtime / "elk" / "node_modules" / "elkjs" / "lib" / "elk.bundled.js",
        SKILLS / "clock-diagram-design" / "SKILL.md",
        SKILLS / "clock-json-schema" / "SKILL.md",
        SKILLS / "clock-layout-algorithms" / "SKILL.md",
        SKILLS / "component-library-design" / "SKILL.md",
        SKILLS / "drawclock-project-navigation" / "SKILL.md",
        SKILLS / "drawclock-project-navigation" / "scripts" / "validate_skills.py",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        print("missing release inputs:\n" + "\n".join(missing), file=sys.stderr)
        return 1

    subprocess.run(
        [
            sys.executable,
            str(SKILLS / "drawclock-project-navigation" / "scripts" / "validate_skills.py"),
            str(SKILLS),
        ],
        cwd=ROOT,
        check=True,
    )

    out = ROOT / "example" / "out"
    out.mkdir(parents=True, exist_ok=True)
    _draw(binary, DRAW_EXAMPLE, out / "draw-example-frozen.svg")
    _draw(binary, LINEAR, out / "arbitrary-suffix.png", "--crossing-style", "gap")
    _draw(binary, DENSE, out / "dense-frozen.svg")
    _draw(binary, STRESS, out / "stress-512-frozen.svg")
    _draw(
        binary, ASYMMETRIC, out / "asymmetric-frozen.svg",
        max_total_bends=2,
    )
    column_output = out / "column-preference-frozen.svg"
    _draw(binary, COLUMN_PREFERENCE, column_output)
    root_x = _assert_named_nodes_same_x(
        column_output, ("root_a", "root_b", "root_c", "root_d")
    )
    mux_x = _assert_named_nodes_same_x(
        column_output, ("sel_00", "sel_01", "sel_02")
    )
    clock_x = _assert_named_nodes_same_x(
        column_output, ("clk_00", "clk_01", "clk_02")
    )
    if not root_x < mux_x < clock_x:
        raise SystemExit(
            "layout_column numeric order is not left-to-right: "
            f"root={root_x}, mux={mux_x}, clock={clock_x}"
        )

    strict_json = out / "frozen-input.json"
    strict_json.write_text('{"osc":{"kind":"source"}}', encoding="utf-8")
    strict_output = out / "frozen-input-json.svg"
    _run(binary, ["-i", str(strict_json), "-l", str(LIBRARY), "-o", str(strict_output)])
    _assert_svg(strict_output, nodes=1, edges=0)

    for suffix in ("jsonc", "json5", "toml", "yaml", "yml", "ini", "conf", "config"):
        config_path = out / f"rejected-input.{suffix}"
        config_path.write_text("{}", encoding="utf-8")
        _run(
            binary,
            ["-i", str(config_path), "-l", str(LIBRARY), "-o", str(out / "rejected.svg")],
            expect_success=False,
        )

    split_root = out / "split-libraries"
    split_root.mkdir(parents=True, exist_ok=True)
    first_library, library_directory = _write_split_libraries(split_root)
    split_output = out / "split-libraries.svg"
    _run(
        binary,
        [
            "-i", str(DRAW_EXAMPLE),
            "-l", str(first_library),
            "-l", str(library_directory),
            "-o", str(split_output),
        ],
    )
    split_config = json.loads(DRAW_EXAMPLE.read_text(encoding="utf-8"))
    _assert_svg(
        split_output,
        nodes=len(split_config),
        edges=_edge_count(split_config),
    )

    for removed in ("draw", "extract", "reload", "run", "drawio-to-json"):
        _run(binary, [removed], expect_success=False)
    print("frozen draw workflow passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
