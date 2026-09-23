#!/usr/bin/env python3
"""Generate and verify dual-public-root mux-bus layouts through the public CLI."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import feedback_layout_reproduction_oracle as oracle
from svg_quality_system import evaluate_with_geometry


TARGET_ISSUE_ID = "FB-ROUTE-023"
TARGET_METRIC_ID = "premature_interior_trunk_entry"

FACTORS = {
    "root_kinds": (("from", "source"), ("source", "from"), ("from", "from")),
    "row_count": (4, 8, 12, 16),
    "row_topology": ("simple-mux2", "pll-reconvergent-mux3", "pll-target-ladder"),
    "public_root_entry": ("branch-only", "repeated-direct"),
    "direct_root_port_order": ("a-before-b", "b-before-a"),
    "direct_entry_pattern": ("all", "top-main-omit-b", "penultimate-main-omit-a", "penultimate-main-omit-b"),
    "ladder_consumers": ("one", "paired", "triple"),
    "peer_output_shape": (
        "direct-clock", "first-gate-clock", "second-gate-clock", "gate-clock",
    ),
    "peer_clock_fanout": (
        "single", "first-double", "second-double", "both-double",
    ),
    "ladder_shape": ("one-stage", "serial-remerge"),
    "pll_weave": ("aligned", "mirror", "rotate"),
    "annotation_pressure": ("none", "late-target", "row-band"),
    "second_path": ("gate", "gate-div"),
    "target_band": ("top", "middle", "penultimate", "lower", "external-lower"),
    "mux_offset": (0, 2, 4),
    "root_bus_position": ("left-axis", "second-branch-axis"),
    "late_target_depth": ("direct", "gate", "gate-div"),
    "second_root_extra_output": ("none", "one-direct", "multiple"),
    "obstacle_pattern": ("none", "interleaved-public", "reverse-interleaved-public", "rotate-interleaved-public", "reverse-interleaved-private", "reverse-private", "dense-downstream"),
    "declaration_order": ("forward", "reverse", "interleaved"),
    "port_permutation": ("a-0-b-1", "a-1-b-0"),
}
REQUIRED_SCENARIOS = {
    "two-public-asymmetric-gate-div": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "simple-mux2", "public_root_entry": "branch-only", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "aligned", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "middle", "mux_offset": 0, "root_bus_position": "left-axis", "late_target_depth": "direct", "second_root_extra_output": "none", "obstacle_pattern": "none", "declaration_order": "forward", "port_permutation": "a-0-b-1"},
    "second-public-source-extra-output": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "simple-mux2", "public_root_entry": "branch-only", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "aligned", "annotation_pressure": "row-band", "second_path": "gate-div", "target_band": "lower", "mux_offset": 2, "root_bus_position": "second-branch-axis", "late_target_depth": "gate", "second_root_extra_output": "multiple", "obstacle_pattern": "interleaved-public", "declaration_order": "reverse", "port_permutation": "a-1-b-0"},
    "both-public-from-lower-right-mux": {"root_kinds": ("from", "from"), "row_count": 16, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "branch-only", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "aligned", "annotation_pressure": "late-target", "second_path": "gate", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "one-direct", "obstacle_pattern": "reverse-private", "declaration_order": "interleaved", "port_permutation": "a-0-b-1"},
    "dual-public-external-lower-right-mux": {"root_kinds": ("source", "from"), "row_count": 16, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "branch-only", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "aligned", "annotation_pressure": "late-target", "second_path": "gate-div", "target_band": "external-lower", "mux_offset": 4, "root_bus_position": "second-branch-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "dense-downstream", "declaration_order": "reverse", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-reconvergent": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "none", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-paired": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "ladder_consumers": "paired", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "none", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-dense": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "dense-downstream", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-sixteen-rows": {"root_kinds": ("from", "source"), "row_count": 16, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "none", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-aligned": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "aligned", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "none", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-rotate": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "rotate", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "none", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-external-lower": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "external-lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "none", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-second-axis": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "second-branch-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "none", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "none", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-paired": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "ladder_consumers": "paired", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "none", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-dense": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "dense-downstream", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-forward": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "none", "declaration_order": "forward", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-reverse": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "none", "declaration_order": "reverse", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-interleaved-public": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-reverse-private": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-private", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-both-from": {"root_kinds": ("from", "from"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-source-from": {"root_kinds": ("source", "from"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-reverse-interleaved": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-staggered-reverse-interleaved": {"root_kinds": ("from", "source"), "row_count": 8, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-staggered-reverse-interleaved-sixteen": {"root_kinds": ("from", "source"), "row_count": 16, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-staggered-reverse-interleaved-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-staggered-reverse-private-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-private", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-staggered-penultimate-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "penultimate", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-staggered-penultimate-offset0-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "penultimate", "mux_offset": 0, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-staggered-penultimate-offset2-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "penultimate", "mux_offset": 2, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-staggered-rotate-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "rotate-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-penultimate-omit-a-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "penultimate-main-omit-a", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-penultimate-omit-b-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "penultimate-main-omit-b", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-1-b-0"},
    "dual-public-repeated-direct-port-swap-staggered-branch-port-swap-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-0-b-1"},
    "dual-public-repeated-direct-port-swap-staggered-branch-port-swap-rotate-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "rotate", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-0-b-1"},
    "dual-public-repeated-direct-port-swap-staggered-branch-port-swap-aligned-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "aligned", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-0-b-1"},
    "dual-public-repeated-direct-port-swap-staggered-branch-port-swap-one-direct-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "one-direct", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-0-b-1"},
    "dual-public-repeated-direct-port-swap-staggered-branch-port-swap-row-band-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "row-band", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-0-b-1"},
    "dual-public-repeated-direct-port-swap-staggered-branch-port-swap-forward-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "forward", "port_permutation": "a-0-b-1"},
    "dual-public-repeated-direct-port-swap-staggered-branch-port-swap-second-axis-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "second-branch-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-0-b-1"},
    "dual-public-repeated-direct-port-swap-staggered-branch-port-swap-second-gate-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "one", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-0-b-1"},
    "dual-public-repeated-direct-port-swap-staggered-branch-port-swap-paired-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "paired", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-0-b-1"},
    "dual-public-repeated-direct-port-swap-staggered-branch-port-swap-triple-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "triple", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-0-b-1"},
    "dual-public-repeated-direct-port-swap-staggered-branch-port-swap-triple-offset2-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "triple", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 2, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-0-b-1"},
    "dual-public-repeated-direct-port-swap-staggered-branch-port-swap-triple-gate-clock-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "triple", "peer_output_shape": "gate-clock", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-0-b-1"},
    "dual-public-repeated-direct-port-swap-staggered-branch-port-swap-triple-first-gate-clock-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "triple", "peer_output_shape": "first-gate-clock", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-0-b-1"},
    "dual-public-repeated-direct-port-swap-staggered-branch-port-swap-triple-second-gate-clock-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "triple", "peer_output_shape": "second-gate-clock", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-0-b-1"},
    "dual-public-repeated-direct-port-swap-staggered-branch-port-swap-triple-first-double-clock-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "triple", "peer_output_shape": "direct-clock", "peer_clock_fanout": "first-double", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-0-b-1"},
    "dual-public-repeated-direct-port-swap-staggered-branch-port-swap-triple-second-double-clock-twelve": {"root_kinds": ("from", "source"), "row_count": 12, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_root_port_order": "b-before-a", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "triple", "peer_output_shape": "direct-clock", "peer_clock_fanout": "second-double", "ladder_shape": "one-stage", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate-div", "target_band": "lower", "mux_offset": 4, "root_bus_position": "left-axis", "late_target_depth": "gate-div", "second_root_extra_output": "multiple", "obstacle_pattern": "reverse-interleaved-public", "declaration_order": "interleaved", "port_permutation": "a-0-b-1"},
    "dual-public-small-staggered-triple-four": {"root_kinds": ("source", "from"), "row_count": 4, "row_topology": "pll-reconvergent-mux3", "public_root_entry": "repeated-direct", "direct_entry_pattern": "top-main-omit-b", "ladder_consumers": "triple", "ladder_shape": "serial-remerge", "pll_weave": "mirror", "annotation_pressure": "none", "second_path": "gate", "target_band": "external-lower", "mux_offset": 0, "root_bus_position": "left-axis", "late_target_depth": "gate", "second_root_extra_output": "none", "obstacle_pattern": "interleaved-public", "declaration_order": "reverse", "port_permutation": "a-0-b-1"},
}
for _scenario in REQUIRED_SCENARIOS.values():
    _scenario.setdefault("direct_root_port_order", "a-before-b")
    _scenario.setdefault("direct_entry_pattern", "all")
    _scenario.setdefault("peer_output_shape", "direct-clock")
    _scenario.setdefault("peer_clock_fanout", "single")
REQUIRED_SCENARIOS_ALL = dict(REQUIRED_SCENARIOS)


def _unit(names: Iterable[str], values: Iterable[Any]) -> str:
    return json.dumps([[name, value] for name, value in zip(names, values)], separators=(",", ":"), sort_keys=True)


def coverage_units(factors: dict[str, Any]) -> set[str]:
    names = tuple(FACTORS)
    result = {_unit((name,), (factors[name],)) for name in names}
    result.update(_unit((left, right), (factors[left], factors[right])) for index, left in enumerate(names) for right in names[index + 1:])
    return result


def required_units() -> set[str]:
    names = tuple(FACTORS)
    result = set()
    for name in names:
        result.update(_unit((name,), (value,)) for value in FACTORS[name])
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            result.update(_unit((left, right), pair) for pair in itertools.product(FACTORS[left], FACTORS[right]))
    return result


def candidate_cases() -> list[dict[str, Any]]:
    """Bounded deterministic pool covering every required pairwise value."""
    names = tuple(FACTORS)
    base = {name: FACTORS[name][0] for name in names}
    candidates = [base, *REQUIRED_SCENARIOS.values()]
    for left_index, left in enumerate(names):
        for right in names[left_index + 1:]:
            for pair in itertools.product(FACTORS[left], FACTORS[right]):
                candidate = dict(base)
                candidate[left], candidate[right] = pair
                candidates.append(candidate)
    generator = random.Random(230918)
    candidates.extend(
        {name: generator.choice(FACTORS[name]) for name in names}
        for _ in range(2048)
    )
    unique: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        unique[json.dumps(candidate, sort_keys=True)] = dict(candidate)
    return list(unique.values())


def covering_suite() -> list[dict[str, Any]]:
    """Deterministic pairwise coverage plus named high-risk structures."""
    candidates = candidate_cases()
    selected = [dict(case) for case in REQUIRED_SCENARIOS.values()]
    covered = set().union(*(coverage_units(case) for case in selected))
    required = required_units()
    while covered != required:
        candidate = max(candidates, key=lambda case: (len(coverage_units(case) - covered), json.dumps(case, sort_keys=True)))
        gain = coverage_units(candidate) - covered
        if not gain:
            raise AssertionError("pairwise coverage candidate space exhausted")
        selected.append(candidate)
        covered.update(gain)
    return selected


def build_case(factors: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build a valid public graph with explicit late-target pressure."""
    first_kind, second_kind = factors["root_kinds"]
    row_count = int(factors["row_count"])
    config: dict[str, dict[str, Any]] = {
        "public_root_a": {"kind": first_kind},
        "public_root_b": {"kind": second_kind},
    }
    if factors["root_bus_position"] == "second-branch-axis":
        config["public_root_b"]["layout_column"] = 2
    target_index = {
        "top": 0,
        "middle": row_count // 2,
        "penultimate": max(0, row_count - 2),
        "lower": row_count - 1,
    }.get(factors["target_band"])
    a_port, b_port = ("0", "1") if factors["port_permutation"] == "a-0-b-1" else ("1", "0")
    rows: list[list[tuple[str, dict[str, Any]]]] = []
    repeated_direct = factors["public_root_entry"] == "repeated-direct"

    def reconvergent_item(primary: str, fallback: str, pll: str) -> dict[str, Any]:
        if repeated_direct:
            a_direct_port, b_direct_port = (
                ("1", "2")
                if factors["direct_root_port_order"] == "a-before-b"
                else ("2", "1")
            )
            return {
                "kind": "mux4",
                "source": {
                    "0": primary,
                    a_direct_port: "public_root_a",
                    b_direct_port: "public_root_b",
                    "3": pll,
                },
            }
        return {"kind": "mux3", "source": {"0": primary, "1": fallback, "2": pll}}

    def branch(prefix: str, root: str, index: int, depth: str) -> tuple[list[tuple[str, dict[str, Any]]], str]:
        suffix = "{:02d}".format(index)
        if depth == "direct":
            return [], root
        gate = prefix + "_gate_" + suffix
        entries: list[tuple[str, dict[str, Any]]] = [(gate, {"kind": "gate", "source": root})]
        if depth != "gate-div":
            return entries, gate
        div = prefix + "_div_" + suffix
        entries.append((div, {"kind": "div", "source": gate}))
        return entries, div

    def append_peer_output(
        entries: list[tuple[str, dict[str, Any]]], clock: str, peer: str,
        peer_index: int,
    ) -> None:
        source = peer
        shape = factors["peer_output_shape"]
        if (
            shape == "gate-clock"
            or shape == "first-gate-clock" and peer_index == 1
            or shape == "second-gate-clock" and peer_index == 2
        ):
            gate = clock + "_gate"
            entries.append((gate, {"kind": "gate", "source": peer}))
            source = gate
        entries.append((clock, {"kind": "clock", "source": source}))
        fanout = factors["peer_clock_fanout"]
        if (
            fanout == "both-double"
            or fanout == "first-double" and peer_index == 1
            or fanout == "second-double" and peer_index == 2
        ):
            entries.append((clock + "_extra", {"kind": "clock", "source": source}))

    for index in range(row_count):
        late = index == target_index
        a_entries, a_end = branch("a", "public_root_a", index, factors["late_target_depth"] if late else "gate")
        b_depth = factors["late_target_depth"] if late else factors["second_path"]
        b_entries, b_end = branch("b", "public_root_b", index, b_depth)
        mux = "mux_{:02d}".format(index)
        item: dict[str, Any] = {"kind": "mux2", "source": {a_port: a_end, b_port: b_end}}
        complex_row = factors["row_topology"] in ("pll-reconvergent-mux3", "pll-target-ladder") and (factors["row_topology"] == "pll-reconvergent-mux3" or late)
        if repeated_direct and not complex_row:
            item["kind"] = "mux4"
            if factors["direct_root_port_order"] == "a-before-b":
                item["source"].update({"2": "public_root_a", "3": "public_root_b"})
            else:
                item["source"].update({"2": "public_root_b", "3": "public_root_a"})
            if factors["direct_entry_pattern"] == "top-main-omit-b" and index == 0:
                item = {
                    "kind": "mux3",
                    "source": {a_port: a_end, b_port: b_end, "2": "public_root_a"},
                }
            elif factors["direct_entry_pattern"] == "penultimate-main-omit-a" and index == row_count - 2:
                item = {
                    "kind": "mux3",
                    "source": {a_port: a_end, b_port: b_end, "2": "public_root_b"},
                }
            elif factors["direct_entry_pattern"] == "penultimate-main-omit-b" and index == row_count - 2:
                item = {
                    "kind": "mux3",
                    "source": {a_port: a_end, b_port: b_end, "2": "public_root_a"},
                }
        if late and int(factors["mux_offset"]):
            item["layout_column"] = 5 + int(factors["mux_offset"])
        row = [*a_entries, *b_entries, (mux, item)]
        if complex_row:
            suffix = "{:02d}".format(index)
            a_pll, b_pll = "a_pll_" + suffix, "b_pll_" + suffix
            primary_gate = "primary_gate_" + suffix
            primary_div = "primary_div_" + suffix
            reconvergent = "reconvergent_mux_" + suffix
            item["kind"] = "mux3"
            item["source"]["2"] = a_pll + "[0]"
            reconvergent_config = reconvergent_item(
                primary_div, "public_root_b" if late else b_end, b_pll + "[1]",
            )
            if repeated_direct and factors["direct_entry_pattern"] == "top-main-omit-b" and index == 0:
                reconvergent_config = {
                    "kind": "mux3",
                    "source": {"0": primary_div, "1": "public_root_a", "2": b_pll + "[1]"},
                }
            elif repeated_direct and factors["direct_entry_pattern"] == "penultimate-main-omit-a" and index == row_count - 2:
                reconvergent_config = {
                    "kind": "mux3",
                    "source": {"0": primary_div, "1": "public_root_b", "2": b_pll + "[1]"},
                }
            elif repeated_direct and factors["direct_entry_pattern"] == "penultimate-main-omit-b" and index == row_count - 2:
                reconvergent_config = {
                    "kind": "mux3",
                    "source": {"0": primary_div, "1": "public_root_a", "2": b_pll + "[1]"},
                }
            if late and int(factors["mux_offset"]):
                reconvergent_config["layout_column"] = 6 + int(factors["mux_offset"])
            ladder_entries = [
                (a_pll, {"kind": "pll2", "pll_kind": "INNO", "source": "public_root_a"}),
                (b_pll, {"kind": "pll2", "pll_kind": "INNO", "source": "public_root_b"}),
                (primary_gate, {"kind": "gate", "source": mux}),
                (primary_div, {"kind": "div", "source": primary_gate}),
                (reconvergent, reconvergent_config),
            ]
            peer_count = {"one": 1, "paired": 2, "triple": 3}[factors["ladder_consumers"]]
            for peer in range(1, peer_count):
                peer_name = reconvergent + "_peer_{}".format(peer)
                peer_item = reconvergent_item(primary_div, b_end, b_pll + "[1]")
                peer_item["layout_column"] = 6 + int(factors["mux_offset"]) + peer
                ladder_entries.append((peer_name, peer_item))
                append_peer_output(
                    ladder_entries,
                    "clock_{}_peer_{}".format(suffix, peer),
                    peer_name,
                    peer,
                )
            if factors["row_topology"] == "pll-target-ladder" and factors["ladder_shape"] == "serial-remerge":
                serial_gate = "serial_gate_" + suffix
                serial_div = "serial_div_" + suffix
                serial_mux = "serial_reconvergent_mux_" + suffix
                serial_config = reconvergent_item(serial_div, b_end, b_pll + "[1]")
                if late and int(factors["mux_offset"]):
                    serial_config["layout_column"] = 7 + int(factors["mux_offset"])
                ladder_entries.extend([
                    (serial_gate, {"kind": "gate", "source": reconvergent}),
                    (serial_div, {"kind": "div", "source": serial_gate}),
                    (serial_mux, serial_config),
                ])
                reconvergent = serial_mux
            row.extend(ladder_entries)
            mux = reconvergent
        row.append(("clock_{:02d}".format(index), {"kind": "clock", "source": mux}))
        rows.append(row)

    if factors["target_band"] == "external-lower":
        a_entries, a_end = branch("external_a", "public_root_a", row_count, factors["late_target_depth"])
        b_entries, b_end = branch("external_b", "public_root_b", row_count, factors["late_target_depth"])
        item = {"kind": "mux2", "source": {a_port: a_end, b_port: b_end}}
        if repeated_direct and factors["row_topology"] != "pll-target-ladder":
            item["kind"] = "mux4"
            if factors["direct_root_port_order"] == "a-before-b":
                item["source"].update({"2": "public_root_a", "3": "public_root_b"})
            else:
                item["source"].update({"2": "public_root_b", "3": "public_root_a"})
        if int(factors["mux_offset"]):
            item["layout_column"] = 5 + int(factors["mux_offset"])
        external_row: list[tuple[str, dict[str, Any]]] = [*a_entries, *b_entries, ("external_mux", item)]
        terminal = "external_mux"
        if factors["row_topology"] == "pll-target-ladder":
            a_pll, b_pll = "external_a_pll", "external_b_pll"
            primary_gate, primary_div = "external_primary_gate", "external_primary_div"
            reconvergent = "external_reconvergent_mux"
            reconvergent_config = reconvergent_item(
                primary_div, "public_root_b", b_pll + "[1]",
            )
            if int(factors["mux_offset"]):
                reconvergent_config["layout_column"] = 6 + int(factors["mux_offset"])
            external_row.extend([
                (a_pll, {"kind": "pll2", "pll_kind": "INNO", "source": "public_root_a"}),
                (b_pll, {"kind": "pll2", "pll_kind": "INNO", "source": "public_root_b"}),
                (primary_gate, {"kind": "gate", "source": "external_mux"}),
                (primary_div, {"kind": "div", "source": primary_gate}),
                (reconvergent, reconvergent_config),
            ])
            peer_count = {"one": 1, "paired": 2, "triple": 3}[factors["ladder_consumers"]]
            for peer in range(1, peer_count):
                peer_name = reconvergent + "_peer_{}".format(peer)
                peer_item = reconvergent_item(primary_div, b_end, b_pll + "[1]")
                peer_item["layout_column"] = 6 + int(factors["mux_offset"]) + peer
                external_row.append((peer_name, peer_item))
                append_peer_output(
                    external_row,
                    "external_clock_peer_{}".format(peer),
                    peer_name,
                    peer,
                )
            terminal = reconvergent
        external_row.append(("external_clock", {"kind": "clock", "source": terminal}))
        rows.append(external_row)

    if factors["declaration_order"] == "reverse":
        rows.reverse()
    elif factors["declaration_order"] == "interleaved":
        rows = rows[::2] + rows[1::2]
    for row in rows:
        config.update(row)

    extra = factors["second_root_extra_output"]
    if extra != "none":
        config["public_root_b_probe"] = {"kind": "clock", "source": "public_root_b"}
    if extra == "multiple":
        config["public_root_b_probe_gate"] = {"kind": "gate", "source": "public_root_b"}
        config["public_root_b_probe_clock"] = {"kind": "clock", "source": "public_root_b_probe_gate"}

    pattern = factors["obstacle_pattern"]
    if pattern in ("interleaved-public", "reverse-interleaved-public", "rotate-interleaved-public", "reverse-interleaved-private"):
        if pattern != "reverse-interleaved-private":
            config["obstacle_root"] = {"kind": "from"}
        for index in range(row_count):
            root = "obstacle_root"
            if pattern == "reverse-interleaved-private":
                root = "obstacle_root_{:02d}".format(index)
                config[root] = {"kind": "from"}
            gate = "obstacle_gate_{:02d}".format(index)
            config[gate] = {"kind": "gate", "source": root}
            if pattern == "interleaved-public":
                target_index = index
            elif pattern == "rotate-interleaved-public":
                target_index = (index + row_count // 2) % row_count
            else:
                target_index = row_count - 1 - index
            mux = config["mux_{:02d}".format(target_index)]
            if mux["kind"] == "mux4":
                config["obstacle_clock_{:02d}".format(index)] = {"kind": "clock", "source": gate}
            elif mux["kind"] == "mux3":
                mux["kind"] = "mux4"
                mux["source"]["3"] = gate
            else:
                mux["kind"] = "mux3"
                mux["source"]["2"] = gate
    elif pattern == "reverse-private":
        for index in range(row_count):
            root = "private_from_{:02d}".format(index)
            gate = "private_gate_{:02d}".format(index)
            config[root] = {"kind": "from"}
            config[gate] = {"kind": "gate", "source": root}
            mux = config["mux_{:02d}".format(row_count - 1 - index)]
            if mux["kind"] == "mux4":
                config["private_clock_{:02d}".format(index)] = {"kind": "clock", "source": gate}
            else:
                mux["kind"] = "mux3"
                mux["source"]["2"] = gate
    elif pattern == "dense-downstream":
        for index in range(row_count):
            mux = "mux_{:02d}".format(index)
            gate = "dense_gate_{:02d}".format(index)
            config[gate] = {"kind": "gate", "source": mux}
            config["dense_clock_{:02d}".format(index)] = {"kind": "clock", "source": gate}
    if factors["row_topology"] == "pll-reconvergent-mux3":
        for index in range(row_count):
            peer = (
                row_count - 1 - index
                if factors["pll_weave"] == "mirror"
                else (index + 1) % row_count
                if factors["pll_weave"] == "rotate"
                else index
            )
            suffix, peer_suffix = "{:02d}".format(index), "{:02d}".format(peer)
            config["mux_" + suffix]["source"]["2"] = "a_pll_" + peer_suffix + "[0]"
            reconvergent_config = config["reconvergent_mux_" + suffix]
            pll_port = "3" if reconvergent_config["kind"] == "mux4" else "2"
            reconvergent_config["source"][pll_port] = "b_pll_" + suffix + "[1]"
    pressure = factors["annotation_pressure"]
    annotation = "late target corridor occupancy must preserve the public backbone"
    if pressure == "late-target":
        target = "external_mux" if factors["target_band"] == "external-lower" else "mux_{:02d}".format(target_index)
        config[target]["description"] = annotation
    elif pressure == "row-band":
        for index in range(row_count):
            config["mux_{:02d}".format(index)]["description"] = annotation + " row {:02d}".format(index)
    return config


def repeated_direct_muxes(config: dict[str, dict[str, Any]]) -> list[str]:
    roots = {"public_root_a", "public_root_b"}
    return [
        name for name, item in config.items()
        if item.get("kind", "").startswith("mux")
        and roots.issubset(set(item.get("source", {}).values()))
    ]


def semantic_preconditions_met(
    factors: dict[str, Any], config: dict[str, dict[str, Any]],
) -> bool:
    if factors["public_root_entry"] != "repeated-direct":
        return True
    return len(repeated_direct_muxes(config)) >= 2


def is_target_reproduction(
    witnesses: list[dict[str, Any]],
    semantic_preconditions: bool,
    failed_metric_ids: list[str],
) -> bool:
    return bool(witnesses) and semantic_preconditions and failed_metric_ids == [TARGET_METRIC_ID]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(
    root: Path,
    input_path: Path,
    svg: Path,
    *,
    max_seconds=None,
) -> dict[str, Any]:
    started = time.perf_counter()
    command = [
        sys.executable,
        str(root / "src"),
        "-i", str(input_path),
        "-l", str(root / "drawio-lib"),
        "-o", str(svg),
        "--crossing-style", "arc",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            timeout=max_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "duration_seconds": round(time.perf_counter() - started, 6),
            "max_seconds": max_seconds,
            "returncode": None,
            "output_exists": svg.is_file(),
            "stderr_tail": (exc.stderr or "")[-1000:],
        }
    duration = time.perf_counter() - started
    status = "passed"
    if completed.returncode or not svg.is_file():
        status = "cli-failed"
    elif max_seconds is not None and duration > max_seconds:
        status = "budget-exceeded"
    return {
        "status": status,
        "duration_seconds": round(duration, 6),
        "max_seconds": max_seconds,
        "returncode": completed.returncode,
        "output_exists": svg.is_file(),
        "stderr_tail": completed.stderr[-1000:] if status != "passed" else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--producer-root", type=Path, default=ROOT)
    parser.add_argument("--expect", choices=("clean", "reproduced"), default="clean")
    parser.add_argument(
        "--max-render-seconds",
        type=float,
        help="Fail each public-CLI render that exceeds this wall-clock budget.",
    )
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument(
        "--scenario",
        choices=tuple(REQUIRED_SCENARIOS_ALL),
        help="Run one named high-risk scenario with the same double-render and full-metric contract.",
    )
    selector.add_argument(
        "--case-index",
        type=int,
        help="Run one zero-based case from the deterministic pairwise suite under the same verification contract.",
    )
    parser.add_argument(
        "--topology-domain",
        choices=("all", "non-tail-bend"),
        default="all",
        help="Run the full historical domain or the simple/target-ladder domain after isolating the known complex-row tail-bend diagnostic.",
    )
    args = parser.parse_args()
    if args.max_render_seconds is not None and args.max_render_seconds <= 0:
        parser.error("--max-render-seconds must be greater than zero")
    if args.topology_domain == "non-tail-bend":
        FACTORS["row_topology"] = ("simple-mux2", "pll-target-ladder")
        FACTORS["annotation_pressure"] = ("none",)
        REQUIRED_SCENARIOS.clear()
        REQUIRED_SCENARIOS.update({
            name: factors
            for name, factors in REQUIRED_SCENARIOS_ALL.items()
            if all(factors[name] in FACTORS[name] for name in FACTORS)
        })
    root, output = args.producer_root.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results, reproduced = [], []
    if args.scenario:
        selected = REQUIRED_SCENARIOS_ALL[args.scenario]
        if any(selected[name] not in FACTORS[name] for name in FACTORS):
            parser.error("selected scenario is outside --topology-domain")
        suite = [dict(selected)]
        scoped_required_units = coverage_units(selected)
        coverage_scope = "named-scenario:" + args.scenario
    elif args.case_index is not None:
        complete_suite = covering_suite()
        if args.case_index < 0 or args.case_index >= len(complete_suite):
            parser.error("--case-index must be between 0 and {}".format(len(complete_suite) - 1))
        selected = complete_suite[args.case_index]
        suite = [dict(selected)]
        scoped_required_units = coverage_units(selected)
        coverage_scope = "pairwise-case-index:{}".format(args.case_index)
    else:
        suite = covering_suite()
        scoped_required_units = required_units()
        coverage_scope = "pairwise-domain"
    for index, factors in enumerate(suite):
        case_dir = output / "case-{:03d}".format(index)
        case_dir.mkdir(parents=True, exist_ok=True)
        input_path, first, second = case_dir / "input.json", case_dir / "first.svg", case_dir / "second.svg"
        config = build_case(factors)
        input_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        render_runs = [
            _run(
                root,
                input_path,
                first,
                max_seconds=args.max_render_seconds,
            )
        ]
        if render_runs[0]["status"] == "passed":
            render_runs.append(
                _run(
                    root,
                    input_path,
                    second,
                    max_seconds=args.max_render_seconds,
                )
            )
        (case_dir / "render-receipt.json").write_text(
            json.dumps({"runs": render_runs}, indent=2) + "\n",
            encoding="utf-8",
        )
        if len(render_runs) != 2 or any(
            run["status"] != "passed" for run in render_runs
        ):
            raise RuntimeError(
                "public CLI render gate failed: {}".format(render_runs)
            )
        if _sha256(first) != _sha256(second):
            raise RuntimeError("nondeterministic public SVG: case-{:03d}".format(index))
        quality, report = evaluate_with_geometry(input_path, first, ROOT / "tests" / "quality-metrics.json")
        witnesses = report["witnesses"]["premature_interior_trunk_entry_witnesses"]
        preconditions = semantic_preconditions_met(factors, config)
        target_reproduced = is_target_reproduction(witnesses, preconditions, quality["failed_metric_ids"])
        row = {"case_id": "case-{:03d}".format(index), "factors": factors, "input_sha256": _sha256(input_path), "svg_sha256": _sha256(first), "render_runs": render_runs, "failed_metric_ids": quality["failed_metric_ids"], "detected_issues": report["detected_issues"], "target_witnesses": witnesses, "semantic_preconditions_met": preconditions, "target_reproduced": target_reproduced}
        results.append(row)
        (case_dir / "result.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
        if target_reproduced:
            reproduced.append(row)
    covered = set().union(*(coverage_units(case) for case in suite))
    receipt = {"schema_version": 2, "expect": args.expect, "coverage_scope": coverage_scope, "suite_size": len(suite), "max_render_seconds": args.max_render_seconds, "required_coverage_units": sorted(scoped_required_units), "covered_coverage_units": sorted(covered), "missing_coverage_units": sorted(scoped_required_units - covered), "quality_failure_cases": [row["case_id"] for row in results if row["failed_metric_ids"]], "unexpected_quality_failure_cases": [row["case_id"] for row in results if any(metric != TARGET_METRIC_ID for metric in row["failed_metric_ids"])], "reproduced_cases": reproduced, "results": results}
    (output / "coverage-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if args.expect == "clean":
        valid = not receipt["missing_coverage_units"] and not receipt["quality_failure_cases"] and not reproduced
    else:
        valid = not receipt["missing_coverage_units"] and bool(reproduced)
    if not valid:
        print("dual-public coverage gate failed", file=sys.stderr)
        return 1
    print("dual-public coverage complete cases={}".format(len(results)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
