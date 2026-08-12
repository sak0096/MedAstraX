#!/usr/bin/env python3
"""Apply human adjudication decisions to frozen summaries."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply adjudication_queue decisions to frozen summaries.")
    parser.add_argument(
        "--queue",
        type=Path,
        default=REPO_ROOT / "study" / "adjudication_queue.json",
    )
    parser.add_argument(
        "--summaries",
        type=Path,
        default=REPO_ROOT / "study" / "frozen_summaries.json",
    )
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Fail if any non-template item is still pending.",
    )
    args = parser.parse_args()

    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    summaries = json.loads(args.summaries.read_text(encoding="utf-8"))
    pending = []
    accepted = 0
    rejected_to_template = 0

    for item in queue.get("items", []):
        key = f"{item['bene_id']}:{item['analytic_year']}"
        status = item.get("status")
        decision = item.get("decision")
        if status == "auto_accepted_template":
            accepted += 1
            continue
        if status == "pending" or not decision:
            pending.append(key)
            continue
        if decision == "accept_candidate":
            if key in summaries.get("summaries", {}):
                summaries["summaries"][key]["narrative"] = item["candidate_narrative"]
                summaries["summaries"][key]["provider"] = item.get("provider") or summaries["summaries"][key].get(
                    "provider"
                )
            item["status"] = "accepted"
            item["reviewed_at"] = item.get("reviewed_at") or datetime.now(timezone.utc).isoformat()
            accepted += 1
        elif decision == "use_template":
            if key in summaries.get("summaries", {}):
                summaries["summaries"][key]["narrative"] = item["template_narrative"]
                summaries["summaries"][key]["provider"] = "template"
            item["status"] = "template_selected"
            item["reviewed_at"] = item.get("reviewed_at") or datetime.now(timezone.utc).isoformat()
            rejected_to_template += 1
        else:
            pending.append(key)

    if args.require_complete and pending:
        raise SystemExit(f"Adjudication incomplete for: {', '.join(pending)}")

    summaries["adjudication_applied_at"] = datetime.now(timezone.utc).isoformat()
    summaries["adjudication_required"] = bool(pending)
    args.summaries.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    args.queue.write_text(json.dumps(queue, indent=2), encoding="utf-8")
    print(
        f"Applied adjudication: accepted={accepted}, template_selected={rejected_to_template}, pending={len(pending)}"
    )


if __name__ == "__main__":
    main()
