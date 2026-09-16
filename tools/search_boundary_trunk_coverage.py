#!/usr/bin/env python3
"""Coverage-driven public-CLI search for premature bus-trunk departure."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import feedback_layout_reproduction_oracle as oracle
from svg_quality_system import evaluate_with_geometry


FACTORS = {
    "row_count": (8, 16, 24),
    "target_band": ("top", "middle", "bottom"),
    "target_membership": ("array", "external"),
    "target_offset": (2, 4),
    "misalignment_cause": ("explicit-column", "depth"),
    "common_depth": (0, 1),
    "target_common_depth": ("same", "direct", "gate"),
    "private_depth": (0, 1, 2),
    "extra_consumer": (False, True),
    "declaration_order": ("forward", "reverse", "interleaved"),
    "target_port": ("0", "1"),
    "constraint_scope": ("mux", "mux-and-common-gate"),
    "target_gate_fanout": ("single", "extra"),
    "obstacle_pattern": (
        "local", "external-anchor-only", "dual-common-weave",
        "double-weave-shared-roots",
    ),
    "external_anchor": ("first", "middle", "lower", "last", "opposed"),
}

HIGH_RISK_TRIPLES = (
    ("row_count", "target_band", "target_offset"),
    ("misalignment_cause", "target_offset", "common_depth"),
    ("target_membership", "target_band", "target_gate_fanout"),
    ("target_band", "extra_consumer", "declaration_order"),
    ("common_depth", "private_depth", "constraint_scope"),
    ("common_depth", "target_common_depth", "target_membership"),
    ("obstacle_pattern", "target_membership", "target_band"),
    ("external_anchor", "obstacle_pattern", "target_membership"),
)

# Pairwise coverage alone does not guarantee the interaction that escaped the
# former gate.  Keep named, reviewable high-order scenarios in the exact set.
REQUIRED_SCENARIOS = {
    "lower-external-anchor-extra-fanout": {
        "row_count": 24,
        "target_band": "bottom",
        "target_membership": "external",
        "target_offset": 4,
        "misalignment_cause": "explicit-column",
        "common_depth": 1,
        "target_common_depth": "same",
        "private_depth": 1,
        "extra_consumer": True,
        "declaration_order": "forward",
        "target_port": "0",
        "constraint_scope": "mux-and-common-gate",
        "target_gate_fanout": "extra",
        "obstacle_pattern": "external-anchor-only",
        "external_anchor": "lower",
    },
    "top-array-explicit-right-offset": {
        "row_count": 8,
        "target_band": "top",
        "target_membership": "array",
        "target_offset": 4,
        "misalignment_cause": "explicit-column",
        "common_depth": 1,
        "target_common_depth": "same",
        "private_depth": 1,
        "extra_consumer": False,
        "declaration_order": "forward",
        "target_port": "0",
        "constraint_scope": "mux",
        "target_gate_fanout": "single",
        "obstacle_pattern": "local",
        "external_anchor": "first",
    },
    "lower-external-target-direct-among-gates": {
        "row_count": 24,
        "target_band": "bottom",
        "target_membership": "external",
        "target_offset": 4,
        "misalignment_cause": "explicit-column",
        "common_depth": 1,
        "target_common_depth": "direct",
        "private_depth": 2,
        "extra_consumer": True,
        "declaration_order": "interleaved",
        "target_port": "1",
        "constraint_scope": "mux",
        "target_gate_fanout": "extra",
        "obstacle_pattern": "double-weave-shared-roots",
        "external_anchor": "opposed",
    },
    "middle-array-target-gate-among-direct": {
        "row_count": 16,
        "target_band": "middle",
        "target_membership": "array",
        "target_offset": 2,
        "misalignment_cause": "explicit-column",
        "common_depth": 0,
        "target_common_depth": "gate",
        "private_depth": 1,
        "extra_consumer": False,
        "declaration_order": "reverse",
        "target_port": "0",
        "constraint_scope": "mux-and-common-gate",
        "target_gate_fanout": "single",
        "obstacle_pattern": "dual-common-weave",
        "external_anchor": "first",
    },
    "visual-hit-does-not-hide-new-graphic-hit": {
        "row_count": 24,
        "target_band": "middle",
        "target_membership": "external",
        "target_offset": 2,
        "misalignment_cause": "explicit-column",
        "common_depth": 1,
        "target_common_depth": "direct",
        "private_depth": 1,
        "extra_consumer": False,
        "declaration_order": "interleaved",
        "target_port": "0",
        "constraint_scope": "mux",
        "target_gate_fanout": "single",
        "obstacle_pattern": "external-anchor-only",
        "external_anchor": "last",
    },
    "late-ranked-final-single-edge-channel": {
        "row_count": 16,
        "target_band": "bottom",
        "target_membership": "external",
        "target_offset": 2,
        "misalignment_cause": "explicit-column",
        "common_depth": 1,
        "target_common_depth": "same",
        "private_depth": 1,
        "extra_consumer": False,
        "declaration_order": "reverse",
        "target_port": "0",
        "constraint_scope": "mux",
        "target_gate_fanout": "extra",
        "obstacle_pattern": "double-weave-shared-roots",
        "external_anchor": "middle",
    },
}

DIAGNOSTIC_REPRODUCTION_SCENARIOS = {
    "lower-external-double-weave-fixed-ports": {
        **REQUIRED_SCENARIOS["lower-external-anchor-extra-fanout"],
        "obstacle_pattern": "double-weave",
    },
}

REQUIRED_SEMANTIC_DIRECTIONS = {
    json.dumps([membership, band, "right-offset"], separators=(",", ":"))
    for membership in ("array", "external")
    for band in ("top", "middle", "bottom")
}


def normalized_factors(case: dict[str, Any]) -> dict[str, Any]:
    """Collapse inapplicable dimensions instead of claiming impossible pairs."""
    result = dict(case)
    if result["target_membership"] != "external":
        result["external_anchor"] = "not-applicable"
    if not int(result["common_depth"]):
        result["constraint_scope"] = "not-applicable"
    return result


def _unit(kind: str, names: Iterable[str], values: Iterable[Any]) -> str:
    return json.dumps(
        [kind, *[[name, value] for name, value in zip(names, values)]],
        ensure_ascii=True,
        separators=(",", ":"),
    )


def coverage_units(case: dict[str, Any]) -> set[str]:
    case = normalized_factors(case)
    names = tuple(FACTORS)
    units = {
        _unit("value", (name,), (case[name],)) for name in names
    }
    units.update(
        _unit("pair", (left, right), (case[left], case[right]))
        for left_index, left in enumerate(names)
        for right in names[left_index + 1:]
    )
    units.update(
        _unit("triple", triple, (case[name] for name in triple))
        for triple in HIGH_RISK_TRIPLES
    )
    return units


def _activated(case: dict[str, Any], varied: set[str]) -> dict[str, Any]:
    """Make conditional dimensions applicable when their values are varied."""
    result = dict(case)
    if "external_anchor" in varied:
        result["target_membership"] = "external"
    if "constraint_scope" in varied:
        result["common_depth"] = 1
    return result


def candidate_cases() -> list[dict[str, Any]]:
    """Construct every required 1/2-way and selected 3-way interaction."""
    base = {name: values[0] for name, values in FACTORS.items()}
    candidates = [dict(base), *map(dict, REQUIRED_SCENARIOS.values())]
    names = tuple(FACTORS)
    for width in (1, 2):
        for selected in itertools.combinations(names, width):
            for values in itertools.product(*(FACTORS[name] for name in selected)):
                case = dict(base)
                case.update(zip(selected, values))
                candidates.append(_activated(case, set(selected)))
    for selected in HIGH_RISK_TRIPLES:
        for values in itertools.product(*(FACTORS[name] for name in selected)):
            case = dict(base)
            case.update(zip(selected, values))
            candidates.append(_activated(case, set(selected)))
    # A fixed-seed balanced pool lets one executable case satisfy many units.
    # The seed only makes compaction reproducible; exact-set membership below
    # remains the pass/fail oracle.
    generator = random.Random(23023)
    for _index in range(4096):
        candidates.append({
            name: generator.choice(values) for name, values in FACTORS.items()
        })
    unique: dict[str, dict[str, Any]] = {}
    for case in candidates:
        unique[json.dumps(case, sort_keys=True)] = case
    return list(unique.values())


def required_units() -> set[str]:
    required: set[str] = set()
    for case in candidate_cases():
        required.update(coverage_units(case))
    required.update(
        _unit("scenario", ("name",), (name,))
        for name in REQUIRED_SCENARIOS
    )
    return required


def covering_suite() -> list[dict[str, Any]]:
    candidates = candidate_cases()
    candidate_rows = [(case, coverage_units(case)) for case in candidates]
    uncovered = required_units()
    suite: list[dict[str, Any]] = [
        dict(case) for case in REQUIRED_SCENARIOS.values()
    ]
    for name, case in REQUIRED_SCENARIOS.items():
        uncovered.difference_update(coverage_units(case))
        uncovered.discard(_unit("scenario", ("name",), (name,)))
    while uncovered:
        best, best_units = max(
            candidate_rows,
            key=lambda row: (
                len(row[1] & uncovered),
                int(row[0]["row_count"]),
                row[0]["target_band"] == "bottom",
                int(row[0]["target_offset"]),
                bool(row[0]["extra_consumer"]),
                row[0]["constraint_scope"] == "mux-and-common-gate",
                row[0]["obstacle_pattern"] == "double-weave",
            ),
        )
        gained = best_units & uncovered
        if not gained:
            raise RuntimeError("coverage model cannot close required exact-set")
        suite.append(best)
        uncovered.difference_update(gained)
        candidate_rows.remove((best, best_units))
    return suite


def scenario_units(case: dict[str, Any]) -> set[str]:
    return {
        _unit("scenario", ("name",), (name,))
        for name, required in REQUIRED_SCENARIOS.items()
        if case == required
    }


def is_target_reproduction(
    witnessed: list[dict[str, Any]],
    semantic_preconditions_met: bool,
    failed_metric_ids: list[str],
) -> bool:
    """Accept the expected target red light, reject every other failure."""
    return (
        bool(witnessed)
        and semantic_preconditions_met
        and failed_metric_ids == ["premature_interior_trunk_entry"]
    )


def build_case(factors: dict[str, Any]) -> dict[str, dict[str, Any]]:
    row_count = int(factors["row_count"])
    target_index = {
        "top": 0,
        "middle": row_count // 2,
        "bottom": row_count - 1,
    }[str(factors["target_band"])]
    if factors["target_membership"] == "external":
        target_index = -1
    public_port = str(factors["target_port"])
    private_port = "1" if public_port == "0" else "0"
    blocks: list[list[tuple[str, dict[str, Any]]]] = []

    def branch_common_depth(is_target: bool) -> int:
        depth = int(factors["common_depth"])
        if not is_target:
            return depth
        override = str(factors["target_common_depth"])
        if override == "direct":
            return 0
        if override == "gate":
            return 1
        return depth

    for index in range(row_count):
        suffix = f"{index:02d}"
        is_target = index == target_index
        block: list[tuple[str, dict[str, Any]]] = []
        if branch_common_depth(is_target):
            common_name = f"common_gate_{suffix}"
            common_item: dict[str, Any] = {
                "kind": "gate", "source": "common_from"
            }
            if (
                is_target
                and factors["misalignment_cause"] == "explicit-column"
                and factors["constraint_scope"] == "mux-and-common-gate"
            ):
                common_item["layout_column"] = 4 + int(
                    factors["target_offset"]
                )
            block.append((common_name, common_item))
        else:
            common_name = "common_from"
        private_name = f"private_from_{suffix}"
        block.append((private_name, {"kind": "from"}))
        previous = private_name
        block.append((f"private_gate_{suffix}", {
            "kind": "gate", "source": previous,
        }))
        previous = f"private_gate_{suffix}"
        private_depth = int(factors["private_depth"])
        if is_target and factors["misalignment_cause"] == "depth":
            private_depth += int(factors["target_offset"])
        for depth in range(private_depth):
            div_name = f"private_div_{suffix}_{depth}"
            block.append((div_name, {"kind": "div", "source": previous}))
            previous = div_name
        mux_name = f"mux_{suffix}"
        mux_item: dict[str, Any] = {
            "kind": "mux2",
            "source": {public_port: common_name, private_port: previous},
        }
        if factors["misalignment_cause"] == "explicit-column":
            mux_item["layout_column"] = (
                5 + int(factors["target_offset"])
                if is_target else 5
            )
        block.append((mux_name, mux_item))
        block.append((f"clock_{suffix}", {"kind": "clock", "source": mux_name}))
        if (
            is_target
            and factors["target_gate_fanout"] == "extra"
        ):
            block.append((f"common_probe_{suffix}", {
                "kind": "clock", "source": common_name,
            }))
        blocks.append(block)

    if factors["target_membership"] == "external":
        external: list[tuple[str, dict[str, Any]]] = []
        if branch_common_depth(True):
            common_name = "external_common_gate"
            common_item = {"kind": "gate", "source": "common_from"}
            if (
                factors["misalignment_cause"] == "explicit-column"
                and factors["constraint_scope"] == "mux-and-common-gate"
            ):
                common_item["layout_column"] = 4 + int(
                    factors["target_offset"]
                )
            external.append((common_name, common_item))
        else:
            common_name = "common_from"
        external.append(("external_private_from", {"kind": "from"}))
        previous = "external_private_from"
        external.append(("external_private_gate", {
            "kind": "gate", "source": previous,
        }))
        previous = "external_private_gate"
        external_depth = int(factors["private_depth"])
        if factors["misalignment_cause"] == "depth":
            external_depth += int(factors["target_offset"])
        for depth in range(external_depth):
            name = f"external_private_div_{depth}"
            external.append((name, {"kind": "div", "source": previous}))
            previous = name
        external_mux: dict[str, Any] = {
            "kind": "mux2",
            "source": {public_port: common_name, private_port: previous},
        }
        if factors["misalignment_cause"] == "explicit-column":
            external_mux["layout_column"] = 5 + int(factors["target_offset"])
        external.append(("external_mux", external_mux))
        external.append(("external_clock", {
            "kind": "clock", "source": "external_mux",
        }))
        if factors["target_gate_fanout"] == "extra":
            external.append(("external_common_probe", {
                "kind": "clock", "source": common_name,
            }))
        insert_at = {
            "top": 0,
            "middle": len(blocks) // 2,
            "bottom": len(blocks),
        }[str(factors["target_band"])]
        blocks.insert(insert_at, external)

    entries: list[tuple[str, dict[str, Any]]] = [
        ("common_from", {"kind": "from"})
    ]
    if factors["declaration_order"] == "reverse":
        blocks.reverse()
    elif factors["declaration_order"] == "interleaved":
        blocks = blocks[::2] + blocks[1::2]
    entries.extend(item for block in blocks for item in block)
    if bool(factors["extra_consumer"]):
        entries.extend([
            ("common_aux_gate", {"kind": "gate", "source": "common_from"}),
            ("common_aux_clock", {"kind": "clock", "source": "common_aux_gate"}),
        ])
    config = dict(entries)

    def private_terminal(index: int) -> str:
        suffix = f"{index:02d}"
        depth = int(factors["private_depth"])
        if index == target_index and factors["misalignment_cause"] == "depth":
            depth += int(factors["target_offset"])
        if depth == 0:
            return f"private_gate_{suffix}"
        return f"private_div_{suffix}_{depth - 1}"

    pattern = str(factors["obstacle_pattern"])
    if (
        pattern == "external-anchor-only"
        and factors["target_membership"] == "external"
    ):
        anchor_index = {
            "first": 0,
            "middle": row_count // 2,
            "lower": (3 * row_count) // 4,
            "last": row_count - 1,
            "opposed": 0,
        }[str(factors["external_anchor"])]
        mux = config["external_mux"]
        spare_port = next(
            port for port in ("0", "1", "2")
            if port not in {public_port, private_port}
        )
        mux["kind"] = "mux3"
        mux["source"] = {
            public_port: mux["source"][public_port],
            private_port: private_terminal(anchor_index),
            spare_port: previous,
        }
    if pattern == "dual-common-weave":
        config["obstacle_from"] = {"kind": "from"}
        for index in range(row_count):
            config[f"obstacle_gate_{index:02d}"] = {
                "kind": "gate", "source": "obstacle_from",
            }
        for index in range(row_count):
            mux = config[f"mux_{index:02d}"]
            reverse_index = row_count - 1 - index
            available = iter(
                port for port in ("0", "1", "2", "3")
                if port not in {public_port, private_port}
            )
            mux["kind"] = "mux4"
            mux["source"] = {
                **mux["source"],
                next(available): f"obstacle_gate_{index:02d}",
                next(available): f"obstacle_gate_{reverse_index:02d}",
            }
        if factors["target_membership"] == "external":
            mux = config["external_mux"]
            anchor_index = {
                "first": 0,
                "middle": row_count // 2,
                "lower": (3 * row_count) // 4,
                "last": row_count - 1,
                "opposed": 0,
            }[str(factors["external_anchor"])]
            available = iter(
                port for port in ("0", "1", "2", "3")
                if port not in {public_port, private_port}
            )
            mux["kind"] = "mux4"
            mux["source"] = {
                **mux["source"],
                next(available): f"obstacle_gate_{anchor_index:02d}",
                next(available): (
                    f"obstacle_gate_{row_count - 1 - anchor_index:02d}"
                ),
            }
    if pattern == "double-weave-shared-roots":
        for index in range(row_count):
            config[f"private_root_probe_{index:02d}"] = {
                "kind": "clock", "source": f"private_from_{index:02d}",
            }
    if pattern in {
        "reverse", "cyclic", "double-weave", "double-weave-shared-roots",
    }:
        for index in range(row_count):
            source_index = (
                row_count - 1 - index if pattern == "reverse"
                else (index + max(1, row_count // 2)) % row_count
            )
            config[f"mux_{index:02d}"]["source"][private_port] = (
                private_terminal(source_index)
            )
        if (
            factors["target_membership"] == "external"
            and pattern != "external-anchor-only"
        ):
            source_index = {
                "first": 0,
                "middle": row_count // 2,
                "lower": (3 * row_count) // 4,
                "last": row_count - 1,
                "opposed": 0,
            }[str(factors["external_anchor"])]
            config["external_mux"]["source"][private_port] = (
                private_terminal(source_index)
            )
    if pattern in {"double-weave", "double-weave-shared-roots"}:
        spare_port = next(
            port for port in ("0", "1", "2")
            if port not in {public_port, private_port}
        )
        for index in range(row_count):
            reverse_index = row_count - 1 - index
            cyclic_index = (index + max(1, row_count // 3)) % row_count
            mux = config[f"mux_{index:02d}"]
            mux["kind"] = "mux3"
            mux["source"] = {
                public_port: mux["source"][public_port],
                private_port: private_terminal(reverse_index),
                spare_port: private_terminal(cyclic_index),
            }
        if factors["target_membership"] == "external":
            mux = config["external_mux"]
            mux["kind"] = "mux3"
            first_index, second_index = {
                "first": (0, max(1, row_count // 3)),
                "middle": (row_count // 2, (row_count // 2 + row_count // 3) % row_count),
                "lower": ((3 * row_count) // 4, (2 * row_count) // 3),
                "last": (row_count - 1, row_count // 2),
                "opposed": (0, row_count - 1),
            }[str(factors["external_anchor"])]
            mux["source"] = {
                public_port: mux["source"][public_port],
                private_port: private_terminal(first_index),
                spare_port: private_terminal(second_index),
            }
    return config


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--expect", choices=("reproduced", "clean"), default="reproduced"
    )
    parser.add_argument(
        "--producer-root", type=Path, default=ROOT,
        help="Checkout containing the frozen public CLI and component library.",
    )
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.producer_root = args.producer_root.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    suite = covering_suite()
    required = required_units()
    covered: set[str] = set()
    results = []
    first_reproduction = None
    for index, factors in enumerate(suite):
        case_dir = args.output / f"case-{index:03d}"
        case_dir.mkdir(parents=True, exist_ok=True)
        input_path = case_dir / "input.json"
        svg_path = case_dir / "output.svg"
        input_path.write_text(
            json.dumps(build_case(factors), indent=2) + "\n", encoding="utf-8"
        )
        run = subprocess.run(
            [sys.executable, str(args.producer_root / "src"),
             "-i", str(input_path),
             "-l", str(args.producer_root / "drawio-lib"),
             "-o", str(svg_path),
             "--crossing-style", "arc"],
            cwd=args.producer_root, capture_output=True, check=False,
        )
        if run.returncode or not svg_path.is_file():
            detail = run.stderr.decode(errors="replace")[-1000:]
            print(
                f"operational_error case={index} exit={run.returncode}: {detail}",
                file=sys.stderr,
            )
            return 2
        quality, report = evaluate_with_geometry(
            input_path, svg_path, ROOT / "tests/quality-metrics.json"
        )
        config = json.loads(input_path.read_text(encoding="utf-8"))
        target_name = (
            "external_mux" if factors["target_membership"] == "external"
            else f"mux_{({'top': 0, 'middle': int(factors['row_count']) // 2, 'bottom': int(factors['row_count']) - 1}[str(factors['target_band'])]):02d}"
        )
        boxes, _routes = oracle.parse_svg(svg_path, set(config))
        mux_centers = {
            box.node: (box.x + box.w / 2.0, box.y + box.h / 2.0)
            for box in boxes
            if box.node in config
            and str(config[box.node].get("kind", "")).startswith("mux")
        }
        peers = [
            point for name, point in mux_centers.items() if name != target_name
        ]
        target_center = mux_centers.get(target_name)
        if target_center is None or not peers:
            print(
                f"semantic_error case={index} target={target_name} "
                f"factors={json.dumps(factors, sort_keys=True)}: "
                "target geometry missing",
                file=sys.stderr,
            )
            return 3
        ordered_y = sorted([point[1] for point in peers] + [target_center[1]])
        rank = ordered_y.index(target_center[1]) / max(1, len(ordered_y) - 1)
        actual_band = "top" if rank <= 0.25 else "bottom" if rank >= 0.75 else "middle"
        right_offset = target_center[0] - max(point[0] for point in peers)
        semantic_preconditions_met = right_offset > oracle.EPS
        witnessed = report["witnesses"][
            "premature_interior_trunk_entry_witnesses"
        ]
        observed_factors = dict(factors)
        observed_factors["target_band"] = actual_band
        # Factor coverage proves what was generated.  Observed geometry is a
        # separate semantic receipt and must never rewrite the input model.
        covered.update(coverage_units(factors))
        covered.update(scenario_units(factors))
        row = {
            "case_id": f"case-{index:03d}",
            "factors": factors,
            "observed_factors": observed_factors,
            "target_node": target_name,
            "target_center": [round(value, 4) for value in target_center],
            "target_right_offset_px": round(right_offset, 4),
            "semantic_preconditions_met": semantic_preconditions_met,
            "input_sha256": _sha256(input_path),
            "svg_sha256": _sha256(svg_path),
            "premature_witnesses": witnessed,
            "failed_metric_ids": quality["failed_metric_ids"],
        }
        results.append(row)
        (case_dir / "result.json").write_text(
            json.dumps(row, indent=2) + "\n", encoding="utf-8"
        )
        if (
            is_target_reproduction(
                witnessed,
                semantic_preconditions_met,
                quality["failed_metric_ids"],
            )
            and first_reproduction is None
        ):
            first_reproduction = row
            if args.expect == "reproduced":
                break

    payload = {
        "schema_version": 1,
        "expect": args.expect,
        "lineage": {
            "producer_src_sha256": _tree_sha256(args.producer_root / "src"),
            "runner_sha256": _sha256(Path(__file__).resolve()),
            "oracle_sha256": _sha256(Path(oracle.__file__).resolve()),
            "metric_registry_sha256": _sha256(
                ROOT / "tests" / "quality-metrics.json"
            ),
        },
        "suite_size": len(suite),
        "executed_cases": len(results),
        "required_coverage_units": sorted(required),
        "covered_coverage_units": sorted(covered),
        "missing_coverage_units": sorted(required - covered),
        "semantic_direction_coverage": sorted({
            json.dumps([
                row["factors"]["target_membership"],
                row["observed_factors"]["target_band"],
                "right-offset" if row["semantic_preconditions_met"] else "aligned-or-left",
            ], separators=(",", ":"))
            for row in results
        }),
        "required_semantic_directions": sorted(REQUIRED_SEMANTIC_DIRECTIONS),
        "missing_semantic_directions": sorted(
            REQUIRED_SEMANTIC_DIRECTIONS - {
                json.dumps([
                    row["factors"]["target_membership"],
                    row["observed_factors"]["target_band"],
                    "right-offset" if row["semantic_preconditions_met"] else "aligned-or-left",
                ], separators=(",", ":"))
                for row in results
            }
        ),
        "quality_failure_cases": [
            row["case_id"] for row in results if row["failed_metric_ids"]
        ],
        "first_reproduction": first_reproduction,
        "results": results,
    }
    (args.output / "coverage-receipt.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    if args.expect == "reproduced":
        if first_reproduction is None:
            print("not_reproduced: coverage exact-set exhausted", file=sys.stderr)
            return 1
        print(json.dumps(first_reproduction, indent=2))
        return 0
    if (
        first_reproduction is not None
        or required != covered
        or payload["missing_semantic_directions"]
        or payload["quality_failure_cases"]
    ):
        print("clean coverage gate failed", file=sys.stderr)
        return 1
    print(f"clean coverage complete cases={len(results)} units={len(covered)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
