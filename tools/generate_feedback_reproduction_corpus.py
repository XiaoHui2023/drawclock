#!/usr/bin/env python3
"""Generate deterministic, valid JSON inputs for feedback reproduction search."""

from __future__ import annotations

import json
import random
from collections import OrderedDict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests" / "reproduction-corpus"
ROOT_KINDS = ("source", "from", "gate")


def _ordered(items: list[tuple[str, dict[str, object]]], seed: int) -> OrderedDict[str, dict[str, object]]:
    random.Random(seed).shuffle(items)
    return OrderedDict(items)


def mux_rows(seed: int, rows: int) -> OrderedDict[str, dict[str, object]]:
    items: list[tuple[str, dict[str, object]]] = []
    common_names = ["shared_wave", "shared_from", "shared_gate"]
    for name, kind in zip(common_names, ROOT_KINDS):
        items.append((name, {"kind": kind}))
    local_names: list[tuple[str, str]] = []
    for row in range(rows):
        for side in range(2):
            name = f"local_{row:02d}_{side}"
            kind = ROOT_KINDS[(row + side + seed) % len(ROOT_KINDS)]
            local_names.append((name, kind))
            items.append((name, {"kind": kind}))
    for row in range(rows):
        common = common_names[(row + seed) % len(common_names)]
        local_a = local_names[row * 2][0]
        local_b = local_names[row * 2 + 1][0]
        sources = [common, local_a, local_b]
        if (row + seed) % 2:
            sources[1], sources[2] = sources[2], sources[1]
        mux = f"mux_{row:02d}"
        items.extend([
            (mux, {"kind": "mux3", "source": {"0": sources[0], "1": sources[1], "2": sources[2]}}),
            (f"gate_{row:02d}", {"kind": "gate", "source": mux}),
            (f"div_{row:02d}", {"kind": "div", "source": f"gate_{row:02d}"}),
            (f"clock_{row:02d}", {"kind": "clock", "source": f"div_{row:02d}"}),
        ])
    return _ordered(items, seed * 101 + rows)


def pad_weave(seed: int, rows: int) -> OrderedDict[str, dict[str, object]]:
    items: list[tuple[str, dict[str, object]]] = []
    public = ["public_source", "public_from", "public_gate"]
    for name, kind in zip(public, ROOT_KINDS):
        items.append((name, {"kind": kind}))
    sparse: list[str] = []
    for row in range(rows * 2):
        name = f"sparse_{row:02d}"
        sparse.append(name)
        items.append((name, {"kind": ROOT_KINDS[(seed + row) % 3]}))
    for row in range(rows):
        first = public[(seed + row) % 3]
        second = sparse[(2 * row + seed) % len(sparse)]
        third = sparse[(2 * row + seed + rows - 1) % len(sparse)]
        sources = [first, second, third]
        shift = (seed + row) % 3
        sources = sources[shift:] + sources[:shift]
        pad = f"pad_{row:02d}"
        items.extend([
            (pad, {"kind": "pad3", "source": {"0": sources[0], "1": sources[1], "2": sources[2]}}),
            (f"mux_after_{row:02d}", {"kind": "mux2", "source": {"0": pad, "1": public[(row + 1) % 3]}}),
            (f"clock_{row:02d}", {"kind": "clock", "source": f"mux_after_{row:02d}"}),
        ])
    return _ordered(items, seed * 211 + rows)


def asymmetric(seed: int, rows: int) -> OrderedDict[str, dict[str, object]]:
    items: list[tuple[str, dict[str, object]]] = []
    roots = [f"root_{kind}" for kind in ROOT_KINDS]
    for name, kind in zip(roots, ROOT_KINDS):
        items.append((name, {"kind": kind}))
    for row in range(rows):
        left = roots[(row + seed) % 3]
        right = f"one_use_{row:02d}"
        items.append((right, {"kind": ROOT_KINDS[(row + seed + 1) % 3]}))
        items.append((f"gate_a_{row:02d}", {"kind": "gate", "source": left}))
        if (row + seed) % 3:
            items.append((f"div_a_{row:02d}", {"kind": "div", "source": f"gate_a_{row:02d}"}))
            branch_a = f"div_a_{row:02d}"
        else:
            branch_a = f"gate_a_{row:02d}"
        if (row + seed) % 2:
            items.append((f"gate_b_{row:02d}", {"kind": "gate", "source": right}))
            branch_b = f"gate_b_{row:02d}"
        else:
            branch_b = right
        items.extend([
            (f"sel_{row:02d}", {"kind": "mux2", "source": {"0": branch_a, "1": branch_b}}),
            (f"cell_{row:02d}", {"kind": "cell", "source": f"sel_{row:02d}"}),
            (f"clock_{row:02d}", {"kind": "clock", "source": f"cell_{row:02d}"}),
        ])
    return _ordered(items, seed * 307 + rows)


def middle_roots(seed: int, rows: int) -> OrderedDict[str, dict[str, object]]:
    items: list[tuple[str, dict[str, object]]] = []
    common = "early_common"
    items.append((common, {"kind": ROOT_KINDS[seed % 3]}))
    items.append(("common_stage", {"kind": "gate", "source": common}))
    for row in range(rows):
        local_a = f"late_root_{row:02d}_a"
        local_b = f"late_root_{row:02d}_b"
        items.append((local_a, {"kind": ROOT_KINDS[(seed + row + 1) % 3]}))
        items.append((local_b, {"kind": ROOT_KINDS[(seed + row + 2) % 3]}))
        ports = ["common_stage", local_a, local_b]
        rotation = (seed + row) % 3
        ports = ports[rotation:] + ports[:rotation]
        mux = f"late_mux_{row:02d}"
        items.extend([
            (mux, {"kind": "mux3", "source": {"0": ports[0], "1": ports[1], "2": ports[2]}}),
            (f"late_div_{row:02d}", {"kind": "div", "source": mux}),
            (f"late_clock_{row:02d}", {"kind": "clock", "source": f"late_div_{row:02d}"}),
        ])
    # Keep the common root causally early in an independent deep chain.
    previous = common
    for depth in range(3):
        name = f"early_chain_{depth}"
        items.append((name, {"kind": "gate" if depth != 1 else "div", "source": previous}))
        previous = name
    items.append(("early_clock", {"kind": "clock", "source": previous}))
    return _ordered(items, seed * 401 + rows)


def fixed_port_pairs(seed: int, rows: int) -> OrderedDict[str, dict[str, object]]:
    items: list[tuple[str, dict[str, object]]] = []
    for row in range(rows):
        upper = f"z_input_{row:02d}"
        lower = f"a_input_{row:02d}"
        items.append((upper, {"kind": ROOT_KINDS[(seed + row) % 3]}))
        items.append((lower, {"kind": ROOT_KINDS[(seed + row + 1) % 3]}))
        if (seed + row) % 2:
            ports = {"0": lower, "1": upper}
        else:
            ports = {"0": upper, "1": lower}
        mux = f"pair_mux_{row:02d}"
        items.extend([
            (mux, {"kind": "mux2", "source": ports}),
            (f"pair_clock_{row:02d}", {"kind": "clock", "source": mux}),
        ])
    return _ordered(items, seed * 503 + rows)


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = []
    builders = (("mux", mux_rows), ("pad", pad_weave), ("asym", asymmetric), ("middle", middle_roots), ("port", fixed_port_pairs))
    for family, builder in builders:
        for rows in (4, 8, 12):
            for seed in range(4):
                name = f"{family}-r{rows:02d}-s{seed:02d}.json"
                data = builder(seed, rows)
                (OUTPUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                records.append({"id": name.removesuffix(".json"), "path": f"tests/reproduction-corpus/{name}", "family": family, "rows": rows, "seed": seed})
    manifest = {
        "schema_version": 1,
        "coverage_model": "many_to_many",
        "factors": ["root_kind", "root_fanout", "fixed_port_order", "chain_depth", "consumer_band_gap", "feasible_root_rank", "input_insertion_order"],
        "issues": list(("FB-ROOT-001", "FB-ROUTE-002", "FB-ROOT-003", "FB-ROOT-004", "FB-BEND-005", "FB-PORT-006")),
        "cases": records,
    }
    (OUTPUT / "corpus.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
