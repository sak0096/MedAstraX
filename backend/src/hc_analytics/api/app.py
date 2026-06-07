from __future__ import annotations

from typing import Dict, Union

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hc_analytics import __version__
from hc_analytics.api.routes import beneficiaries, cohort, explanations, language, predictions
from hc_analytics.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Healthcare Analytics XAI Prototype",
    description="Research prototype for provider-facing dashboard explainability studies.",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predictions.router)
app.include_router(cohort.router)
app.include_router(beneficiaries.router)
app.include_router(explanations.router)
app.include_router(language.router)


@app.get("/health")
def health() -> Dict[str, str]:
    runtime_settings = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "condition": runtime_settings.experimental_condition.value,
        "study_id": runtime_settings.study_id,
    }


@app.get("/api/meta")
def meta() -> Dict[str, Union[str, bool]]:
    runtime_settings = get_settings()
    processed = runtime_settings.processed_data_path
    data_ready = processed.exists() and any(processed.iterdir()) if processed.exists() else False
    predictions_ready = (processed / "predictions.parquet").exists()
    models_dir = runtime_settings.artifacts_path / "models"
    models_ready = models_dir.exists() and any(models_dir.rglob("*.joblib")) if models_dir.exists() else False
    explanations_ready = (runtime_settings.artifacts_path / "explanations" / "manifest.json").exists()
    language_ready = explanations_ready
    llm_configured = bool(
        runtime_settings.llm_provider and runtime_settings.llm_api_key and runtime_settings.llm_model
    )
    return {
        "prototype_phase": "7",
        "experimental_condition": runtime_settings.experimental_condition.value,
        "data_ready": data_ready,
        "models_ready": models_ready,
        "predictions_ready": predictions_ready,
        "explanations_ready": explanations_ready,
        "language_ready": language_ready,
        "llm_configured": llm_configured,
        "instrumentation_enabled": runtime_settings.log_events,
    }
