from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from hc_analytics.api.data_access import (
    BENEFICIARY_LIST_COLUMNS,
    CHRONIC_CONDITION_COLUMNS,
    CHRONIC_CONDITION_LABELS,
    frame_to_records,
    load_merged_dashboard_frame,
)
from hc_analytics.modeling.constants import RiskTarget, risk_score_column

PRIMARY_RISK_COLUMNS = [risk_score_column(target) for target in RiskTarget]

router = APIRouter(prefix="/api/beneficiaries", tags=["beneficiaries"])

SORTABLE_COLUMNS = set(BENEFICIARY_LIST_COLUMNS)


@router.get("")
def list_beneficiaries(
    bene_id: Optional[str] = Query(default=None),
    analytic_year: Optional[int] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    sort_by: str = Query(default="hospitalization_risk"),
    descending: bool = Query(default=True),
) -> Dict[str, Any]:
    frame = load_merged_dashboard_frame()
    if bene_id is not None:
        frame = frame.loc[frame["bene_id"] == bene_id]
    if analytic_year is not None:
        frame = frame.loc[frame["analytic_year"] == analytic_year]

    if frame.empty:
        raise HTTPException(status_code=404, detail="No matching beneficiaries found.")

    if sort_by in SORTABLE_COLUMNS and sort_by in frame.columns:
        frame = frame.sort_values(sort_by, ascending=not descending)

    available_columns = [column for column in BENEFICIARY_LIST_COLUMNS if column in frame.columns]
    frame = frame[available_columns].head(limit)
    records = frame_to_records(frame)
    return {
        "count": len(records),
        "sort_by": sort_by,
        "rows": records,
    }


def _chronic_conditions(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    conditions: List[Dict[str, Any]] = []
    for column, label in CHRONIC_CONDITION_LABELS.items():
        value = record.get(column)
        if value in (1, True, "1"):
            conditions.append({"field": column, "label": label})
    return conditions


@router.get("/{bene_id}")
def get_beneficiary(
    bene_id: str,
    analytic_year: Optional[int] = Query(default=None),
) -> Dict[str, Any]:
    frame = load_merged_dashboard_frame()
    frame = frame.loc[frame["bene_id"] == bene_id]
    if analytic_year is not None:
        frame = frame.loc[frame["analytic_year"] == analytic_year]

    if frame.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No beneficiary record found for {bene_id}.",
        )

    if analytic_year is None and len(frame) > 1:
        frame = frame.sort_values("analytic_year", ascending=False)

    history = frame_to_records(frame)
    latest = history[0]
    risk_scores = {
        column: latest.get(column)
        for column in PRIMARY_RISK_COLUMNS
        if column in latest
    }
    utilization = {
        "inpatient_claims": latest.get("inpatient_claims"),
        "outpatient_claims": latest.get("outpatient_claims"),
        "carrier_claims": latest.get("carrier_claims"),
        "total_claims": latest.get("total_claims"),
        "total_payment_amt": latest.get("total_payment_amt"),
        "inpatient_payment_amt": latest.get("inpatient_payment_amt"),
        "readmission_30d_count": latest.get("readmission_30d_count"),
    }
    prescriptions = {
        "rx_fill_count": latest.get("rx_fill_count"),
        "rx_unique_drugs": latest.get("rx_unique_drugs"),
        "rx_days_supply": latest.get("rx_days_supply"),
    }
    chronic_conditions = _chronic_conditions(latest)

    return {
        "bene_id": bene_id,
        "analytic_year": latest.get("analytic_year"),
        "demographics": {
            "age": latest.get("age"),
            "sex": latest.get("sex"),
            "race": latest.get("race"),
            "state_code": latest.get("state_code"),
            "esrd_ind": latest.get("esrd_ind"),
        },
        "risk_scores": risk_scores,
        "utilization": utilization,
        "prescriptions": prescriptions,
        "diagnosis": {
            "distinct_diagnosis_count": latest.get("distinct_diagnosis_count"),
            "chronic_condition_count": latest.get("chronic_condition_count"),
            "chronic_conditions": chronic_conditions,
            "chronic_flags": {
                column: latest.get(column) for column in CHRONIC_CONDITION_COLUMNS
            },
        },
        "labels": {
            "next_year_hospitalization": latest.get("next_year_hospitalization"),
            "next_year_high_utilization": latest.get("next_year_high_utilization"),
            "next_year_elevated_cost": latest.get("next_year_elevated_cost"),
        },
        "model_version": latest.get("model_version"),
        "history": history,
    }
