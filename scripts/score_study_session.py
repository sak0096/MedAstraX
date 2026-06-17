#!/usr/bin/env python3
"""Score behavioral reliance metrics from an exported study session."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from hc_analytics.config import Settings
from hc_analytics.instrumentation.store import load_session_events
from hc_analytics.study.scoring import score_session_events


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_id", help="Study session id to score")
    parser.add_argument(
        "--export-json",
        type=Path,
        help="Optional path to a session export JSON file (array of events)",
    )
    args = parser.parse_args()

    if args.export_json:
        events = json.loads(args.export_json.read_text(encoding="utf-8"))
    else:
        settings = Settings(repo_root=REPO_ROOT)
        events = load_session_events(args.session_id, settings=settings)

    report = score_session_events(events)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
