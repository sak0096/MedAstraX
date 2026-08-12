from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

from hc_analytics import __version__
from hc_analytics.config import Settings, get_settings
from hc_analytics.instrumentation.constants import DASHBOARD_BUILD_VERSION, INSTRUMENTATION_SCHEMA_VERSION
from hc_analytics.language.constants import LANGUAGE_SCHEMA_VERSION
from hc_analytics.modeling.constants import TARGET_SHORT_NAMES, RiskTarget
from hc_analytics.modeling.trainers import require_primary_model_family


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_manifest(path: Path, key: str = "schema_version") -> Optional[str]:
    payload = _read_json(path)
    value = payload.get(key)
    return str(value) if value is not None else None


def _sha256_file(path: Path, *, length: int = 16) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()[:length]


def build_version_context(settings: Optional[Settings] = None) -> Dict[str, Any]:
    settings = settings or get_settings()
    artifacts = settings.artifacts_path
    model_manifest = _read_json(artifacts / "model_manifest.json")
    explanation_manifest = _read_json(artifacts / "explanations" / "manifest.json")
    frozen = _read_json(settings.repo_root / "study" / "frozen_summaries.json")

    try:
        primary_family = model_manifest.get("primary_model_family") or require_primary_model_family()
    except Exception:
        primary_family = model_manifest.get("primary_model_family")

    model_hashes: Dict[str, Optional[str]] = {}
    for target in RiskTarget:
        short = TARGET_SHORT_NAMES[target]
        if not primary_family:
            continue
        model_path = artifacts / "models" / short / f"{primary_family}.joblib"
        model_hashes[short] = _sha256_file(model_path)

    return {
        "instrumentation_schema": INSTRUMENTATION_SCHEMA_VERSION,
        "api_version": __version__,
        "dashboard_build": DASHBOARD_BUILD_VERSION,
        "prototype_phase": "8",
        "model_version": model_manifest.get("schema_version"),
        "model_family": primary_family,
        "model_git_commit": model_manifest.get("git_commit"),
        "model_artifact_hashes": model_hashes,
        "explanation_version": explanation_manifest.get("schema_version"),
        "explanation_git_commit": explanation_manifest.get("git_commit"),
        "explanation_row_count": explanation_manifest.get("row_count"),
        "local_topk_hash": _sha256_file(artifacts / "explanations" / "local_topk.parquet"),
        "language_version": LANGUAGE_SCHEMA_VERSION,
        "frozen_summary_provider": frozen.get("provider"),
        "frozen_summary_model_version": frozen.get("model_version"),
        "frozen_summaries_hash": _sha256_file(settings.repo_root / "study" / "frozen_summaries.json"),
        "study_cases_hash": _sha256_file(settings.repo_root / "study" / "study_cases.json"),
        "study_id": settings.study_id,
        "experimental_condition": settings.experimental_condition.value,
    }
