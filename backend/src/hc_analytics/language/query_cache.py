from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from hc_analytics.config import Settings, get_settings
from hc_analytics.language.models import InterpretedQuery, QueryResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS query_cache (
    query_id TEXT PRIMARY KEY,
    natural_language TEXT NOT NULL,
    interpreted_json TEXT NOT NULL,
    result_json TEXT,
    confirmed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
"""


def _cache_path(settings: Optional[Settings] = None) -> Path:
    settings = settings or get_settings()
    return settings.artifacts_path / "query_cache" / "queries.sqlite"


def _connect(settings: Optional[Settings] = None) -> sqlite3.Connection:
    path = _cache_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(_SCHEMA)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(query_cache)")}
    if "parent_query_id" not in columns:
        connection.execute("ALTER TABLE query_cache ADD COLUMN parent_query_id TEXT")
    if "status" not in columns:
        connection.execute("ALTER TABLE query_cache ADD COLUMN status TEXT DEFAULT 'interpreted'")
    if "lineage_json" not in columns:
        connection.execute("ALTER TABLE query_cache ADD COLUMN lineage_json TEXT")
    if "owner_id" not in columns:
        connection.execute("ALTER TABLE query_cache ADD COLUMN owner_id TEXT")
    return connection


def _postgres(settings: Settings) -> bool:
    return settings.storage_backend == "postgres"


def store_interpretation(
    interpreted: InterpretedQuery,
    settings: Optional[Settings] = None,
    *,
    owner_id: Optional[str] = None,
    parent_query_id: Optional[str] = None,
    status: str = "interpreted",
    lineage: Optional[dict] = None,
) -> None:
    runtime = settings or get_settings()
    lineage_json = json.dumps(lineage) if lineage is not None else None
    if _postgres(runtime):
        from hc_analytics.persistence.repository import StudyRepository

        StudyRepository.from_settings(runtime).store_query(
            query_id=interpreted.query_id,
            owner_id=owner_id,
            natural_language=interpreted.natural_language,
            interpreted_json=interpreted.model_dump_json(),
            parent_query_id=parent_query_id,
            status=status,
            lineage_json=lineage_json,
        )
        return
    with _connect(runtime) as connection:
        connection.execute(
            """
            INSERT INTO query_cache
            (query_id, natural_language, interpreted_json, result_json, confirmed, created_at,
             parent_query_id, status, lineage_json, owner_id)
            VALUES (?, ?, ?, NULL, 0, ?, ?, ?, ?, ?)
            """,
            (
                interpreted.query_id,
                interpreted.natural_language,
                interpreted.model_dump_json(),
                datetime.now(timezone.utc).isoformat(),
                parent_query_id,
                status,
                lineage_json,
                owner_id,
            ),
        )
        connection.commit()


def query_status(
    query_id: str,
    settings: Optional[Settings] = None,
    *,
    owner_id: Optional[str] = None,
) -> Optional[str]:
    runtime = settings or get_settings()
    if _postgres(runtime):
        from hc_analytics.persistence.repository import StudyRepository

        row = StudyRepository.from_settings(runtime).load_query(query_id, owner_id=owner_id)
        return str(row["status"]) if row is not None else None
    with _connect(runtime) as connection:
        row = connection.execute(
            """
            SELECT status FROM query_cache
            WHERE query_id = ? AND (owner_id IS NULL OR owner_id = ?)
            """,
            (query_id, owner_id),
        ).fetchone()
    if row is None:
        return None
    return row[0] or "interpreted"


def set_query_status(
    query_id: str,
    status: str,
    settings: Optional[Settings] = None,
    *,
    owner_id: Optional[str] = None,
) -> None:
    runtime = settings or get_settings()
    if _postgres(runtime):
        from hc_analytics.persistence.repository import StudyRepository

        StudyRepository.from_settings(runtime).set_query_status(
            query_id,
            owner_id=owner_id,
            status=status,
        )
        return
    with _connect(runtime) as connection:
        connection.execute(
            """
            UPDATE query_cache SET status = ?
            WHERE query_id = ? AND (owner_id IS NULL OR owner_id = ?)
            """,
            (status, query_id, owner_id),
        )
        connection.commit()


def load_interpretation(
    query_id: str,
    settings: Optional[Settings] = None,
    *,
    owner_id: Optional[str] = None,
) -> Optional[InterpretedQuery]:
    runtime = settings or get_settings()
    if _postgres(runtime):
        from hc_analytics.persistence.repository import StudyRepository

        row = StudyRepository.from_settings(runtime).load_query(query_id, owner_id=owner_id)
        if row is None:
            return None
        return InterpretedQuery.model_validate_json(row["interpreted_json"])
    with _connect(runtime) as connection:
        row = connection.execute(
            """
            SELECT interpreted_json FROM query_cache
            WHERE query_id = ? AND (owner_id IS NULL OR owner_id = ?)
            """,
            (query_id, owner_id),
        ).fetchone()
    if row is None:
        return None
    return InterpretedQuery.model_validate_json(row[0])


def store_result(
    result: QueryResult,
    *,
    confirmed: bool,
    settings: Optional[Settings] = None,
    owner_id: Optional[str] = None,
) -> None:
    runtime = settings or get_settings()
    if _postgres(runtime):
        from hc_analytics.persistence.repository import StudyRepository

        StudyRepository.from_settings(runtime).set_query_result(
            result.query_id,
            owner_id=owner_id,
            result_json=result.model_dump_json(),
            confirmed=confirmed,
        )
        return
    with _connect(runtime) as connection:
        connection.execute(
            """
            UPDATE query_cache
            SET result_json = ?, confirmed = ?
            WHERE query_id = ? AND (owner_id IS NULL OR owner_id = ?)
            """,
            (result.model_dump_json(), int(confirmed), result.query_id, owner_id),
        )
        connection.commit()


def load_result(
    query_id: str,
    settings: Optional[Settings] = None,
    *,
    owner_id: Optional[str] = None,
) -> Optional[QueryResult]:
    runtime = settings or get_settings()
    if _postgres(runtime):
        from hc_analytics.persistence.repository import StudyRepository

        row = StudyRepository.from_settings(runtime).load_query(query_id, owner_id=owner_id)
        if row is None or row["result_json"] is None or not row["confirmed"]:
            return None
        result = QueryResult.model_validate_json(row["result_json"])
        result.cached = True
        return result
    with _connect(runtime) as connection:
        row = connection.execute(
            """
            SELECT result_json, confirmed FROM query_cache
            WHERE query_id = ? AND (owner_id IS NULL OR owner_id = ?)
            """,
            (query_id, owner_id),
        ).fetchone()
    if row is None or row[0] is None or not row[1]:
        return None
    result = QueryResult.model_validate_json(row[0])
    result.cached = True
    return result
