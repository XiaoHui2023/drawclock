"""Exercise the release executable through its only public operation."""

from __future__ import annotations

import json
import itertools
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "drawio-lib" / "drawclock"
DRAW_EXAMPLE = ROOT / "example" / "draw.json"
LINEAR = ROOT / "example" / "auto-layout" / "01-linear.json"
DENSE = ROOT / "example" / "auto-layout" / "05-dense-cross-root.json"
MEDIUM = ROOT / "example" / "auto-layout" / "07-medium-64-clocks.json"
ASYMMETRIC = ROOT / "example" / "auto-layout" / "20-asymmetric-merge-route-bulge.json"
COLUMN_PREFERENCE = ROOT / "example" / "auto-layout" / "21-layout-column-preference.json"
FREQUENCY = ROOT / "example" / "auto-layout" / "22-terminal-frequency-table.json"
MULTI_SOURCE = ROOT / "example" / "auto-layout" / "19-dispersed-root-fanout.json"
SINGLE_ALIAS = ROOT / "example" / "auto-layout" / "24-single-source-rendering-alias.json"
MIDDLE_SOURCE = ROOT / "example" / "auto-layout" / "23-middle-column-low-use-sources.json"
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
    rendered_nodes = [
        element for element in root.iter()
        if "component" in element.get("class", "").split()
    ]
    if len(rendered_nodes) < nodes or len(rendered_edges) != edges:
        raise SystemExit(
            f"unexpected SVG topology: {path} nodes={len(rendered_nodes)} edges={len(rendered_edges)}"
        )
    forbidden = {"foreignObject", "script", "iframe", "audio", "video", "canvas"}
    if any(element.tag.rsplit("}", 1)[-1] in forbidden for element in root.iter()):
        raise SystemExit(f"browser-only SVG content: {path}")
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


def _write_mixed_library_inputs(target: Path) -> tuple[Path, Path]:
    first = target / "source.xml"
    remaining = target / "nested"
    remaining.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LIBRARY / "source.xml", first)
    for path in LIBRARY.glob("*.xml"):
        if path.name != "source.xml":
            shutil.copy2(path, remaining / path.name)
    return first, remaining


def _named_node_xs(path: Path, names: tuple[str, ...]) -> dict[str, float]:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    x_by_name: dict[str, float] = {}
    for element in root.iter():
        if "component" not in element.get("class", "").split():
            continue
        text_content = "".join(element.itertext())
        graphic = next(
            (
                child for child in element.iter()
                if "component-graphic" in child.get("class", "").split()
            ),
            None,
        )
        if graphic is None:
            continue
        for name in names:
            if name in text_content:
                x_by_name[name] = float(graphic.get("x", "nan"))
    if set(x_by_name) != set(names):
        raise SystemExit(f"layout_column nodes are missing: {x_by_name}")
    return x_by_name


def _assert_named_nodes_same_x(path: Path, names: tuple[str, ...]) -> float:
    x_by_name = _named_node_xs(path, names)
    if len(set(x_by_name.values())) != 1:
        raise SystemExit(f"layout_column nodes are not co-column: {x_by_name}")
    return next(iter(x_by_name.values()))


def _assert_single_logical_source_has_rendering_anchors(
    path: Path, config_path: Path, logical_name: str,
) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    roots = {
        name for name, item in config.items()
        if not item.get("source")
    }
    if roots != {logical_name}:
        raise SystemExit(f"example is not single-logical-source: {roots}")
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    anchors = [
        element for element in root.iter()
        if element.get("class") == "component"
        and element.get("data-node-id") == logical_name
    ]
    if len(anchors) < 2:
        raise SystemExit(
            f"single logical source was not rendered near distant consumers: {len(anchors)}"
        )


def _assert_multi_source_row_patterns(path: Path, config_path: Path) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    roots = {name for name, item in config.items() if not item.get("source")}
    terminals = [name for name, item in config.items() if item.get("kind") == "clock"]
    pads = [name for name, item in config.items() if item.get("kind") == "pad3"]
    memo: dict[str, frozenset[str]] = {}

    def root_ancestors(name: str) -> frozenset[str]:
        if name in memo:
            return memo[name]
        source = config[name].get("source")
        if not source:
            result = frozenset({name})
            memo[name] = result
            return result
        values = source.values() if isinstance(source, dict) else (source,)
        ancestors: set[str] = set()
        for value in values:
            ancestors.update(root_ancestors(str(value).split("[", 1)[0]))
        result = frozenset(ancestors)
        memo[name] = result
        return result

    signatures = [root_ancestors(name) for name in terminals]
    pairs = {
        pair
        for signature in signatures
        for pair in itertools.combinations(sorted(signature), 2)
    }
    pad_ports = Counter(len(config[name]["source"]) for name in pads)
    hybrid_muxes = 0
    for item in config.values():
        source = item.get("source")
        if item.get("kind") != "mux2" or not isinstance(source, dict):
            continue
        upstream = {str(value).split("[", 1)[0] for value in source.values()}
        hybrid_muxes += bool(upstream & set(pads) and upstream & roots)
    observed = {
        "roots": len(roots),
        "terminals": len(terminals),
        "pads": len(pads),
        "pad_ports": pad_ports,
        "hybrid_muxes": hybrid_muxes,
        "signature_sizes": Counter(map(len, signatures)),
        "unique_signatures": len(set(signatures)),
        "source_pairs": len(pairs),
    }
    if observed != {
        "roots": 8,
        "terminals": 48,
        "pads": 8,
        "pad_ports": Counter({3: 6, 2: 2}),
        "hybrid_muxes": 8,
        "signature_sizes": Counter({1: 24, 3: 15, 4: 6, 2: 3}),
        "unique_signatures": 24,
        "source_pairs": 25,
    }:
        raise SystemExit(f"multi-source feature coverage is invalid: {observed}")
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    rendered_ids = [
        element.get("data-node-id")
        for element in root.iter()
        if element.get("class") == "component"
    ]
    if set(rendered_ids) != set(config):
        raise SystemExit("multi-source rendering lost logical node identities")
    rendered_pad_nodes = [
        element for element in root.iter()
        if element.get("class") == "component"
        and element.get("data-node-id") in pads
    ]
    if len(rendered_pad_nodes) != 8:
        raise SystemExit(f"multi-input pad rendering is invalid: {len(rendered_pad_nodes)}")
    if len(rendered_ids) <= len(config):
        raise SystemExit("dispersed sources did not produce local rendering anchors")


def _assert_frequency_table(path: Path, config_path: Path) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    referenced = set()
    for item in config.values():
        source = item.get("source")
        values = source.values() if isinstance(source, dict) else (source,)
        referenced.update(
            value.split("[", 1)[0]
            for value in values
            if isinstance(value, str)
        )
    terminals = set(config) - referenced
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    components = [
        element for element in root.iter()
        if element.get("class") == "component"
        and element.get("data-node-id") in terminals
    ]
    if len(components) != len(terminals):
        raise SystemExit("frequency example terminal traceability is incomplete")
    graphics = [
        next(child for child in component.iter()
             if child.get("class") == "component-graphic")
        for component in components
    ]
    if len({graphic.get("x") for graphic in graphics}) != 1:
        raise SystemExit("frequency example terminals are not co-column")
    if len({graphic.get("y") for graphic in graphics}) != len(graphics):
        raise SystemExit("frequency example places multiple terminals on one row")

    headings = [
        element for element in root.iter()
        if element.get("class") == "frequency-heading"
    ]
    labels = [element.get("aria-label", element.text or "") for element in headings]
    fields = [element.get("data-frequency-field") for element in headings]
    if labels != ["工作频率", "SCAN", "BIST"] or fields != [
        "func_freq", "scan_freq", "bist_freq",
    ]:
        raise SystemExit(f"frequency headings are invalid: {labels=} {fields=}")
    if any(element.get("fill") != "#20252b" for element in headings):
        raise SystemExit("frequency headings are not black")
    outline = headings[0]
    if outline.get("data-heading-render") != "outline" or sum(
        child.tag.rsplit("}", 1)[-1] == "path" for child in outline
    ) != 4:
        raise SystemExit("Chinese frequency heading is not font-independent")

    values = [
        element for element in root.iter()
        if element.get("class") == "frequency-value"
    ]
    observed = {
        (element.get("data-node-id"), element.get("data-frequency-field")): element.text
        for element in values
    }
    expected = {
        (name, field): str(item[field])
        for name, item in config.items()
        if name in terminals
        for field in ("func_freq", "scan_freq", "bist_freq")
        if field in item and str(item[field])
    }
    if observed != expected or any(
        element.get("fill") != "#d02020" for element in values
    ):
        raise SystemExit(f"frequency values are invalid: {observed=}, {expected=}")


def main() -> int:
    global ROOT, LIBRARY, DRAW_EXAMPLE, LINEAR, DENSE, MEDIUM, ASYMMETRIC
    global COLUMN_PREFERENCE, FREQUENCY, MULTI_SOURCE, SINGLE_ALIAS, MIDDLE_SOURCE, SKILLS
    binary = _binary_path()
    package_root = binary.parent
    if (package_root / "source-manifest.json").is_file():
        ROOT = package_root
        LIBRARY = ROOT / "drawio-lib" / "drawclock"
        DRAW_EXAMPLE = ROOT / "example" / "draw.json"
        LINEAR = ROOT / "example" / "auto-layout" / "01-linear.json"
        DENSE = ROOT / "example" / "auto-layout" / "05-dense-cross-root.json"
        MEDIUM = ROOT / "example" / "auto-layout" / "07-medium-64-clocks.json"
        ASYMMETRIC = ROOT / "example" / "auto-layout" / "20-asymmetric-merge-route-bulge.json"
        COLUMN_PREFERENCE = ROOT / "example" / "auto-layout" / "21-layout-column-preference.json"
        FREQUENCY = ROOT / "example" / "auto-layout" / "22-terminal-frequency-table.json"
        MULTI_SOURCE = ROOT / "example" / "auto-layout" / "19-dispersed-root-fanout.json"
        SINGLE_ALIAS = ROOT / "example" / "auto-layout" / "24-single-source-rendering-alias.json"
        MIDDLE_SOURCE = ROOT / "example" / "auto-layout" / "23-middle-column-low-use-sources.json"
        SKILLS = ROOT / "skills"
    required = (
        binary, DRAW_EXAMPLE, LINEAR, DENSE, MEDIUM, ASYMMETRIC,
        COLUMN_PREFERENCE, FREQUENCY, MULTI_SOURCE, SINGLE_ALIAS, MIDDLE_SOURCE,
        SKILLS / "clock-diagram-design" / "SKILL.md",
        SKILLS / "clock-json-schema" / "SKILL.md",
        SKILLS / "clock-layout-algorithms" / "SKILL.md",
        SKILLS / "component-library-design" / "SKILL.md",
        SKILLS / "drawclock-project-navigation" / "SKILL.md",
        SKILLS / "svg-artifact-design" / "SKILL.md",
        SKILLS / "svg-portability" / "SKILL.md",
        SKILLS / "drawclock-project-navigation" / "scripts" / "validate_skills.py",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if not LIBRARY.is_dir() or not any(LIBRARY.glob("*.xml")):
        missing.append(str(LIBRARY))
    if missing:
        print("missing release inputs:\n" + "\n".join(missing), file=sys.stderr)
        return 1
    forbidden_runtime = (
        package_root / "runtime",
        package_root / "node_modules",
        package_root / "package.json",
        package_root / "package-lock.json",
    )
    if any(path.exists() for path in forbidden_runtime):
        print("release contains an unused Node/ELK runtime", file=sys.stderr)
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
    _draw(binary, MEDIUM, out / "medium-64-frozen.svg")
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

    frequency_output = out / "terminal-frequency-frozen.svg"
    _draw(binary, FREQUENCY, frequency_output)
    _assert_frequency_table(frequency_output, FREQUENCY)

    multi_source_output = out / "multi-source-rows-frozen.svg"
    _draw(binary, MULTI_SOURCE, multi_source_output)
    _assert_multi_source_row_patterns(multi_source_output, MULTI_SOURCE)
    single_alias_output = out / "single-source-alias-frozen.svg"
    _draw(binary, SINGLE_ALIAS, single_alias_output)
    _assert_single_logical_source_has_rendering_anchors(
        single_alias_output, SINGLE_ALIAS, "shared_source"
    )
    middle_output = out / "middle-source-frozen.svg"
    _draw(binary, MIDDLE_SOURCE, middle_output)
    source_x = _named_node_xs(
        middle_output,
        (
            "common_source", "local_source_00", "local_source_01",
            "local_source_02", "local_source_03", "local_source_04",
            "local_source_05", "local_source_06", "local_source_07",
            "mux_00", "mux_01", "mux_02", "mux_03", "mux_04",
            "mux_05", "mux_06", "mux_07",
        ),
    )
    local_xs = {source_x[name] for name in source_x if name.startswith("local_source_")}
    mux_xs = {source_x[name] for name in source_x if name.startswith("mux_")}
    if (
        len(local_xs) != 1
        or len(mux_xs) != 1
        or not source_x["common_source"] < next(iter(local_xs)) < next(iter(mux_xs))
    ):
        raise SystemExit(f"low-use roots did not move to a middle column: {source_x}")

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
    first_library, library_directory = _write_mixed_library_inputs(split_root)
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
