"""Model training pipeline (Phase 3)."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

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
from hc_analytics.modeling.split import time_based_year_split
from hc_analytics.modeling.trainers import (
    load_model_artifact,
    save_model_artifact,
    train_model,
    xgboost_available,
)


def _active_model_families() -> tuple[str, ...]:
    if xgboost_available():
        return MODEL_FAMILIES
    return ("logistic_regression",)


def _primary_model_family() -> str:
    if xgboost_available():
        return PRIMARY_MODEL_FAMILY
    return "logistic_regression"


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


def _frame_with_modeling_labels(frame: pd.DataFrame) -> pd.DataFrame:
    """Derive next-year labels from explicit year+1 joins (more reliable than row shifts)."""
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

    labeled = frame.merge(next_year, on=["bene_id", "analytic_year"], how="inner")
    claims_threshold = labeled["next_total_claims"][labeled["next_total_claims"] > 0].quantile(0.75)
    cost_threshold = labeled["next_total_payment_amt"][
        labeled["next_total_payment_amt"] > 0
    ].quantile(0.75)

    labeled[RiskTarget.HOSPITALIZATION.value] = labeled["next_inpatient_claims"].gt(0).astype(int)
    labeled[RiskTarget.HIGH_UTILIZATION.value] = (
        labeled["next_total_claims"] >= claims_threshold
    ).astype(int)
    labeled[RiskTarget.ELEVATED_COST.value] = (
        labeled["next_total_payment_amt"] >= cost_threshold
    ).astype(int)
    return labeled


def _labeled_rows(frame: pd.DataFrame, target: RiskTarget) -> pd.DataFrame:
    labeled = _frame_with_modeling_labels(frame)
    labeled = labeled.dropna(subset=[target.value]).copy()
    labeled[target.value] = labeled[target.value].astype(int)
    return labeled


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

    for target in targets:
        labeled = _labeled_rows(features, target)
        train, test, split_spec = time_based_year_split(
            labeled,
            label_column=target.value,
            test_year_count=test_year_count,
        )
        split_payload = asdict(split_spec)

        for family in _active_model_families():
            pipeline, metrics = train_model(
                family=family,
                target=target,
                train_x=train,
                train_y=train[target.value],
                test_x=test,
                test_y=test[target.value],
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
            )
        trained_targets.append(target.value)

    manifest_path = _write_model_manifest(
        settings=settings,
        models_dir=models_dir,
        targets=trained_targets,
        git_commit=git_commit,
        test_year_count=test_year_count,
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
        "models_dir": str(models_dir),
        "predictions_output": str(settings.processed_data_path / "predictions.parquet"),
    }
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
