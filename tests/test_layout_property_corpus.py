from __future__ import annotations

import random
from pathlib import Path

import pytest

from elk_layout import generate_elk_layout
from layout_quality import inspect_layout_quality


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "drawio-lib" / "drawclock.xml"


def _varied_clock_dag(seed: int) -> dict[str, dict[str, object]]:
    rng = random.Random(seed)
    root_count = rng.randint(2, 5)
    roots = [
        (
            f"root_{index}_{'long_instance_name_' * rng.randint(0, 2)}{seed}"
        )
        for index in range(root_count)
    ]
    config: dict[str, dict[str, object]] = {
        name: {
            "kind": "from" if rng.random() < 0.35 else "source",
            **(
                {}
                if rng.random() < 0.35
                else {"source_kind": "source"}
            ),
        }
        for name in roots
    }
    # Normalize source metadata after the independent random kind choice.
    for name in roots:
        if config[name]["kind"] == "from":
            config[name].pop("source_kind", None)

    plls = []
    for index in range(rng.randint(2, 4)):
        name = f"pll2_{seed}_{index}"
        plls.append(name)
        config[name] = {
            "kind": "pll2",
            "pll_kind": "INNO",
            "source": rng.choice(roots),
        }

    for domain in range(rng.randint(4, 12)):
        prefix = f"s{seed:02d}_d{domain:02d}"
        mux_kind = rng.choice(("mux2", "mux3"))
        port_count = 2 if mux_kind == "mux2" else 3
        connected_ports = sorted(
            rng.sample(range(port_count), rng.randint(1, port_count))
        )
        sources = [
            rng.choice(roots + [f"{pll}[{rng.randrange(2)}]" for pll in plls])
            for _ in connected_ports
        ]
        first = f"mux_a_{prefix}"
        config[first] = {
            "kind": mux_kind,
            "source": {
                str(port): source
                for port, source in zip(connected_ports, sources)
            },
        }
        previous = first
        for stage in range(rng.randint(1, 4)):
            name = f"stage_{stage}_{prefix}"
            kind = rng.choice(("gate", "div", "div_r", "dto", "inv"))
            config[name] = {"kind": kind, "source": previous}
            if kind == "div_r":
                config[name]["ratio"] = str(2 ** rng.randint(1, 5))
            if kind == "inv":
                config[name]["inv_kind"] = "inv"
            previous = name
        if rng.random() < 0.75:
            second = f"mux_b_{prefix}"
            config[second] = {
                "kind": "mux2",
                "source": {
                    "0": previous,
                    "1": rng.choice(
                        roots
                        + [f"{pll}[{rng.randrange(2)}]" for pll in plls]
                    ),
                },
            }
            previous = second
        cell = f"cell_{prefix}"
        config[cell] = {"kind": "cell", "source": previous}
        for leaf in range(rng.randint(1, 4)):
            config[f"clock_{prefix}_{leaf}"] = {
                "kind": "clock",
                "source": cell,
            }
    return config


@pytest.mark.parametrize("seed", range(12))
def test_varied_topology_property_corpus(seed: int) -> None:
    config = _varied_clock_dag(seed)
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    quality = inspect_layout_quality(
        config,
        document,
        library_path=LIBRARY,
        grid=0.0001,
        tolerance=0.01,
    )
    line = quality["line_integrity"]

    assert quality["passed"] is True
    assert line["edge_node_intersections"] == []
    assert line["edge_label_intersections"] == []
    assert line["source_lead_clearance_short"] == []
    assert line["target_lead_clearance_short"] == []
    assert line["avoidable_bend_edges"] == []
    assert line["avoidable_exclusive_chain_bend_edges"] == []
    assert line["avoidable_crossing_edges"] == []
