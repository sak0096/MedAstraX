"""Ingestion pipeline entry point (Phase 1)."""

from __future__ import annotations

from typing import Optional

from hc_analytics.config import Settings, get_settings
from hc_analytics.schemas.common import ProvenanceRecord


def run_ingestion(settings: Optional[Settings] = None) -> ProvenanceRecord:
    """Download, parse, validate, and stage CMS synthetic data.

    Phase 0 scaffold — implementation arrives in Phase 1.
    """
    settings = settings or get_settings()
    settings.raw_data_path.mkdir(parents=True, exist_ok=True)
    settings.processed_data_path.mkdir(parents=True, exist_ok=True)
    raise NotImplementedError(
        "Ingestion pipeline not yet implemented. See docs/DATA.md and Phase 1 roadmap."
    )
