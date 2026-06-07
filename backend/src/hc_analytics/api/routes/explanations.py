from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from hc_analytics.config import get_settings
from hc_analytics.explainability.bundles import EvidenceBundle
from hc_analytics.explainability.pipeline import (
    _explanations_dir,
    load_cached_bundle,
    load_global_importance,
)
from hc_analytics.modeling.constants import RiskTarget, TARGET_SHORT_NAMES

router = APIRouter(prefix="/api", tags=["explanations"])


def _local_topk_path() -> Path:
    return _explanations_dir(get_settings()) / "local_topk.parquet"


def _explanations_ready() -> bool:
    explanations_dir = _explanations_dir(get_settings())
    return (explanations_dir / "manifest.json").exists()


def _parse_target(target: Optional[str]) -> RiskTarget:
    if target is None:
        return RiskTarget.HOSPITALIZATION
    normalized = target.strip().lower()
    aliases = {
        **{item.value: item for item in RiskTarget},
        **{short: item for item, short in TARGET_SHORT_NAMES.items()},
    }
    if normalized not in aliases:
        raise HTTPException(status_code=400, detail=f"Unknown target: {target}")
    return aliases[normalized]


def _load_local_topk() -> pd.DataFrame:
    path = _local_topk_path()
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail="Explanations not available. Run `python -m hc_analytics.explainability` first.",
        )
    return pd.read_parquet(path)


@router.get("/explanations/meta")
def explanations_meta() -> Dict[str, Any]:
    settings = get_settings()
    manifest_path = _explanations_dir(settings) / "manifest.json"
    payload: Dict[str, Any] = {
        "explanations_ready": _explanations_ready(),
        "targets": [target.value for target in RiskTarget],
    }
    if manifest_path.exists():
        import json

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload.update(
            {
                "schema_version": manifest.get("schema_version"),
                "model_family": manifest.get("model_family"),
                "top_k": manifest.get("top_k"),
                "row_count": manifest.get("row_count"),
                "stability_method": manifest.get("stability_method"),
            }
        )
    return payload


@router.get("/explanations/global")
def global_explanations(
    target: Optional[str] = Query(default="hospitalization"),
) -> Dict[str, Any]:
    selected = _parse_target(target)
    payload = load_global_importance(selected, settings=get_settings())
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"Global explanations for {selected.value} not found.",
        )
    return payload


@router.get("/explanations/{bene_id}")
def beneficiary_explanations(
    bene_id: str,
    analytic_year: Optional[int] = Query(default=None),
    target: Optional[str] = Query(default=None),
    top_k: int = Query(default=5, ge=1, le=10),
) -> Dict[str, Any]:
    frame = _load_local_topk()
    frame = frame.loc[frame["bene_id"] == bene_id]
    if analytic_year is not None:
        frame = frame.loc[frame["analytic_year"] == analytic_year]
    if target is not None:
        selected = _parse_target(target)
        frame = frame.loc[frame["target"] == selected.value]

    if frame.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No explanations found for beneficiary {bene_id}.",
        )

    if analytic_year is None:
        analytic_year = int(frame["analytic_year"].max())

    frame = frame.loc[frame["analytic_year"] == analytic_year]
    frame = frame.sort_values(["target", "rank"]).head(top_k * frame["target"].nunique())
    records = frame.where(pd.notna(frame), None).to_dict(orient="records")
    stability = (
        frame.groupby("target", as_index=False)[["stability_badge", "stability_score"]]
        .first()
        .to_dict(orient="records")
    )
    return {
        "bene_id": bene_id,
        "analytic_year": analytic_year,
        "contributors": records,
        "stability": stability,
    }


@router.get("/explanations/{bene_id}/bundle")
def beneficiary_evidence_bundle(
    bene_id: str,
    analytic_year: Optional[int] = Query(default=None),
) -> Dict[str, Any]:
    settings = get_settings()
    if analytic_year is None:
        local = _load_local_topk()
        years = local.loc[local["bene_id"] == bene_id, "analytic_year"]
        if years.empty:
            raise HTTPException(status_code=404, detail=f"No bundle found for {bene_id}.")
        analytic_year = int(years.max())

    bundle = load_cached_bundle(bene_id, analytic_year, settings=get_settings())
    if bundle is None:
        raise HTTPException(
            status_code=404,
            detail=f"No evidence bundle found for {bene_id} ({analytic_year}).",
        )
    return bundle.model_dump()
