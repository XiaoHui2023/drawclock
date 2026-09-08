from tools.reproduction_semantics import observe


def test_split_rejoin_contract_rejects_nearby_wrong_root_kind() -> None:
    config = {
        "public_from": {"kind": "gate"},
        "left": {"kind": "gate", "source": "public_from"},
        "right": {"kind": "gate", "source": "public_from"},
    }
    contract = {
        "variant_id": "public-from-split-rejoin",
        "nodes": [
            {"name": "public_from", "kind": "from", "root": True, "min_outdegree": 2}
        ],
        "symptom": {"type": "split_rejoin", "root": "public_from", "port": "right"},
    }
    report = {"witnesses": {"split_rejoin_roots": ["public_from:right"]}}
    result = observe(config, report, contract)
    assert result["symptom_observed"] is True
    assert result["preconditions_met"] is False
    assert "kind" in result["errors"][0]


def test_direct_mux_contract_requires_exact_sources_and_kinds() -> None:
    contract = {
        "variant_id": "direct-from-mux-column",
        "direct_mux_fanin": {
            "target": "mux",
            "sources": ["a", "b", "c"],
            "source_kinds": ["from"],
        },
        "symptom": {
            "type": "direct_root_fanin_columns",
            "target": "mux",
            "sources": ["a", "b", "c"],
            "min_distinct_columns": 2,
        },
    }
    config = {
        "a": {"kind": "from"},
        "b": {"kind": "source"},
        "c": {"kind": "from"},
        "extra": {"kind": "from"},
        "mux": {"kind": "mux4", "source": {"0": "a", "1": "b", "2": "extra"}},
    }
    report = {
        "witnesses": {
            "direct_root_fanin_column_witnesses": [{
                "target": "mux",
                "sources": ["a", "b", "c"],
                "distinct_columns": [10.0, 20.0],
            }]
        }
    }
    result = observe(config, report, contract)
    assert result["symptom_observed"] is True
    assert result["preconditions_met"] is False
    assert any("direct sources differ" in error for error in result["errors"])
    assert any("kind" in error for error in result["errors"])


def test_direct_mux_contract_accepts_exact_column_witness() -> None:
    sources = ["a", "b", "c", "d"]
    config = {name: {"kind": "from"} for name in sources}
    config["mux"] = {
        "kind": "mux4",
        "source": {str(index): name for index, name in enumerate(sources)},
    }
    contract = {
        "variant_id": "direct-from-mux-column",
        "direct_mux_fanin": {
            "target": "mux",
            "sources": sources,
            "source_kinds": ["from"],
        },
        "symptom": {
            "type": "direct_root_fanin_columns",
            "target": "mux",
            "sources": sources,
            "min_distinct_columns": 2,
        },
    }
    report = {
        "witnesses": {
            "direct_root_fanin_column_witnesses": [{
                "target": "mux",
                "sources": list(reversed(sources)),
                "distinct_columns": [10.0, 20.0, 30.0],
            }]
        }
    }
    result = observe(config, report, contract)
    assert result == {
        "variant_id": "direct-from-mux-column",
        "preconditions_met": True,
        "symptom_observed": True,
        "errors": [],
    }
