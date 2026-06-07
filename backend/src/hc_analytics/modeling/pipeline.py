"""Model training pipeline (Phase 3)."""

from enum import Enum


class RiskTarget(str, Enum):
    HOSPITALIZATION = "hospitalization_risk"
    HIGH_UTILIZATION = "high_utilization_risk"
    ELEVATED_COST = "elevated_cost_risk"


def run_training(target: RiskTarget = RiskTarget.HOSPITALIZATION) -> None:
    raise NotImplementedError(f"Training for {target.value} not yet implemented.")
