from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from hc_analytics.config import get_settings
from hc_analytics.modeling.constants import RiskTarget, risk_score_column

router = APIRouter(prefix="/api", tags=["predictions"])

RISK_COLUMNS = [
    risk_score_column(target, family)
    for target in RiskTarget
    for family in ("xgboost", "logistic_regression")
]
PRIMARY_RISK_COLUMNS = [risk_score_column(target) for target in RiskTarget]


def _predictions_path() -> Path:
    return get_settings().processed_data_path / "predictions.parquet"


def _load_predictions() -> pd.DataFrame:
    path = _predictions_path()
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail="Predictions not available. Run `python -m hc_analytics.modeling` first.",
        )
    return pd.read_parquet(path)


def _models_ready() -> bool:
    models_dir = get_settings().artifacts_path / "models"
    return models_dir.exists() and any(models_dir.rglob("*.joblib"))


@router.get("/models/meta")
def models_meta() -> Dict[str, Any]:
    settings = get_settings()
    manifest_path = settings.artifacts_path / "model_manifest.json"
    predictions_ready = _predictions_path().exists()
    payload: Dict[str, Any] = {
        "models_ready": _models_ready(),
        "predictions_ready": predictions_ready,
        "primary_risk_columns": PRIMARY_RISK_COLUMNS,
        "targets": [target.value for target in RiskTarget],
    }
    if manifest_path.exists():
        import json

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["model_version"] = manifest.get("schema_version", "unknown")
        payload["model_families"] = manifest.get("model_families", [])
        payload["split"] = manifest.get("split", {})
    return payload


@router.get("/predictions")
def get_predictions(
    bene_id: Optional[str] = Query(default=None),
    analytic_year: Optional[int] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    sort_by: str = Query(default="hospitalization_risk"),
    descending: bool = Query(default=True),
) -> Dict[str, object]:
    frame = _load_predictions()
    if bene_id is not None:
        frame = frame.loc[frame["bene_id"] == bene_id]
    if analytic_year is not None:
        frame = frame.loc[frame["analytic_year"] == analytic_year]

    if frame.empty:
        raise HTTPException(status_code=404, detail="No matching predictions found.")

    if sort_by in frame.columns:
        frame = frame.sort_values(sort_by, ascending=not descending)
    frame = frame.head(limit)

    records = frame.where(pd.notna(frame), None).to_dict(orient="records")
    return {
        "count": len(records),
        "sort_by": sort_by,
        "rows": records,
    }


@router.get("/predictions/{bene_id}")
def get_prediction_for_beneficiary(
    bene_id: str,
    analytic_year: Optional[int] = Query(default=None),
) -> Dict[str, object]:
    frame = _load_predictions()
    frame = frame.loc[frame["bene_id"] == bene_id]
    if analytic_year is not None:
        frame = frame.loc[frame["analytic_year"] == analytic_year]

    if frame.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No predictions found for beneficiary {bene_id}.",
        )

    if analytic_year is None and len(frame) > 1:
        frame = frame.sort_values("analytic_year", ascending=False).head(1)

    record = frame.iloc[0].where(pd.notna(frame.iloc[0]), None).to_dict()
    return {"bene_id": bene_id, "prediction": record}
