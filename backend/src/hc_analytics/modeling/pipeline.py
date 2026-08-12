"""Model training pipeline (Phase 3)."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from hc_analytics.config import Settings, get_settings
from hc_analytics.ingestion.io import git_commit_hash
from hc_analytics.modeling.constants import (
    FEATURE_COLUMNS,
    MODEL_FAMILIES,
    MODEL_SCHEMA_VERSION,
    PRIMARY_MODEL_FAMILY,
    RiskTarget,
    risk_score_column,
)
from hc_analytics.modeling.split import calibration_frame, time_based_year_split
from hc_analytics.modeling.trainers import (
    load_model_artifact,
    require_primary_model_family,
    save_model_artifact,
    train_model,
    xgboost_available,
)


def _active_model_families() -> tuple[str, ...]:
    family = require_primary_model_family()
    if family == PRIMARY_MODEL_FAMILY and xgboost_available():
        return MODEL_FAMILIES
    return (family,)


def _primary_model_family() -> str:
    return require_primary_model_family()


def _load_feature_store(processed_dir: Path) -> pd.DataFrame:
    path = processed_dir / "feature_store.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing feature store at {path}. Run `python -m hc_analytics.features` first."
        )
    return pd.read_parquet(path)


def _rows_with_valid_next_year(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep beneficiary-years where the immediate next analytic year is observed."""
    ordered = frame.sort_values(["bene_id", "analytic_year"]).copy()
    next_year = ordered.groupby("bene_id", sort=False)["analytic_year"].shift(-1)
    valid = (next_year - ordered["analytic_year"]) == 1
    return ordered.loc[valid.fillna(False)].copy()


def _frame_with_next_year_outcomes(frame: pd.DataFrame) -> pd.DataFrame:
    """Join each beneficiary-year to outcomes in the immediate next analytic year."""
    next_year = frame[
        ["bene_id", "analytic_year", "inpatient_claims", "total_claims", "total_payment_amt"]
    ].copy()
    next_year["analytic_year"] = next_year["analytic_year"] - 1
    next_year = next_year.rename(
        columns={
            "inpatient_claims": "next_inpatient_claims",
            "total_claims": "next_total_claims",
            "total_payment_amt": "next_total_payment_amt",
        }
    )

    return frame.merge(next_year, on=["bene_id", "analytic_year"], how="inner")


def _rows_with_informative_followup(
    outcomes: pd.DataFrame,
    *,
    min_positive_rate: float = 0.01,
) -> pd.DataFrame:
    """Exclude years whose next-year claims are absent from the source extract."""
    positive_rates = outcomes.groupby("analytic_year")["next_total_claims"].apply(
        lambda values: float(values.gt(0).mean())
    )
    eligible_years = [
        int(year) for year, rate in positive_rates.items() if rate >= min_positive_rate
    ]
    if not eligible_years:
        raise ValueError("No analytic years have informative next-year claims follow-up.")
    return outcomes.loc[outcomes["analytic_year"].isin(eligible_years)].copy()


def _positive_quantile(series: pd.Series, *, quantile: float, label: str) -> float:
    positive = series.loc[series > 0].dropna()
    if positive.empty:
        raise ValueError(f"Cannot derive {label}: training years contain no positive outcomes.")
    return float(positive.quantile(quantile))


def _derive_label_definitions(
    outcomes: pd.DataFrame,
    *,
    threshold_years: Sequence[int],
) -> Dict[str, Dict[str, Any]]:
    """Freeze label thresholds using training years only."""
    source_years = tuple(sorted(int(year) for year in threshold_years))
    threshold_frame = outcomes.loc[outcomes["analytic_year"].isin(source_years)]
    if threshold_frame.empty:
        raise ValueError("Cannot derive label thresholds without training-year outcomes.")

    quantile = 0.75
    claims_threshold = _positive_quantile(
        threshold_frame["next_total_claims"],
        quantile=quantile,
        label=RiskTarget.HIGH_UTILIZATION.value,
    )
    cost_threshold = _positive_quantile(
        threshold_frame["next_total_payment_amt"],
        quantile=quantile,
        label=RiskTarget.ELEVATED_COST.value,
    )
    shared = {
        "outcome_horizon": "immediate_next_analytic_year",
        "threshold_source": "training_years_only",
        "threshold_source_years": list(source_years),
    }
    return {
        RiskTarget.HOSPITALIZATION.value: {
            **shared,
            "event_definition": "next_inpatient_claims > 0",
            "threshold": 0.0,
            "positive_only": False,
        },
        RiskTarget.HIGH_UTILIZATION.value: {
            **shared,
            "event_definition": "next_total_claims >= threshold",
            "threshold": claims_threshold,
            "quantile": quantile,
            "positive_only": True,
        },
        RiskTarget.ELEVATED_COST.value: {
            **shared,
            "event_definition": "next_total_payment_amt >= threshold",
            "threshold": cost_threshold,
            "quantile": quantile,
            "positive_only": True,
        },
    }


def _apply_modeling_labels(
    outcomes: pd.DataFrame,
    *,
    label_definitions: Dict[str, Dict[str, Any]],
) -> pd.DataFrame:
    labeled = outcomes.copy()
    claims_threshold = float(label_definitions[RiskTarget.HIGH_UTILIZATION.value]["threshold"])
    cost_threshold = float(label_definitions[RiskTarget.ELEVATED_COST.value]["threshold"])

    labeled[RiskTarget.HOSPITALIZATION.value] = labeled["next_inpatient_claims"].gt(0).astype(int)
    labeled[RiskTarget.HIGH_UTILIZATION.value] = (
        labeled["next_total_claims"] >= claims_threshold
    ).astype(int)
    labeled[RiskTarget.ELEVATED_COST.value] = (
        labeled["next_total_payment_amt"] >= cost_threshold
    ).astype(int)
    return labeled


def _frame_with_modeling_labels(
    frame: pd.DataFrame,
    *,
    threshold_years: Sequence[int],
) -> pd.DataFrame:
    """Derive next-year labels with thresholds frozen from explicit training years."""
    outcomes = _frame_with_next_year_outcomes(frame)
    definitions = _derive_label_definitions(outcomes, threshold_years=threshold_years)
    return _apply_modeling_labels(outcomes, label_definitions=definitions)


def _score_frame(
    frame: pd.DataFrame,
    *,
    models_dir: Path,
    target: RiskTarget,
) -> pd.DataFrame:
    scores = frame[["bene_id", "analytic_year"]].copy()
    primary_family = _primary_model_family()
    for family in _active_model_families():
        pipeline = load_model_artifact(models_dir, target, family)
        prob = pipeline.predict_proba(frame[FEATURE_COLUMNS])[:, 1]
        scores[risk_score_column(target, family)] = prob
        if family == primary_family:
            scores[risk_score_column(target)] = prob
    return scores


def train_all_models(
    settings: Optional[Settings] = None,
    *,
    targets: Optional[List[RiskTarget]] = None,
    test_year_count: int = 2,
) -> Dict[str, object]:
    settings = settings or get_settings()
    features = _load_feature_store(settings.processed_data_path)
    models_dir = settings.artifacts_path / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    targets = targets or list(RiskTarget)
    git_commit = git_commit_hash(settings.repo_root)
    trained_targets: List[str] = []
    outcomes = _rows_with_informative_followup(_frame_with_next_year_outcomes(features))
    _, _, split_spec = time_based_year_split(
        outcomes,
        test_year_count=test_year_count,
        calibration_year_count=1,
    )
    label_definitions = _derive_label_definitions(
        outcomes,
        threshold_years=split_spec.train_years,
    )
    labeled = _apply_modeling_labels(outcomes, label_definitions=label_definitions)
    split_payload = {
        **asdict(split_spec),
        "followup_eligibility": "next_total_claims_positive_rate >= 0.01",
    }

    for target in targets:
        train = labeled.loc[labeled["analytic_year"].isin(split_spec.train_years)].copy()
        test = labeled.loc[labeled["analytic_year"].isin(split_spec.test_years)].copy()
        calib = calibration_frame(
            labeled,
            year_column="analytic_year",
            calibration_years=split_spec.calibration_years,
        )

        for family in _active_model_families():
            pipeline, metrics = train_model(
                family=family,
                target=target,
                train_x=train,
                train_y=train[target.value],
                test_x=test,
                test_y=test[target.value],
                calibration_x=calib if len(calib) else None,
                calibration_y=calib[target.value] if len(calib) else None,
            )
            save_model_artifact(
                pipeline=pipeline,
                models_dir=models_dir,
                target=target,
                family=family,
                metrics=metrics,
                split_spec=split_payload,
                feature_columns=FEATURE_COLUMNS,
                git_commit=git_commit,
                label_definition=label_definitions[target.value],
            )
        trained_targets.append(target.value)

    manifest_path = _write_model_manifest(
        settings=settings,
        models_dir=models_dir,
        targets=trained_targets,
        git_commit=git_commit,
        test_year_count=test_year_count,
        label_definitions={target: label_definitions[target] for target in trained_targets},
    )

    return {
        "models_dir": str(models_dir),
        "targets": trained_targets,
        "manifest": str(manifest_path),
    }


def build_predictions(
    settings: Optional[Settings] = None,
    *,
    targets: Optional[List[RiskTarget]] = None,
) -> pd.DataFrame:
    settings = settings or get_settings()
    features = _load_feature_store(settings.processed_data_path)
    models_dir = settings.artifacts_path / "models"
    targets = targets or list(RiskTarget)

    predictions = features[["bene_id", "analytic_year"]].copy()
    for target in targets:
        target_scores = _score_frame(features, models_dir=models_dir, target=target)
        score_columns = [
            column
            for column in target_scores.columns
            if column not in {"bene_id", "analytic_year"}
        ]
        predictions = predictions.merge(
            target_scores[["bene_id", "analytic_year", *score_columns]],
            on=["bene_id", "analytic_year"],
            how="left",
        )

    predictions["model_version"] = MODEL_SCHEMA_VERSION
    predictions["primary_model_family"] = _primary_model_family()
    return predictions.sort_values(["bene_id", "analytic_year"]).reset_index(drop=True)


def _write_model_manifest(
    *,
    settings: Settings,
    models_dir: Path,
    targets: List[str],
    git_commit: Optional[str],
    test_year_count: int,
    label_definitions: Dict[str, Dict[str, Any]],
) -> Path:
    manifest_path = settings.artifacts_path / "model_manifest.json"
    settings.artifacts_path.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": MODEL_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "targets": targets,
        "model_families": list(_active_model_families()),
        "primary_model_family": _primary_model_family(),
        "xgboost_available": xgboost_available(),
        "split": {
            "strategy": "time_based_year_holdout",
            "test_year_count": test_year_count,
        },
        "feature_columns": FEATURE_COLUMNS,
        "label_definitions": label_definitions,
        "models_dir": str(models_dir),
        "predictions_output": str(settings.processed_data_path / "predictions.parquet"),
    }
    hosp_meta = models_dir / "hospitalization" / "metadata.json"
    if hosp_meta.exists():
        try:
            hosp = json.loads(hosp_meta.read_text(encoding="utf-8"))
            if isinstance(hosp.get("split"), dict):
                payload["split"] = {**payload["split"], **hosp["split"]}
        except (OSError, json.JSONDecodeError):
            pass
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return manifest_path


def run_training(
    settings: Optional[Settings] = None,
    *,
    targets: Optional[List[RiskTarget]] = None,
    test_year_count: int = 2,
) -> Dict[str, object]:
    train_result = train_all_models(
        settings=settings,
        targets=targets,
        test_year_count=test_year_count,
    )
    settings = settings or get_settings()
    predictions = build_predictions(settings=settings, targets=targets)
    predictions_path = settings.processed_data_path / "predictions.parquet"
    settings.processed_data_path.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(predictions_path, index=False)

    return {
        **train_result,
        "prediction_rows": len(predictions),
        "predictions": str(predictions_path),
    }


def run_training_for_target(
    target: RiskTarget = RiskTarget.HOSPITALIZATION,
    settings: Optional[Settings] = None,
) -> Dict[str, object]:
    return run_training(settings=settings, targets=[target])
