from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from hc_analytics.modeling.constants import (
    CATEGORICAL_COLUMNS,
    FEATURE_COLUMNS,
    MODEL_FAMILIES,
    MODEL_SCHEMA_VERSION,
    PRIMARY_MODEL_FAMILY,
    RiskTarget,
    TARGET_SHORT_NAMES,
)


def allow_logistic_fallback() -> bool:
    import os

    from hc_analytics.config import get_settings

    if os.getenv("HC_ALLOW_LOGISTIC_FALLBACK", "").strip().lower() in {"1", "true", "yes"}:
        return True
    try:
        return bool(get_settings().allow_logistic_fallback)
    except Exception:
        return False


def xgboost_available() -> bool:
    try:
        from xgboost import XGBClassifier  # noqa: F401
    except Exception:
        return False
    return True


def require_primary_model_family() -> str:
    if xgboost_available():
        return PRIMARY_MODEL_FAMILY
    if allow_logistic_fallback():
        return "logistic_regression"
    raise RuntimeError(
        "XGBoost is required for the frozen study model family but is unavailable. "
        "On macOS install OpenMP with `brew install libomp`, reinstall xgboost, then retrain. "
        "For local prototyping only, set HC_ALLOW_LOGISTIC_FALLBACK=true."
    )


@dataclass
class ModelMetrics:
    roc_auc: Optional[float]
    average_precision: Optional[float]
    brier_score: Optional[float]
    positive_rate: float
    row_count: int


def _build_preprocessor() -> ColumnTransformer:
    numeric_columns = [column for column in FEATURE_COLUMNS if column not in CATEGORICAL_COLUMNS]
    return ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_columns,
            ),
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                CATEGORICAL_COLUMNS,
            ),
        ]
    )


def _build_estimator(family: str):
    if family == "logistic_regression":
        return LogisticRegression(max_iter=3000, class_weight="balanced")
    if family == "xgboost":
        if not xgboost_available():
            raise RuntimeError(
                "XGBoost is unavailable. On macOS install OpenMP with `brew install libomp`."
            )
        from xgboost import XGBClassifier

        return XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=42,
        )
    raise ValueError(f"Unsupported model family: {family}")


def build_model_pipeline(family: str) -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocessor", _build_preprocessor()),
            ("classifier", _build_estimator(family)),
        ]
    )


def _safe_metric(metric_fn, y_true: np.ndarray, y_score: np.ndarray) -> Optional[float]:
    if len(np.unique(y_true)) < 2:
        return None
    return float(metric_fn(y_true, y_score))


def evaluate_predictions(y_true: pd.Series, y_prob: np.ndarray) -> ModelMetrics:
    labels = y_true.astype(int).to_numpy()
    return ModelMetrics(
        roc_auc=_safe_metric(roc_auc_score, labels, y_prob),
        average_precision=_safe_metric(average_precision_score, labels, y_prob),
        brier_score=float(brier_score_loss(labels, y_prob)),
        positive_rate=float(labels.mean()),
        row_count=len(labels),
    )


def train_model(
    *,
    family: str,
    target: RiskTarget,
    train_x: pd.DataFrame,
    train_y: pd.Series,
    test_x: pd.DataFrame,
    test_y: pd.Series,
    calibration_x: Optional[pd.DataFrame] = None,
    calibration_y: Optional[pd.Series] = None,
    calibrate: bool = True,
) -> tuple[object, Dict[str, object]]:
    pipeline = build_model_pipeline(family)
    pipeline.fit(train_x[FEATURE_COLUMNS], train_y.astype(int))

    calibrated = False
    model: object = pipeline
    if (
        calibrate
        and calibration_x is not None
        and calibration_y is not None
        and len(calibration_x) > 0
        and calibration_y.nunique() > 1
    ):
        from sklearn.calibration import CalibratedClassifierCV
        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=".*cv='prefit'.*",
                category=UserWarning,
            )
            calibrator = CalibratedClassifierCV(pipeline, method="isotonic", cv="prefit")
            calibrator.fit(calibration_x[FEATURE_COLUMNS], calibration_y.astype(int))
        model = calibrator
        calibrated = True

    train_prob = model.predict_proba(train_x[FEATURE_COLUMNS])[:, 1]
    test_prob = model.predict_proba(test_x[FEATURE_COLUMNS])[:, 1]
    metrics: Dict[str, object] = {
        "train": asdict(evaluate_predictions(train_y, train_prob)),
        "test": asdict(evaluate_predictions(test_y, test_prob)),
        "calibrated": calibrated,
        "calibration_method": "isotonic" if calibrated else None,
    }
    if calibration_x is not None and calibration_y is not None and len(calibration_x) > 0:
        calib_prob = model.predict_proba(calibration_x[FEATURE_COLUMNS])[:, 1]
        metrics["calibration"] = asdict(evaluate_predictions(calibration_y, calib_prob))
    return model, metrics


def model_artifact_path(models_dir: Path, target: RiskTarget, family: str) -> Path:
    short = TARGET_SHORT_NAMES[target]
    return models_dir / short / f"{family}.joblib"


def metadata_path(models_dir: Path, target: RiskTarget) -> Path:
    short = TARGET_SHORT_NAMES[target]
    return models_dir / short / "metadata.json"


def save_model_artifact(
    *,
    pipeline: object,
    models_dir: Path,
    target: RiskTarget,
    family: str,
    metrics: Dict[str, object],
    split_spec: Dict[str, object],
    feature_columns: List[str],
    git_commit: Optional[str],
    label_definition: Dict[str, object],
) -> Path:
    target_dir = models_dir / TARGET_SHORT_NAMES[target]
    target_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = model_artifact_path(models_dir, target, family)
    joblib.dump(pipeline, artifact_path)

    metadata = {
        "schema_version": MODEL_SCHEMA_VERSION,
        "target": target.value,
        "target_short": TARGET_SHORT_NAMES[target],
        "family": family,
        "primary_for_dashboard": family == PRIMARY_MODEL_FAMILY,
        "feature_columns": feature_columns,
        "categorical_columns": CATEGORICAL_COLUMNS,
        "metrics": metrics,
        "split": split_spec,
        "label_definition": label_definition,
        "artifact_path": str(artifact_path),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
    }
    meta_path = metadata_path(models_dir, target)
    existing: Dict[str, object] = {}
    if meta_path.exists():
        existing = json.loads(meta_path.read_text(encoding="utf-8"))
    models = existing.get("models", {})
    if not isinstance(models, dict):
        models = {}
    models[family] = metadata
    payload = {
        "schema_version": MODEL_SCHEMA_VERSION,
        "target": target.value,
        "target_short": TARGET_SHORT_NAMES[target],
        "feature_columns": feature_columns,
        "split": split_spec,
        "label_definition": label_definition,
        "models": models,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
    }
    meta_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return artifact_path


def load_model_artifact(models_dir: Path, target: RiskTarget, family: str) -> object:
    path = model_artifact_path(models_dir, target, family)
    if not path.exists():
        raise FileNotFoundError(f"Missing model artifact: {path}")
    return joblib.load(path)


def unwrap_model_for_shap(model: object) -> object:
    """Return the base estimator/pipeline for SHAP (skip isotonic calibrator wrapper)."""
    if hasattr(model, "calibrated_classifiers_") and hasattr(model, "estimator"):
        return model.estimator
    if hasattr(model, "estimator") and not hasattr(model, "named_steps"):
        inner = model.estimator
        if hasattr(inner, "named_steps") or hasattr(inner, "predict_proba"):
            return inner
    return model
