#!/usr/bin/env python3
"""Generate study/frozen_summaries.json and an adjudication queue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from hc_analytics.config import Settings
from hc_analytics.explainability.pipeline import load_cached_bundle
from hc_analytics.language.provider import (
    adjudication_record,
    freeze_metadata,
    generate_grounded_summary,
    prompt_fingerprint,
    provider_configured,
)
from hc_analytics.language.summaries import build_template_narrative
from hc_analytics.study.loader import get_study_catalog

YEAR = 2022


def case_ids_from_catalog(settings: Settings) -> dict[str, str]:
    catalog = get_study_catalog(settings=settings)
    if catalog is None:
        # Freeze tooling may run with study_mode false; load directly.
        from hc_analytics.study.loader import load_study_catalog

        catalog = load_study_catalog(settings=settings)
    return {case.case_id: case.bene_id for case in catalog.cases}


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze grounded summaries for study stimuli.")
    parser.add_argument(
        "--require-llm",
        action="store_true",
        help="Fail if HC_LLM_PROVIDER/API_KEY/MODEL are not configured.",
    )
    parser.add_argument(
        "--allow-template",
        action="store_true",
        help="Force template generation even if LLM credentials exist.",
    )
    args = parser.parse_args()

    settings = Settings(repo_root=REPO_ROOT, study_mode=True)
    if args.require_llm and not provider_configured(settings):
        raise SystemExit(
            "HC_LLM_PROVIDER, HC_LLM_API_KEY, and HC_LLM_MODEL must be set when using --require-llm."
        )

    case_ids = case_ids_from_catalog(settings)
    summaries: dict[str, dict] = {}
    prompt_hashes: dict[str, str] = {}
    adjudication: list[dict] = []

    for case_id, bene_id in case_ids.items():
        bundle = load_cached_bundle(bene_id, YEAR, settings=settings)
        if bundle is None:
            print(f"Skipping {case_id}: no bundle")
            continue
        summary = generate_grounded_summary(
            bundle,
            settings=settings,
            allow_llm=not args.allow_template,
        )
        key = f"{bene_id}:{YEAR}"
        summaries[key] = summary.model_dump(mode="json")
        prompt_hash = prompt_fingerprint(bundle, settings=settings)
        prompt_hashes[key] = prompt_hash
        adjudication.append(
            adjudication_record(
                case_id=case_id,
                bene_id=bene_id,
                analytic_year=YEAR,
                summary=summary,
                template_narrative=build_template_narrative(bundle),
                prompt_hash=prompt_hash,
            )
        )
        print(f"Frozen {case_id} -> {key} ({summary.provider})")

    meta = freeze_metadata(settings)
    if args.allow_template:
        meta["provider"] = "template"
        meta["adjudication_required"] = False
        meta["model_version"] = "frozen-template-v1"

    output = REPO_ROOT / "study" / "frozen_summaries.json"
    payload = {
        **meta,
        "prompt_hashes": prompt_hashes,
        "summaries": summaries,
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    queue_path = REPO_ROOT / "study" / "adjudication_queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "schema_version": "1.1",
                "generated_at": meta["generated_at"],
                "provider": meta["provider"],
                "llm_model": meta.get("llm_model"),
                "ai_evidence_audit": "pending" if meta["provider"] != "template" else "not_required",
                "human_review": "pending" if meta["provider"] != "template" else "not_required",
                "items": adjudication,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {output} ({len(summaries)} summaries)")
    print(f"Wrote {queue_path} ({len(adjudication)} adjudication items)")


if __name__ == "__main__":
    main()
