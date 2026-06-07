from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from hc_analytics.config import get_settings
from hc_analytics.instrumentation.context import build_version_context
from hc_analytics.instrumentation.events import EventType, StudyEvent, log_event
from hc_analytics.instrumentation.export import build_session_export, write_session_export
from hc_analytics.instrumentation.store import list_sessions

router = APIRouter(prefix="/api/instrumentation", tags=["instrumentation"])


class SessionExportRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=128)


@router.get("/meta")
def instrumentation_meta() -> Dict[str, Any]:
    settings = get_settings()
    sessions = list_sessions(settings=settings)
    return {
        "instrumentation_enabled": settings.log_events,
        "session_count": len(sessions),
        "version_context": build_version_context(settings),
        "event_types": [item.value for item in EventType],
    }


@router.post("/events")
def record_event(event: StudyEvent) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.log_events:
        return {"stored": False, "event": event.model_dump(mode="json")}
    record = log_event(event)
    return {"stored": True, "event": record}


@router.get("/sessions")
def sessions() -> Dict[str, List[Dict[str, object]]]:
    return {"sessions": list_sessions(settings=get_settings())}


@router.post("/export")
def export_session(request: SessionExportRequest) -> Dict[str, Any]:
    settings = get_settings()
    try:
        bundle = build_session_export(request.session_id, settings=settings)
        export_path = write_session_export(request.session_id, settings=settings)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {
        "session_id": request.session_id,
        "export_path": str(export_path),
        "event_count": bundle["event_count"],
        "bundle": bundle,
    }


@router.get("/export/{session_id}/download")
def download_session_export(session_id: str) -> FileResponse:
    settings = get_settings()
    try:
        export_path = write_session_export(session_id, settings=settings)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return FileResponse(
        path=export_path,
        media_type="application/json",
        filename=export_path.name,
    )
