from __future__ import annotations

import json
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
