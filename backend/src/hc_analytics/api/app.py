from __future__ import annotations

from typing import Dict, Union

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hc_analytics import __version__
from hc_analytics.api.routes import predictions
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


@app.get("/health")
def health() -> Dict[str, str]:
    return {
        "status": "ok",
        "version": __version__,
        "condition": settings.experimental_condition.value,
        "study_id": settings.study_id,
    }


@app.get("/api/meta")
def meta() -> Dict[str, Union[str, bool]]:
    processed = settings.processed_data_path
    data_ready = processed.exists() and any(processed.iterdir()) if processed.exists() else False
    predictions_ready = (processed / "predictions.parquet").exists()
    models_ready = (settings.artifacts_path / "models").exists() and any(
        (settings.artifacts_path / "models").rglob("*.joblib")
    ) if (settings.artifacts_path / "models").exists() else False
    return {
        "prototype_phase": "3",
        "experimental_condition": settings.experimental_condition.value,
        "data_ready": data_ready,
        "models_ready": models_ready,
        "predictions_ready": predictions_ready,
        "instrumentation_enabled": settings.log_events,
    }
