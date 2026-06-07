from __future__ import annotations

from collections import Counter
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from hc_analytics.explainability.constants import (
    STABILITY_GREEN_THRESHOLD,
    STABILITY_MARGIN_GREEN,
    STABILITY_MARGIN_YELLOW,
    STABILITY_YELLOW_THRESHOLD,
)
from hc_analytics.explainability.shap_engine import (
    aggregate_shap_to_features,
    compute_shap_matrix,
    top_contributors,
)
from hc_analytics.modeling.constants import FEATURE_COLUMNS


def badge_from_score(score: float) -> str:
    if score >= STABILITY_GREEN_THRESHOLD:
        return "green"
    if score >= STABILITY_YELLOW_THRESHOLD:
        return "yellow"
    return "red"


def stability_from_margin(top_shap_values: Sequence[float]) -> Tuple[str, float]:
    if not top_shap_values:
        return "red", 0.0
    if len(top_shap_values) == 1:
        return "yellow", 0.5
    first = abs(float(top_shap_values[0]))
    second = abs(float(top_shap_values[1]))
    score = (first - second) / (first + 1e-9)
    if score >= STABILITY_MARGIN_GREEN:
        return "green", min(1.0, score)
    if score >= STABILITY_MARGIN_YELLOW:
        return "yellow", score
    return "red", score


def bootstrap_top_feature_stability(
    pipeline: Pipeline,
    row: pd.Series,
    *,
    background: pd.DataFrame,
    bootstrap_iterations: int,
    random_state: int = 42,
) -> Tuple[str, float, str]:
    rng = np.random.default_rng(random_state)
    top_features: List[str] = []
    row_frame = pd.DataFrame([row[FEATURE_COLUMNS]])

    for _ in range(bootstrap_iterations):
        sample = background.sample(
            n=len(background),
            replace=True,
            random_state=int(rng.integers(0, 1_000_000)),
        )
        shap_matrix, names = compute_shap_matrix(pipeline, row_frame, background=sample)
        aggregated = aggregate_shap_to_features(names, shap_matrix[0])
        top = top_contributors(aggregated, top_k=1)
        if top:
            top_features.append(str(top[0]["feature"]))

    if not top_features:
        return "red", 0.0, ""

    counts = Counter(top_features)
    top_feature, agreement = counts.most_common(1)[0]
    score = agreement / bootstrap_iterations
    return badge_from_score(score), score, top_feature


def attach_margin_stability(rows: List[Dict[str, object]]) -> Tuple[str, float]:
    shap_values = [float(row["shap_value"]) for row in rows]
    return stability_from_margin(shap_values)
