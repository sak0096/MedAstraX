from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from hc_analytics import __version__
from hc_analytics.config import Settings, get_settings
from hc_analytics.instrumentation.constants import DASHBOARD_BUILD_VERSION, INSTRUMENTATION_SCHEMA_VERSION
from hc_analytics.language.constants import LANGUAGE_SCHEMA_VERSION


def _read_manifest(path: Path, key: str = "schema_version") -> Optional[str]:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    value = payload.get(key)
    return str(value) if value is not None else None


def build_version_context(settings: Optional[Settings] = None) -> Dict[str, Any]:
    settings = settings or get_settings()
    artifacts = settings.artifacts_path
    return {
        "instrumentation_schema": INSTRUMENTATION_SCHEMA_VERSION,
        "api_version": __version__,
        "dashboard_build": DASHBOARD_BUILD_VERSION,
        "prototype_phase": "8",
        "model_version": _read_manifest(artifacts / "model_manifest.json"),
        "explanation_version": _read_manifest(artifacts / "explanations" / "manifest.json"),
        "language_version": LANGUAGE_SCHEMA_VERSION,
        "study_id": settings.study_id,
        "experimental_condition": settings.experimental_condition.value,
    }
