#!/usr/bin/env python3
"""Validate blocked assignment against the existing case/error catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from hc_analytics.config import Settings  # noqa: E402
from hc_analytics.study.session import validate_assignment_design  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-study", type=int, default=60)
    args = parser.parse_args()
    report = validate_assignment_design(
        per_study=args.per_study,
        settings=Settings(repo_root=REPO_ROOT, study_mode=True),
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
