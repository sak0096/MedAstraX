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
from hc_analytics.language.provider import freeze_metadata, generate_grounded_summary, prompt_fingerprint
from hc_analytics.study.loader import get_study_catalog

YEAR = 2022


def case_ids_from_catalog(settings: Settings) -> dict[str, str]:
    catalog = get_study_catalog(settings=settings)
    if catalog is None:
        raise SystemExit("Study catalog not loaded; cannot freeze summaries.")
    return {case.case_id: case.bene_id for case in catalog.cases}


def main() -> None:
    settings = Settings(repo_root=REPO_ROOT)
    case_ids = case_ids_from_catalog(settings)
    summaries: dict[str, dict] = {}
    prompt_hashes: dict[str, str] = {}
    for case_id, bene_id in case_ids.items():
        bundle = load_cached_bundle(bene_id, YEAR, settings=settings)
        if bundle is None:
            print(f"Skipping {case_id}: no bundle")
            continue
        summary = generate_grounded_summary(bundle, settings=settings)
        key = f"{bene_id}:{YEAR}"
        summaries[key] = summary.model_dump(mode="json")
        prompt_hashes[key] = prompt_fingerprint(bundle)
        print(f"Frozen {case_id} -> {key}")

    output = REPO_ROOT / "study" / "frozen_summaries.json"
    payload = {
        **freeze_metadata(settings),
        "prompt_hashes": prompt_hashes,
        "summaries": summaries,
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {output} ({len(summaries)} summaries)")


if __name__ == "__main__":
    main()
