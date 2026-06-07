from hc_analytics.language.grounding import (
    FALLBACK_INSUFFICIENT_EVIDENCE,
    EvidenceClaim,
    GroundedExplanation,
)


def test_grounded_explanation_requires_evidence_fields() -> None:
    claim = EvidenceClaim(
        statement="Recent hospital use elevated risk.",
        source_fields=["inpatient_claims_12m", "shap:inpatient_claims_12m"],
        shap_feature="inpatient_claims_12m",
        shap_value=0.27,
    )
    explanation = GroundedExplanation(beneficiary_id="BENE001", claims=[claim])
    assert explanation.fallback is None
    assert len(explanation.claims) == 1


def test_insufficient_evidence_fallback() -> None:
    explanation = GroundedExplanation.insufficient_evidence(beneficiary_id="BENE002")
    assert explanation.fallback == FALLBACK_INSUFFICIENT_EVIDENCE
    assert explanation.claims == []
