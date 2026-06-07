from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
import shap
from sklearn.pipeline import Pipeline

from hc_analytics.modeling.constants import CATEGORICAL_COLUMNS, FEATURE_COLUMNS


def _split_pipeline(pipeline: Pipeline) -> tuple[object, object]:
    return pipeline.named_steps["preprocessor"], pipeline.named_steps["classifier"]


def transform_features(pipeline: Pipeline, frame: pd.DataFrame) -> tuple[np.ndarray, Sequence[str]]:
    preprocessor, _ = _split_pipeline(pipeline)
    matrix = preprocessor.transform(frame[FEATURE_COLUMNS])
    names = preprocessor.get_feature_names_out()
    return matrix, names


def aggregate_shap_to_features(
    transformed_names: Sequence[str],
    shap_row: np.ndarray,
) -> Dict[str, float]:
    aggregated = {column: 0.0 for column in FEATURE_COLUMNS}
    for index, name in enumerate(transformed_names):
        value = float(shap_row[index])
        if name.startswith("numeric__"):
            feature = name.removeprefix("numeric__")
            if feature in aggregated:
                aggregated[feature] = value
            continue
        if name.startswith("categorical__"):
            suffix = name.removeprefix("categorical__")
            for column in CATEGORICAL_COLUMNS:
                if suffix == column or suffix.startswith(f"{column}_"):
                    aggregated[column] += value
                    break
    return aggregated


def compute_shap_matrix(
    pipeline: Pipeline,
    frame: pd.DataFrame,
    *,
    background: pd.DataFrame,
) -> tuple[np.ndarray, Sequence[str]]:
    preprocessor, classifier = _split_pipeline(pipeline)
    feature_matrix = preprocessor.transform(frame[FEATURE_COLUMNS])
    background_matrix = preprocessor.transform(background[FEATURE_COLUMNS])
    names = preprocessor.get_feature_names_out()

    if hasattr(classifier, "coef_"):
        explainer = shap.LinearExplainer(classifier, background_matrix, feature_names=names)
    else:
        explainer = shap.TreeExplainer(classifier)
    shap_values = explainer.shap_values(feature_matrix)

    if isinstance(shap_values, list):
        shap_values = shap_values[1]
    return np.asarray(shap_values), names


def top_contributors(
    feature_shap: Dict[str, float],
    *,
    top_k: int,
    feature_values: Dict[str, object] | None = None,
) -> List[Dict[str, object]]:
    ranked = sorted(feature_shap.items(), key=lambda item: abs(item[1]), reverse=True)[:top_k]
    rows: List[Dict[str, object]] = []
    for rank, (feature, value) in enumerate(ranked, start=1):
        row: Dict[str, object] = {
            "feature": feature,
            "shap_value": round(float(value), 6),
            "direction": "increases_risk" if value > 0 else "decreases_risk",
            "rank": rank,
        }
        if feature_values and feature in feature_values:
            row["feature_value"] = feature_values[feature]
        rows.append(row)
    return rows


def global_importance_from_shap(
    shap_matrix: np.ndarray,
    transformed_names: Sequence[str],
) -> List[Dict[str, object]]:
    mean_abs = np.mean(np.abs(shap_matrix), axis=0)
    aggregated = aggregate_shap_to_features(
        transformed_names,
        mean_abs,
    )
    ranked = sorted(aggregated.items(), key=lambda item: item[1], reverse=True)
    return [
        {
            "feature": feature,
            "mean_abs_shap": round(float(value), 6),
            "rank": rank,
        }
        for rank, (feature, value) in enumerate(ranked, start=1)
    ]


def select_background(
    frame: pd.DataFrame,
    *,
    size: int,
    random_state: int = 42,
) -> pd.DataFrame:
    if len(frame) <= size:
        return frame.copy()
    return frame.sample(n=size, random_state=random_state).reset_index(drop=True)
