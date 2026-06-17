#!/usr/bin/env python3
"""Generate study/frozen_summaries.json from evidence bundles."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from hc_analytics.config import Settings
from hc_analytics.explainability.pipeline import load_cached_bundle
from hc_analytics.language.provider import generate_grounded_summary

CASE_IDS = {
    "B-07": "-10000010260449",
    "B-09": "-10000010271299",
    "B-12": "-10000010273042",
    "B-15": "-10000010266211",
    "B-01": "-10000010263023",
    "B-02": "-10000010266687",
    "B-03": "-10000010279991",
    "B-04": "-10000010259786",
    "B-01b": "-10000010275202",
    "B-02b": "-10000010262670",
    "B-03b": "-10000010256636",
    "B-04b": "-10000010265432",
}
YEAR = 2022


def main() -> None:
    settings = Settings(repo_root=REPO_ROOT)
    summaries: dict[str, dict] = {}
    for case_id, bene_id in CASE_IDS.items():
        bundle = load_cached_bundle(bene_id, YEAR, settings=settings)
        if bundle is None:
            print(f"Skipping {case_id}: no bundle")
            continue
        summary = generate_grounded_summary(bundle, settings=settings)
        key = f"{bene_id}:{YEAR}"
        summaries[key] = summary.model_dump(mode="json")
        print(f"Frozen {case_id} -> {key}")

    output = REPO_ROOT / "study" / "frozen_summaries.json"
    payload = {
        "schema_version": "1.0",
        "model_version": "frozen-template-v1",
        "prompt_version": "template-v1",
        "summaries": summaries,
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
