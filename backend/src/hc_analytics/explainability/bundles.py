from __future__ import annotations

from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field

from hc_analytics.language.grounding import EvidenceClaim, GroundedExplanation


class LocalContributor(BaseModel):
    feature: str
    shap_value: float
    direction: str
    rank: int
    feature_value: Optional[Union[float, str, int]] = None


class TargetExplanation(BaseModel):
    target: str
    target_short: str
    risk_score: Optional[float] = None
    top_contributors: List[LocalContributor] = Field(default_factory=list)
    stability_badge: str
    stability_score: float


class EvidenceBundle(BaseModel):
    schema_version: str
    bene_id: str
    analytic_year: int
    model_family: str
    targets: List[TargetExplanation] = Field(default_factory=list)
    grounded: GroundedExplanation


def _statement_for_contributor(target_short: str, contributor: LocalContributor) -> str:
    direction = "increased" if contributor.direction == "increases_risk" else "decreased"
    return (
        f"{contributor.feature} {direction} predicted {target_short.replace('_', ' ')} risk "
        f"(SHAP {contributor.shap_value:+.3f})."
    )


def build_grounded_explanation(
    *,
    bene_id: str,
    target_explanations: List[TargetExplanation],
    max_claims_per_target: int = 3,
) -> GroundedExplanation:
    claims: List[EvidenceClaim] = []
    for explanation in target_explanations:
        for contributor in explanation.top_contributors[:max_claims_per_target]:
            claims.append(
                EvidenceClaim(
                    statement=_statement_for_contributor(explanation.target_short, contributor),
                    source_fields=[contributor.feature],
                    shap_feature=contributor.feature,
                    shap_value=contributor.shap_value,
                )
            )

    if not claims:
        return GroundedExplanation.insufficient_evidence(beneficiary_id=bene_id)
    return GroundedExplanation(beneficiary_id=bene_id, claims=claims)


def build_evidence_bundle(
    *,
    schema_version: str,
    bene_id: str,
    analytic_year: int,
    model_family: str,
    target_explanations: List[TargetExplanation],
) -> EvidenceBundle:
    grounded = build_grounded_explanation(
        bene_id=bene_id,
        target_explanations=target_explanations,
    )
    return EvidenceBundle(
        schema_version=schema_version,
        bene_id=bene_id,
        analytic_year=analytic_year,
        model_family=model_family,
        targets=target_explanations,
        grounded=grounded,
    )


def bundle_to_dict(bundle: EvidenceBundle) -> Dict[str, object]:
    return bundle.model_dump()
