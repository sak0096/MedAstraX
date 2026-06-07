from __future__ import annotations

from typing import Optional

from hc_analytics.config import Settings, get_settings
from hc_analytics.explainability.bundles import EvidenceBundle
from hc_analytics.language.models import GroundedSummaryResponse
from hc_analytics.language.summaries import build_grounded_summary


def active_provider_name(settings: Optional[Settings] = None) -> str:
    settings = settings or get_settings()
    if settings.llm_provider and settings.llm_api_key:
        return settings.llm_provider
    return "template"


def provider_configured(settings: Optional[Settings] = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.llm_provider and settings.llm_api_key and settings.llm_model)


def generate_grounded_summary(bundle: EvidenceBundle, settings: Optional[Settings] = None) -> GroundedSummaryResponse:
    settings = settings or get_settings()
    provider = active_provider_name(settings)
    # External LLM polishing is intentionally deferred; template summaries remain fully grounded.
    return build_grounded_summary(bundle, provider=provider)
