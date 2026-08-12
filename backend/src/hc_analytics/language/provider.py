from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from hc_analytics.config import Settings, get_settings
from hc_analytics.explainability.bundles import EvidenceBundle
from hc_analytics.ingestion.io import git_commit_hash
from hc_analytics.language.models import GroundedSummaryResponse
from hc_analytics.language.summaries import build_grounded_summary


def active_provider_name(settings: Optional[Settings] = None) -> str:
    settings = settings or get_settings()
    if settings.llm_provider and settings.llm_api_key and settings.llm_model:
        return settings.llm_provider
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


def generate_grounded_summary(
    bundle: EvidenceBundle,
    settings: Optional[Settings] = None,
) -> GroundedSummaryResponse:
    settings = settings or get_settings()
    provider = active_provider_name(settings)
    # Named-model polishing is optional. When configured, the freeze script records model
    # metadata; the grounded template remains the safety baseline until adjudication lands.
    if provider_configured(settings) and provider != "template":
        # External generation path reserved for freeze-time adjudication workflows.
        # Until a provider adapter is approved, fall back to the grounded template.
        pass
    return build_grounded_summary(bundle, provider=provider if provider == "template" else "template")


def freeze_metadata(settings: Optional[Settings] = None) -> dict:
    settings = settings or get_settings()
    configured = provider_configured(settings)
    return {
        "schema_version": "1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit_hash(settings.repo_root),
        "provider": active_provider_name(settings) if configured else "template",
        "llm_model": settings.llm_model if configured else None,
        "llm_temperature": settings.llm_temperature if configured else None,
        "prompt_version": "grounded-template-v1",
        "model_version": (
            f"frozen-{settings.llm_model}" if configured and settings.llm_model else "frozen-template-v1"
        ),
        "adjudication_required": configured,
        "notes": (
            "Named LLM outputs must be human-adjudicated before study freeze. "
            "Current generator emits grounded template narratives."
        ),
    }
