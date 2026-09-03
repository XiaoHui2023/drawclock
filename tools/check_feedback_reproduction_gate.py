#!/usr/bin/env python3
"""Project adapter for the user-root natural-reproduction phase gate."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".cursor/skills/project-goals/issues/user-feedback-natural-reproduction.json"
VALIDATOR = Path.home() / ".cursor/skills/agent-quality-workflow/scripts/validate_feedback_reproduction.py"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("structure", "reproduce", "solve", "complete"), required=True)
    args = parser.parse_args()
    if not VALIDATOR.is_file():
        print(f"natural-reproduction validator missing: {VALIDATOR}", file=sys.stderr)
        return 2
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(MANIFEST), "--project-root", str(ROOT), "--phase", args.phase],
        cwd=ROOT,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
