from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Union

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from hc_analytics import __version__
from hc_analytics.api.routes import (
    admin,
    beneficiaries,
    cohort,
    explanations,
    instrumentation,
    integration,
    language,
    predictions,
    study,
)
from hc_analytics.config import get_settings
from hc_analytics.release import release_blockers
from hc_analytics.study.context import StudyRequestContext, get_study_context

settings = get_settings()

app = FastAPI(
    title="Healthcare Analytics XAI Prototype",
    description="Research prototype for provider-facing dashboard explainability studies.",
    version=__version__,
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None if settings.environment == "production" else "/redoc",
    openapi_url=None if settings.environment == "production" else "/openapi.json",
)

allowed_origins = settings.allowed_origins()
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(predictions.router)
app.include_router(cohort.router)
app.include_router(beneficiaries.router)
app.include_router(explanations.router)
app.include_router(language.router)
app.include_router(study.router)
app.include_router(instrumentation.router)
app.include_router(integration.router)
app.include_router(admin.router)


def _adjudication_pending(runtime) -> bool:
    path = runtime.repo_root / "study" / "frozen_summaries.json"
    if not path.exists():
        return True
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True
    return bool(payload.get("human_adjudication_required", True))


def _database_ready(runtime) -> tuple[bool, str]:
    if runtime.storage_backend == "sqlite":
        if runtime.environment == "production":
            return False, "PostgreSQL is not configured."
        return True, "sqlite-local"
    try:
        from hc_analytics.persistence.repository import StudyRepository

        StudyRepository.from_settings(runtime).ensure_schema()
    except Exception:
        return False, "PostgreSQL is unavailable."
    return True, "postgres"


@app.get("/health/live")
def health_live() -> Dict[str, str]:
    return {"status": "live", "version": __version__}


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    runtime = get_settings()
    database_ok, database_state = _database_ready(runtime)
    launch_blockers = list(runtime.production_blockers())
    if _adjudication_pending(runtime):
        launch_blockers.append("Human adjudication of frozen summaries is pending.")
    launch_blockers.extend(release_blockers(runtime))
    if not runtime.recruitment_enabled:
        launch_blockers.append("Recruitment is disabled.")
    infrastructure = list(runtime.infrastructure_blockers())
    if not database_ok:
        infrastructure.append(database_state)
    body = {
        "status": "ready" if database_ok and not infrastructure else "not_ready",
        "version": __version__,
        "storage_backend": runtime.storage_backend,
        "participant_launch_allowed": database_ok and not launch_blockers and not infrastructure,
        "recruitment_enabled": runtime.recruitment_enabled,
    }
    if not database_ok or infrastructure:
        body["reasons"] = infrastructure
        return JSONResponse(status_code=503, content=body)
    if launch_blockers:
        body["launch_blockers"] = launch_blockers
    return JSONResponse(status_code=200, content=body)


@app.get("/api/meta")
def meta(
    study_ctx: StudyRequestContext = Depends(get_study_context),
) -> Dict[str, Union[str, bool, None]]:
    runtime_settings = get_settings()
    processed = runtime_settings.processed_data_path
    data_ready = processed.exists() and any(processed.iterdir()) if processed.exists() else False
    predictions_ready = (processed / "predictions.parquet").exists()
    models_dir = runtime_settings.artifacts_path / "models"
    models_ready = (
        models_dir.exists() and any(models_dir.rglob("*.joblib")) if models_dir.exists() else False
    )
    explanations_ready = (
        runtime_settings.artifacts_path / "explanations" / "manifest.json"
    ).exists()
    language_ready = explanations_ready
    llm_configured = bool(
        runtime_settings.llm_provider
        and runtime_settings.llm_api_key
        and runtime_settings.llm_model
    )
    return {
        "prototype_phase": "8",
        "experimental_condition": study_ctx.experimental_condition.value,
        "assigned_study": study_ctx.study,
        "data_ready": data_ready,
        "models_ready": models_ready,
        "predictions_ready": predictions_ready,
        "explanations_ready": explanations_ready,
        "language_ready": language_ready,
        "llm_configured": llm_configured and not runtime_settings.study_mode,
        "instrumentation_enabled": runtime_settings.log_events,
        "study_mode_enabled": runtime_settings.study_mode,
        "participant_launch_allowed": runtime_settings.recruitment_enabled
        and not runtime_settings.production_blockers()
        and not _adjudication_pending(runtime_settings)
        and not release_blockers(runtime_settings),
    }


def _frontend_file(dist: Path, full_path: str) -> Path:
    root = dist.resolve()
    candidate = (root / full_path).resolve()
    if not candidate.is_relative_to(root):
        raise HTTPException(status_code=404, detail="Not found.")
    return candidate


@app.get("/{full_path:path}")
def frontend_or_not_found(full_path: str, request: Request) -> FileResponse:
    if full_path == "api" or full_path.startswith("api/") or full_path.startswith("health"):
        return JSONResponse(status_code=404, content={"detail": "Not found."})  # type: ignore[return-value]
    runtime = get_settings()
    dist = runtime.frontend_dist_path
    if not dist.exists():
        raise HTTPException(status_code=404, detail="Not found.")
    candidate = _frontend_file(dist, full_path)
    if candidate.is_file():
        return FileResponse(candidate)
    index = _frontend_file(dist, "index.html")
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not found.")
