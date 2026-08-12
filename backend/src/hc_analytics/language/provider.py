from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from hc_analytics.config import Settings, get_settings
from hc_analytics.explainability.bundles import EvidenceBundle
from hc_analytics.ingestion.io import git_commit_hash
from hc_analytics.language.models import GroundedSummaryResponse
from hc_analytics.language.summaries import build_grounded_summary, build_template_narrative


def active_provider_name(settings: Optional[Settings] = None) -> str:
    settings = settings or get_settings()
    if settings.llm_provider and settings.llm_api_key and settings.llm_model:
        return str(settings.llm_provider)
    return "template"


def provider_configured(settings: Optional[Settings] = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.llm_provider and settings.llm_api_key and settings.llm_model)


def prompt_fingerprint(bundle: EvidenceBundle) -> str:
    payload = {
        "bene_id": bundle.bene_id,
        "analytic_year": bundle.analytic_year,
        "targets": [target.model_dump() for target in bundle.targets],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return digest[:16]


def _claims_supported(narrative: str, bundle: EvidenceBundle) -> bool:
    """Reject polish that drops every grounded claim signal."""
    if bundle.grounded.fallback:
        return True
    lowered = narrative.lower()
    hits = 0
    for claim in bundle.grounded.claims:
        token = claim.statement.lower()[:24].strip()
        if token and token in lowered:
            hits += 1
            continue
        for field in claim.source_fields:
            label = field.replace("_", " ").lower()
            if label and label in lowered:
                hits += 1
                break
    return hits >= max(1, min(2, len(bundle.grounded.claims)))


def generate_grounded_summary(
    bundle: EvidenceBundle,
    settings: Optional[Settings] = None,
    *,
    allow_llm: bool = True,
) -> GroundedSummaryResponse:
    settings = settings or get_settings()
    provider = active_provider_name(settings)
    base = build_grounded_summary(bundle, provider="template")

    if not allow_llm or not provider_configured(settings) or provider == "template":
        return base

    from hc_analytics.language.openai_provider import polish_narrative_with_llm

    polished = polish_narrative_with_llm(bundle, settings=settings)
    narrative = polished["narrative"]
    if not _claims_supported(narrative, bundle):
        # Safety: keep grounded template if polish drifts from allowed claims.
        return base.model_copy(
            update={
                "provider": "template_fallback",
                "narrative": build_template_narrative(bundle),
            }
        )
    return base.model_copy(
        update={
            "provider": provider,
            "narrative": narrative,
        }
    )


def freeze_metadata(settings: Optional[Settings] = None) -> dict:
    settings = settings or get_settings()
    configured = provider_configured(settings)
    provider = active_provider_name(settings) if configured else "template"
    return {
        "schema_version": "1.2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit_hash(settings.repo_root),
        "provider": provider,
        "llm_model": settings.llm_model if configured else None,
        "llm_temperature": settings.llm_temperature if configured else None,
        "prompt_version": "grounded-polish-v1" if configured else "grounded-template-v1",
        "model_version": (
            f"frozen-{settings.llm_model}" if configured and settings.llm_model else "frozen-template-v1"
        ),
        "adjudication_required": configured,
        "notes": (
            "When HC_LLM_* is configured, narratives are LLM-polished over grounded claims and "
            "must be human-adjudicated via study/adjudication_queue.json before confirmatory use. "
            "Without LLM credentials, stimuli remain grounded template summaries "
            "(natural-language augmentation, not an LLM-capability evaluation)."
        ),
    }


def adjudication_record(
    *,
    case_id: str,
    bene_id: str,
    analytic_year: int,
    summary: GroundedSummaryResponse,
    template_narrative: str,
    prompt_hash: str,
) -> Dict[str, Any]:
    return {
        "case_id": case_id,
        "bene_id": bene_id,
        "analytic_year": analytic_year,
        "provider": summary.provider,
        "prompt_hash": prompt_hash,
        "template_narrative": template_narrative,
        "candidate_narrative": summary.narrative,
        "claims": [claim.model_dump() for claim in summary.grounded.claims],
        "status": "pending" if summary.provider != "template" else "auto_accepted_template",
        "decision": None,
        "reviewer": None,
        "reviewed_at": None,
        "notes": None,
    }
