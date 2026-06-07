from __future__ import annotations

from typing import Dict, List, Optional

from hc_analytics.explainability.bundles import EvidenceBundle, TargetExplanation
from hc_analytics.language.grounding import FALLBACK_INSUFFICIENT_EVIDENCE, GroundedExplanation
from hc_analytics.language.models import GroundedSummaryResponse


def _feature_label(feature: str) -> str:
    return feature.replace("_", " ")


def _target_sentence(target: TargetExplanation) -> str:
    risk_text = (
        f"{target.target_short.replace('_', ' ')} risk is {target.risk_score:.0%}"
        if target.risk_score is not None
        else f"{target.target_short.replace('_', ' ')} risk is unavailable"
    )
    if not target.top_contributors:
        return risk_text + "."

    contributor_bits: List[str] = []
    for contributor in target.top_contributors[:3]:
        direction = "raised" if contributor.direction == "increases_risk" else "lowered"
        value_text = ""
        if contributor.feature_value is not None:
            value_text = f" (value: {contributor.feature_value})"
        contributor_bits.append(
            f"{_feature_label(contributor.feature)}{value_text} {direction} risk "
            f"(SHAP {contributor.shap_value:+.3f})"
        )
    return f"{risk_text}, primarily driven by {', '.join(contributor_bits)}."


def build_template_narrative(bundle: EvidenceBundle) -> str:
    grounded = bundle.grounded
    if grounded.fallback == FALLBACK_INSUFFICIENT_EVIDENCE:
        return "Insufficient evidence to produce a grounded summary for this beneficiary-year."

    intro = (
        f"Beneficiary {bundle.bene_id} ({bundle.analytic_year}) — "
        f"model family {bundle.model_family}."
    )
    target_sentences = [_target_sentence(target) for target in bundle.targets]
    stability_bits = [
        f"{target.target_short} explanation stability: {target.stability_badge}"
        for target in bundle.targets
    ]
    return " ".join([intro, *target_sentences, " ".join(stability_bits)])


def build_grounded_summary(
    bundle: EvidenceBundle,
    *,
    provider: str = "template",
) -> GroundedSummaryResponse:
    grounded = bundle.grounded
    if grounded.fallback == FALLBACK_INSUFFICIENT_EVIDENCE:
        return GroundedSummaryResponse(
            bene_id=bundle.bene_id,
            analytic_year=bundle.analytic_year,
            narrative="Insufficient evidence to produce a grounded summary for this beneficiary-year.",
            provider=provider,
            grounded=grounded,
        )

    narrative = build_template_narrative(bundle)
    target_summaries: List[Dict[str, object]] = []
    for target in bundle.targets:
        target_summaries.append(
            {
                "target": target.target,
                "target_short": target.target_short,
                "risk_score": target.risk_score,
                "stability_badge": target.stability_badge,
                "top_features": [item.feature for item in target.top_contributors[:3]],
            }
        )

    return GroundedSummaryResponse(
        bene_id=bundle.bene_id,
        analytic_year=bundle.analytic_year,
        narrative=narrative,
        provider=provider,
        grounded=grounded,
        target_summaries=target_summaries,
    )


def cohort_query_narrative(
    *,
    natural_language: str,
    row_count: int,
    parameters: Dict[str, object],
) -> GroundedExplanation:
    from hc_analytics.language.grounding import EvidenceClaim

    sort_by = str(parameters.get("sort_by", "hospitalization_risk"))
    return GroundedExplanation(
        claims=[
            EvidenceClaim(
                statement=(
                    f"Query '{natural_language}' returned {row_count} beneficiary-year rows "
                    f"sorted by {sort_by}."
                ),
                source_fields=["feature_store", "predictions", sort_by],
            )
        ],
    )
