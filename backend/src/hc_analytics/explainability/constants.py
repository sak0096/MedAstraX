from __future__ import annotations

EXPLANATION_SCHEMA_VERSION = "1.0"
DEFAULT_TOP_K = 5
DEFAULT_BACKGROUND_SIZE = 200
DEFAULT_BOOTSTRAP_ITERATIONS = 5

STABILITY_GREEN_THRESHOLD = 0.8
STABILITY_YELLOW_THRESHOLD = 0.5

STABILITY_MARGIN_GREEN = 0.4
STABILITY_MARGIN_YELLOW = 0.15

# Demographic and access-related features surfaced with fairness cues in the XAI UI.
EQUITY_RELEVANT_FEATURES = ("age", "sex", "race", "state_code", "esrd_ind")
