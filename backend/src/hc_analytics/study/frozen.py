"""Load frozen LLM summary stimuli for study mode."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from hc_analytics.config import Settings, get_settings
from hc_analytics.language.models import GroundedSummaryResponse


def frozen_summaries_path(settings: Optional[Settings] = None) -> Path:
    runtime = settings or get_settings()
    return runtime.repo_root / "study" / "frozen_summaries.json"


@lru_cache(maxsize=1)
def _cached_frozen(path_str: str, mtime_ns: int) -> Dict[str, Any]:
    _ = mtime_ns
    return json.loads(Path(path_str).read_text(encoding="utf-8"))


def load_frozen_summary(
    bene_id: str,
    analytic_year: int,
    *,
    settings: Optional[Settings] = None,
) -> Optional[GroundedSummaryResponse]:
    runtime = settings or get_settings()
    path = frozen_summaries_path(runtime)
    if not path.exists():
        return None
    catalog = _cached_frozen(str(path), path.stat().st_mtime_ns)
    key = f"{bene_id}:{analytic_year}"
    payload = catalog.get("summaries", {}).get(key)
    if payload is None:
        return None
    return GroundedSummaryResponse.model_validate(payload)
