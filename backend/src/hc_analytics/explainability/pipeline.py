"""Explanation generation pipeline (Phase 4)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from hc_analytics.config import Settings, get_settings
from hc_analytics.explainability.bundles import (
    EvidenceBundle,
    TargetExplanation,
    build_evidence_bundle,
)
from hc_analytics.explainability.constants import (
    DEFAULT_BACKGROUND_SIZE,
    DEFAULT_TOP_K,
    EXPLANATION_SCHEMA_VERSION,
)
from hc_analytics.explainability.shap_engine import (
    aggregate_shap_to_features,
    compute_shap_matrix,
    global_importance_from_shap,
    select_background,
    top_contributors,
)
from hc_analytics.explainability.stability import attach_margin_stability
from hc_analytics.ingestion.io import git_commit_hash
from hc_analytics.modeling.constants import (
    FEATURE_COLUMNS,
    PRIMARY_MODEL_FAMILY,
    RiskTarget,
    TARGET_SHORT_NAMES,
    risk_score_column,
)
from hc_analytics.modeling.trainers import load_model_artifact, xgboost_available

RowKey = Tuple[str, int]


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


def _load_predictions(processed_dir: Path) -> pd.DataFrame:
    path = processed_dir / "predictions.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing predictions at {path}. Run `python -m hc_analytics.modeling` first."
        )
    return pd.read_parquet(path)


def _explanations_dir(settings: Settings) -> Path:
    return settings.artifacts_path / "explanations"


def _bundle_path(explanations_dir: Path, bene_id: str, analytic_year: int) -> Path:
    return explanations_dir / "bundles" / f"{bene_id}_{analytic_year}.json"


def _global_path(explanations_dir: Path, target: RiskTarget) -> Path:
    return explanations_dir / "global" / f"{TARGET_SHORT_NAMES[target]}.json"


def load_cached_bundle(
    bene_id: str,
    analytic_year: int,
    settings: Optional[Settings] = None,
) -> Optional[EvidenceBundle]:
    settings = settings or get_settings()
    path = _bundle_path(_explanations_dir(settings), bene_id, analytic_year)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return EvidenceBundle.model_validate(payload)


def load_global_importance(
    target: RiskTarget,
    settings: Optional[Settings] = None,
) -> Optional[Dict[str, object]]:
    settings = settings or get_settings()
    path = _global_path(_explanations_dir(settings), target)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _risk_score_for_row(
    predictions: pd.DataFrame,
    *,
    bene_id: str,
    analytic_year: int,
    target: RiskTarget,
) -> Optional[float]:
    row = predictions.loc[
        (predictions["bene_id"] == bene_id) & (predictions["analytic_year"] == analytic_year)
    ]
    if row.empty:
        return None
    column = risk_score_column(target)
    value = row.iloc[0].get(column)
    if pd.isna(value):
        return None
    return float(value)


def _build_target_explanation(
    *,
    target: RiskTarget,
    row: pd.Series,
    shap_row: Dict[str, float],
    risk_score: Optional[float],
    top_k: int,
) -> TargetExplanation:
    from hc_analytics.explainability.bundles import LocalContributor

    feature_values = {column: row[column] for column in FEATURE_COLUMNS}
    contributors = top_contributors(shap_row, top_k=top_k, feature_values=feature_values)
    badge, score = attach_margin_stability(contributors)
    return TargetExplanation(
        target=target.value,
        target_short=TARGET_SHORT_NAMES[target],
        risk_score=risk_score,
        top_contributors=[LocalContributor(**item) for item in contributors],
        stability_badge=badge,
        stability_score=round(score, 4),
    )


def _write_global_importance(
    *,
    explanations_dir: Path,
    target: RiskTarget,
    model_family: str,
    importance: List[Dict[str, object]],
    git_commit: Optional[str],
) -> Path:
    global_dir = explanations_dir / "global"
    global_dir.mkdir(parents=True, exist_ok=True)
    path = _global_path(explanations_dir, target)
    payload = {
        "schema_version": EXPLANATION_SCHEMA_VERSION,
        "target": target.value,
        "target_short": TARGET_SHORT_NAMES[target],
        "model_family": model_family,
        "importance": importance,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _write_bundle(bundle: EvidenceBundle, explanations_dir: Path) -> Path:
    bundle_dir = explanations_dir / "bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    path = _bundle_path(explanations_dir, bundle.bene_id, bundle.analytic_year)
    path.write_text(json.dumps(bundle.model_dump(), indent=2), encoding="utf-8")
    return path


def _write_local_topk_parquet(rows: List[Dict[str, object]], explanations_dir: Path) -> Path:
    path = explanations_dir / "local_topk.parquet"
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


def _write_manifest(
    *,
    explanations_dir: Path,
    model_family: str,
    top_k: int,
    row_count: int,
    git_commit: Optional[str],
) -> Path:
    path = explanations_dir / "manifest.json"
    payload = {
        "schema_version": EXPLANATION_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "model_family": model_family,
        "top_k": top_k,
        "targets": [target.value for target in RiskTarget],
        "row_count": row_count,
        "global_dir": str(explanations_dir / "global"),
        "bundles_dir": str(explanations_dir / "bundles"),
        "local_topk": str(explanations_dir / "local_topk.parquet"),
        "stability_method": "top_feature_margin",
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def run_explainability(
    settings: Optional[Settings] = None,
    *,
    top_k: int = DEFAULT_TOP_K,
    background_size: int = DEFAULT_BACKGROUND_SIZE,
    max_rows: Optional[int] = None,
) -> Dict[str, object]:
    settings = settings or get_settings()
    features = _load_feature_store(settings.processed_data_path)
    predictions = _load_predictions(settings.processed_data_path)
    explanations_dir = _explanations_dir(settings)
    explanations_dir.mkdir(parents=True, exist_ok=True)

    model_family = _primary_model_family()
    models_dir = settings.artifacts_path / "models"
    background = select_background(features, size=background_size)
    git_commit = git_commit_hash(settings.repo_root)

    work_frame = features.reset_index(drop=True)
    if max_rows is not None:
        work_frame = work_frame.head(max_rows).copy()

    per_row_targets: Dict[RowKey, List[TargetExplanation]] = {}
    local_rows: List[Dict[str, object]] = []

    for target in RiskTarget:
        pipeline = load_model_artifact(models_dir, target, model_family)
        shap_matrix, transformed_names = compute_shap_matrix(
            pipeline,
            work_frame,
            background=background,
        )
        importance = global_importance_from_shap(shap_matrix, transformed_names)
        _write_global_importance(
            explanations_dir=explanations_dir,
            target=target,
            model_family=model_family,
            importance=importance,
            git_commit=git_commit,
        )

        for index, row in work_frame.iterrows():
            bene_id = str(row["bene_id"])
            analytic_year = int(row["analytic_year"])
            key = (bene_id, analytic_year)
            aggregated = aggregate_shap_to_features(transformed_names, shap_matrix[index])
            target_explanation = _build_target_explanation(
                target=target,
                row=row,
                shap_row=aggregated,
                risk_score=_risk_score_for_row(
                    predictions,
                    bene_id=bene_id,
                    analytic_year=analytic_year,
                    target=target,
                ),
                top_k=top_k,
            )
            per_row_targets.setdefault(key, []).append(target_explanation)
            for contributor in target_explanation.top_contributors:
                local_rows.append(
                    {
                        "bene_id": bene_id,
                        "analytic_year": analytic_year,
                        "target": target.value,
                        "target_short": TARGET_SHORT_NAMES[target],
                        "feature": contributor.feature,
                        "shap_value": contributor.shap_value,
                        "direction": contributor.direction,
                        "rank": contributor.rank,
                        "stability_badge": target_explanation.stability_badge,
                        "stability_score": target_explanation.stability_score,
                        "model_family": model_family,
                    }
                )

    bundle_paths: List[str] = []
    for (bene_id, analytic_year), target_explanations in per_row_targets.items():
        bundle = build_evidence_bundle(
            schema_version=EXPLANATION_SCHEMA_VERSION,
            bene_id=bene_id,
            analytic_year=analytic_year,
            model_family=model_family,
            target_explanations=target_explanations,
        )
        bundle_paths.append(str(_write_bundle(bundle, explanations_dir)))

    local_path = _write_local_topk_parquet(local_rows, explanations_dir)
    manifest_path = _write_manifest(
        explanations_dir=explanations_dir,
        model_family=model_family,
        top_k=top_k,
        row_count=len(work_frame),
        git_commit=git_commit,
    )

    return {
        "explanations_dir": str(explanations_dir),
        "manifest": str(manifest_path),
        "local_topk": str(local_path),
        "bundle_count": len(bundle_paths),
        "row_count": len(work_frame),
        "model_family": model_family,
    }
