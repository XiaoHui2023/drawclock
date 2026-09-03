from __future__ import annotations

import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "example" / "auto-layout"


def build(domain_count: int) -> dict[str, dict[str, object]]:
    config: dict[str, dict[str, object]] = {
        "xtal_0": {"kind": "source", "source_kind": "source"},
        "xtal_1": {"kind": "source", "source_kind": "source"},
    }
    for pll_index in range(4):
        name = f"pll_{pll_index}"
        config[name] = {
            "kind": "pll",
            "pll_kind": "SC",
            "source": f"xtal_{pll_index % 2}",
        }

    output_cells = ("occ_clk_cell", "gen_cell", "bist_clk_cell")
    for domain in range(domain_count):
        prefix = f"d{domain:03d}"
        bank = min(3, domain * 4 // domain_count)
        mux = f"mux_{prefix}"
        divider = f"div_{prefix}"
        gate = f"gate_{prefix}"
        cell = f"cell_{prefix}"
        config[mux] = {
            "kind": "mux3",
            "source": {
                "0": f"xtal_{bank % 2}",
                "1": f"pll_{bank}",
                "2": f"pll_{(bank + 1) % 4}",
            },
        }
        config[divider] = {
            "kind": "div_r" if domain % 3 == 0 else "div",
            "ratio": str(2 ** (1 + domain % 5)),
            "source": mux,
        }
        config[gate] = {"kind": "gate", "source": divider}
        config[cell] = {
            "kind": "cell",
            "cell_kind": output_cells[domain % len(output_cells)],
            "source": gate,
        }
        if domain % 8 == 7:
            config[f"occ_bist_{prefix}"] = {
                "kind": "cell",
                "cell_kind": "occ_bist_clk_cell",
                "source": gate,
            }
        for leaf in range(4):
            config[f"clk_{prefix}_{leaf}"] = {
                "kind": "clock",
                "freq": f"{25 * (1 + (domain + leaf) % 16)} MHz",
                "source": cell,
            }
    return config


def build_dual_from_reuse(branch_count: int = 16) -> dict[str, dict[str, object]]:
    """Two shared roots feeding asymmetric, repeated mux domains."""
    config: dict[str, dict[str, object]] = {
        "from_a": {"kind": "from"},
        "from_b": {"kind": "from"},
    }
    for branch in range(branch_count):
        suffix = f"{branch:02d}"
        config[f"gate_a_{suffix}"] = {"kind": "gate", "source": "from_a"}
        config[f"div_{suffix}"] = {
            "kind": "div",
            "source": f"gate_a_{suffix}",
        }
        config[f"gate_b_{suffix}"] = {"kind": "gate", "source": "from_b"}
        config[f"sel_{suffix}"] = {
            "kind": "mux2",
            "source": {
                "0": f"div_{suffix}",
                "1": f"gate_b_{suffix}",
            },
        }
        config[f"cell_{suffix}"] = {
            "kind": "cell",
            "source": f"sel_{suffix}",
        }
        config[f"clk_{suffix}"] = {
            "kind": "clock",
            "source": f"cell_{suffix}",
        }
    return config


def build_multi_from_clusters(
    cluster_count: int = 4, branches_per_cluster: int = 6
) -> dict[str, dict[str, object]]:
    """Shared ``from`` roots whose consumers occupy distinct vertical bands."""
    roots = [f"from_{index}" for index in range(cluster_count)]
    config: dict[str, dict[str, object]] = {
        name: {"kind": "from"} for name in roots
    }
    for cluster in range(cluster_count):
        for branch in range(branches_per_cluster):
            suffix = f"{cluster}_{branch:02d}"
            config[f"gate_primary_{suffix}"] = {
                "kind": "gate", "source": roots[cluster]
            }
            config[f"div_{suffix}"] = {
                "kind": "div", "source": f"gate_primary_{suffix}"
            }
            config[f"gate_backup_{suffix}"] = {
                "kind": "gate",
                "source": roots[(cluster + 1) % cluster_count],
            }
            config[f"sel_{suffix}"] = {
                "kind": "mux2",
                "source": {
                    "0": f"div_{suffix}",
                    "1": f"gate_backup_{suffix}",
                },
            }
            config[f"cell_{suffix}"] = {
                "kind": "cell", "source": f"sel_{suffix}"
            }
            config[f"clk_{suffix}"] = {
                "kind": "clock", "source": f"cell_{suffix}"
            }
    return config


def build_terminal_fanout_crossing() -> dict[str, dict[str, object]]:
    """Minimal A-B-A sink ordering trap: one branch fans out, one does not."""
    return {
        "root": {"kind": "from"},
        "gate_a": {"kind": "gate", "source": "root"},
        "gate_b": {"kind": "gate", "source": "root"},
        "clock_a": {"kind": "clock", "source": "gate_a"},
        "clock_m": {"kind": "clock", "source": "gate_b"},
        "clock_z": {"kind": "clock", "source": "gate_a"},
    }


def build_asymmetric_merge_columns(
    domain_count: int = 8,
) -> dict[str, dict[str, object]]:
    """Equivalent reconvergences with complementary pre/post-merge depth."""
    config: dict[str, dict[str, object]] = {
        "root_a": {"kind": "from"},
        "root_b": {"kind": "from"},
    }
    for domain in range(domain_count):
        suffix = f"{domain:02d}"
        config[f"gate_a_{suffix}"] = {"kind": "gate", "source": "root_a"}
        config[f"gate_b_{suffix}"] = {"kind": "gate", "source": "root_b"}
        left = f"gate_a_{suffix}"
        if domain % 2 == 0:
            config[f"div_pre_{suffix}"] = {"kind": "div", "source": left}
            left = f"div_pre_{suffix}"
        config[f"merge_{suffix}"] = {
            "kind": "mux2",
            "source": {"0": left, "1": f"gate_b_{suffix}"},
        }
        tail = f"merge_{suffix}"
        if domain % 2 == 1:
            config[f"div_post_{suffix}"] = {"kind": "div", "source": tail}
            tail = f"div_post_{suffix}"
        config[f"cell_{suffix}"] = {"kind": "cell", "source": tail}
        config[f"clock_{suffix}"] = {"kind": "clock", "source": f"cell_{suffix}"}
    return config


def build_dispersed_root_fanout() -> dict[str, dict[str, object]]:
    """Many roots weave through irregular direct, pad, and hybrid rows."""
    roots = tuple(f"source_{letter}" for letter in "abcdefgh")
    config: dict[str, dict[str, object]] = {
        root: {"kind": "source"} for root in roots
    }

    pad_inputs = (
        ("source_a", "source_b", "source_c"),
        ("source_d", "source_e", "source_f"),
        ("source_a", "source_d", "source_g"),
        ("source_b", "source_e", "source_h"),
        ("source_c", "source_f", "source_a"),
        ("source_d", None, "source_b"),
        (None, "source_e", "source_c"),
        ("source_f", "source_g", "source_a"),
    )
    for index, sources in enumerate(pad_inputs):
        config[f"input_pad_{index}"] = {
            "kind": "pad3",
            "source": {
                str(port): source
                for port, source in enumerate(sources)
                if source is not None
            },
        }

    def add_terminal_row(index: int, source: str) -> None:
        suffix = f"{index:02d}"
        tail = source
        config[f"row_gate_{suffix}"] = {"kind": "gate", "source": tail}
        tail = f"row_gate_{suffix}"
        if index % 3 != 0:
            config[f"row_div_{suffix}"] = {"kind": "div", "source": tail}
            tail = f"row_div_{suffix}"
        if index % 4 in {2, 3}:
            config[f"row_cell_{suffix}"] = {"kind": "cell", "source": tail}
            tail = f"row_cell_{suffix}"
        config[f"row_clock_{suffix}"] = {"kind": "clock", "source": tail}

    direct_sequence = (
        "source_a", "source_b", "source_c", "source_a",
        "source_d", "source_b", "source_e", "source_a",
        "source_c", "source_f", "source_b", "source_d",
        "source_a", "source_g", "source_c", "source_e",
        "source_b", "source_h", "source_a", "source_d",
        "source_f", "source_c", "source_b", "source_g",
    )
    row_index = 0
    for source in direct_sequence:
        add_terminal_row(row_index, source)
        row_index += 1

    pad_fanouts = (1, 3, 2, 4, 1, 2, 1, 2)
    for pad_index, fanout in enumerate(pad_fanouts):
        for _ in range(fanout):
            add_terminal_row(row_index, f"input_pad_{pad_index}")
            row_index += 1

    hybrid_sources = (
        "source_h", "source_a", "source_e", "source_c",
        "source_g", "source_f", "source_b", "source_h",
    )
    for pad_index, source in enumerate(hybrid_sources):
        select = f"row_select_{row_index:02d}"
        config[select] = {
            "kind": "mux2",
            "source": {"0": f"input_pad_{pad_index}", "1": source},
        }
        add_terminal_row(row_index, select)
        row_index += 1

    assert row_index == 48
    return config


def build_single_source_rendering_alias(
    middle_domains: int = 12,
) -> dict[str, dict[str, object]]:
    """One logical root gains a local rendering anchor near a distant child."""
    config: dict[str, dict[str, object]] = {
        "shared_source": {"kind": "from"},
        "near_gate": {"kind": "gate", "source": "shared_source"},
        "fanout_hub": {"kind": "gate", "source": "shared_source"},
    }
    for index in range(middle_domains):
        suffix = f"{index:02d}"
        branch = f"fanout_branch_{suffix}"
        config[branch] = {"kind": "gate", "source": "fanout_hub"}
        if index == 0:
            branch_name = "near_merge"
            config[branch_name] = {
                "kind": "mux2",
                "source": {"0": "near_gate", "1": branch},
            }
            branch = branch_name
        config[f"fanout_clock_{suffix}"] = {"kind": "clock", "source": branch}
    return config


def build_middle_column_low_use_sources(
    domain_count: int = 8,
) -> dict[str, dict[str, object]]:
    """Low-use roots move beside their muxes while one shared root stays early."""
    config: dict[str, dict[str, object]] = {
        "common_source": {"kind": "from"},
        "common_stage_1": {"kind": "gate", "source": "common_source"},
        "common_stage_2": {"kind": "div", "source": "common_stage_1"},
        "common_stage_3": {"kind": "cell", "source": "common_stage_2"},
    }
    for index in range(domain_count):
        suffix = f"{index:02d}"
        common_branch = f"common_branch_{suffix}"
        local_source = f"local_source_{suffix}"
        mux = f"mux_{suffix}"
        cell = f"cell_{suffix}"
        config[common_branch] = {"kind": "gate", "source": "common_stage_3"}
        config[local_source] = {"kind": "from"}
        config[mux] = {
            "kind": "mux2",
            "source": {"0": common_branch, "1": local_source},
        }
        config[cell] = {"kind": "cell", "source": mux}
        config[f"clock_{suffix}"] = {"kind": "clock", "source": cell}
    return config


def build_mixed_root_port_order_torture(
    domain_count: int = 12,
) -> dict[str, dict[str, object]]:
    """Mixed-kind graph roots stress placement, port order, trunks and bends."""
    config: dict[str, dict[str, object]] = {
        "common_source": {"kind": "source"},
        "common_from": {"kind": "from"},
        # ``gate`` deliberately has no upstream edge.  It proves that root
        # treatment is derived from graph degree, not a component-name list.
        "common_gate_root": {"kind": "gate"},
    }
    root_kinds = ("from", "source", "gate")
    for index in range(domain_count):
        suffix = f"{index:02d}"
        local_a = f"local_a_{suffix}"
        local_b = f"local_b_{suffix}"
        config[local_a] = {"kind": root_kinds[index % len(root_kinds)]}
        config[local_b] = {"kind": root_kinds[(index + 1) % len(root_kinds)]}
        common = ("common_source", "common_from", "common_gate_root")[index % 3]
        # Rotate logical declaration order independently from fixed pad ports.
        # A good layout orders the two one-use roots by their destination ports
        # and lets them occupy a late feasible column beside this pad.
        inputs = (
            {"0": common, "1": local_a, "2": local_b},
            {"0": local_b, "1": common, "2": local_a},
            {"0": local_a, "1": local_b, "2": common},
        )[index % 3]
        pad = f"pad_{suffix}"
        config[pad] = {"kind": "pad3", "source": inputs}
        tail = pad
        if index % 2:
            config[f"div_{suffix}"] = {"kind": "div", "source": tail}
            tail = f"div_{suffix}"
        config[f"cell_{suffix}"] = {"kind": "cell", "source": tail}
        config[f"clock_{suffix}"] = {"kind": "clock", "source": f"cell_{suffix}"}
    return config


def build_asymmetric_merge_route_bulge(
    *, long_branch: str = "b"
) -> dict[str, dict[str, object]]:
    """Minimal fixed-port fan-in trap with one reused asymmetric parent."""
    if long_branch not in {"a", "b"}:
        raise ValueError("long_branch must be 'a' or 'b'")
    config: dict[str, dict[str, object]] = {
        "from_a": {"kind": "from"},
        "from_b": {"kind": "from"},
        "gate_a": {"kind": "gate", "source": "from_a"},
        "gate_b": {"kind": "gate", "source": "from_b"},
    }
    config[f"div_{long_branch}"] = {
        "kind": "div",
        "source": f"gate_{long_branch}",
    }
    inputs = {
        "0": "div_a" if long_branch == "a" else "gate_a",
        "1": "div_b" if long_branch == "b" else "gate_b",
    }
    config["sel"] = {"kind": "mux2", "source": inputs}
    config["cell"] = {"kind": "cell", "source": "sel"}
    config["clock"] = {"kind": "clock", "source": "cell"}
    reused_branch = "b" if long_branch == "a" else "a"
    config[f"gate_{reused_branch}_tap"] = {
        "kind": "clock",
        "source": f"gate_{reused_branch}",
    }
    return config


def _prefix_config(
    config: dict[str, dict[str, object]],
    prefix: str,
    *,
    kind_overrides: dict[str, str] | None = None,
) -> dict[str, dict[str, object]]:
    """Namespace a topology while preserving source ports and public schema."""
    overrides = kind_overrides or {}

    def rename_source(value: object) -> object:
        if isinstance(value, str):
            if "[" in value:
                node, selector = value.split("[", 1)
                return f"{prefix}{node}[{selector}"
            return f"{prefix}{value}"
        if isinstance(value, dict):
            return {port: rename_source(source) for port, source in value.items()}
        return value

    result: dict[str, dict[str, object]] = {}
    for name, node in config.items():
        copied = dict(node)
        copied["kind"] = overrides.get(str(copied["kind"]), copied["kind"])
        if "source" in copied:
            copied["source"] = rename_source(copied["source"])
        result[f"{prefix}{name}"] = copied
    return result


def build_feedback_reproduction_combined() -> dict[str, dict[str, object]]:
    """Complex public example assembled only from general topology features."""
    weave_items: list[tuple[str, dict[str, object]]] = []
    public = ("public_source", "public_from", "public_gate")
    for name, kind in zip(public, ("source", "from", "gate")):
        weave_items.append((name, {"kind": kind}))
    sparse = [f"sparse_{index:02d}" for index in range(16)]
    for index, name in enumerate(sparse):
        weave_items.append((name, {"kind": ("source", "from", "gate")[index % 3]}))
    for row in range(8):
        sources = [public[row % 3], sparse[2 * row], sparse[(2 * row + 7) % len(sparse)]]
        shift = row % 3
        sources = sources[shift:] + sources[:shift]
        weave_items.extend(
            (
                (f"merge_{row:02d}", {"kind": "mux3", "source": {"0": sources[0], "1": sources[1], "2": sources[2]}}),
                (f"select_{row:02d}", {"kind": "mux2", "source": {"0": f"merge_{row:02d}", "1": public[(row + 1) % 3]}}),
                (f"clock_{row:02d}", {"kind": "clock", "source": f"select_{row:02d}"}),
            )
        )
    random.Random(8).shuffle(weave_items)
    combined = _prefix_config(dict(weave_items), "weave__")
    combined.update(
        _prefix_config(
            build_mixed_root_port_order_torture(12),
            "roots__",
            kind_overrides={"pad3": "mux3"},
        )
    )
    combined.update(_prefix_config(build_asymmetric_merge_route_bulge(), "ports__"))
    return combined


def build_adversarial_weave(
    domain_count: int,
    *,
    clocks_per_domain: int,
    long_names: bool = False,
) -> dict[str, dict[str, object]]:
    """Cross-root, multi-stage mux network with deliberately permuted reuse."""
    root_names = [
        (
            f"reference_clock_source_with_long_instance_name_{index}"
            if long_names
            else f"ref_{index}"
        )
        for index in range(4)
    ]
    config: dict[str, dict[str, object]] = {
        name: {"kind": "source", "source_kind": "source"}
        for name in root_names
    }
    pll_names: list[str] = []
    for index in range(4):
        name = f"pll_dual_{index}"
        pll_names.append(name)
        config[name] = {
            "kind": "pll2",
            "pll_kind": "INNO",
            "source": root_names[(index * 3) % len(root_names)],
        }

    cell_kinds = ("occ_clk_cell", "gen_cell", "bist_clk_cell")
    for domain in range(domain_count):
        suffix = f"{domain:03d}"
        label = (
            f"subsystem_clock_domain_with_long_instance_name_{suffix}"
            if long_names
            else f"domain_{suffix}"
        )
        select_a = f"select_primary_{label}"
        gate_a = f"gate_primary_{label}"
        divide = f"divide_primary_{label}"
        select_b = f"select_reconvergent_{label}"
        dto = f"dto_trim_{label}"
        cell = f"cell_output_{label}"
        config[select_a] = {
            "kind": "mux3",
            "source": {
                "0": root_names[(domain * 3) % 4],
                "1": f"{pll_names[(domain + 1) % 4]}[0]",
                "2": f"{pll_names[(domain * 3 + 2) % 4]}[1]",
            },
        }
        config[gate_a] = {"kind": "gate", "source": select_a}
        config[divide] = {
            "kind": "div_r" if domain % 2 else "div",
            "ratio": str(2 ** (1 + domain % 5)),
            "source": gate_a,
        }
        config[select_b] = {
            "kind": "mux3",
            "source": {
                "0": divide,
                "1": root_names[(domain + 2) % 4],
                "2": f"{pll_names[(domain * 5 + 3) % 4]}[{domain % 2}]",
            },
        }
        config[dto] = {"kind": "dto", "source": select_b}
        config[cell] = {
            "kind": "cell",
            "cell_kind": cell_kinds[domain % len(cell_kinds)],
            "source": dto,
        }
        for leaf in range(clocks_per_domain):
            config[f"clock_{label}_{leaf:02d}"] = {
                "kind": "clock",
                "freq": f"{25 * (1 + (domain + leaf) % 32)} MHz",
                "source": cell,
            }
    return config


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scenarios = (
        ("06-simple-16-clocks", 4),
        ("07-medium-64-clocks", 16),
        ("08-stress-512-clocks", 128),
        ("09-stress-1024-clocks", 256),
        ("10-stress-2048-clocks", 512),
        ("11-stress-4096-clocks", 1024),
    )
    for name, domain_count in scenarios:
        config = build(domain_count)
        (OUTPUT / f"{name}.json").write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        clocks = sum(item.get("kind") == "clock" for item in config.values())
        print(f"{name}: nodes={len(config)}, clocks={clocks}")
    dual_from = build_dual_from_reuse()
    name = "12-dual-from-reuse"
    (OUTPUT / f"{name}.json").write_text(
        json.dumps(dual_from, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"{name}: nodes={len(dual_from)}, clocks={16}")
    multi_from = build_multi_from_clusters()
    name = "16-multi-from-clusters"
    (OUTPUT / f"{name}.json").write_text(
        json.dumps(multi_from, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"{name}: nodes={len(multi_from)}, clocks={24}")
    structural = (
        ("17-terminal-fanout-order", build_terminal_fanout_crossing()),
        ("18-asymmetric-merge-columns", build_asymmetric_merge_columns()),
        ("19-dispersed-root-fanout", build_dispersed_root_fanout()),
        ("20-asymmetric-merge-route-bulge", build_asymmetric_merge_route_bulge()),
        ("23-middle-column-low-use-sources", build_middle_column_low_use_sources()),
        ("24-single-source-rendering-alias", build_single_source_rendering_alias()),
        ("25-mixed-root-port-order-torture", build_mixed_root_port_order_torture()),
        ("26-feedback-reproduction-combined", build_feedback_reproduction_combined()),
    )
    for name, config in structural:
        (OUTPUT / f"{name}.json").write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        clocks = sum(item.get("kind") == "clock" for item in config.values())
        print(f"{name}: nodes={len(config)}, clocks={clocks}")
    adversarial = (
        ("13-label-clearance-weave", 16, 2, True),
        ("14-crossing-weave-128-clocks", 64, 2, False),
        ("15-routing-torture-512-clocks", 128, 4, True),
    )
    for name, domains, clocks_per_domain, long_names in adversarial:
        config = build_adversarial_weave(
            domains,
            clocks_per_domain=clocks_per_domain,
            long_names=long_names,
        )
        (OUTPUT / f"{name}.json").write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        clocks = sum(item.get("kind") == "clock" for item in config.values())
        print(f"{name}: nodes={len(config)}, clocks={clocks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
