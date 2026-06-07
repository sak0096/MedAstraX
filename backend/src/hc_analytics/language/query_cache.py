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
    return connection


def store_interpretation(interpreted: InterpretedQuery, settings: Optional[Settings] = None) -> None:
    with _connect(settings) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO query_cache
            (query_id, natural_language, interpreted_json, result_json, confirmed, created_at)
            VALUES (?, ?, ?, COALESCE((SELECT result_json FROM query_cache WHERE query_id = ?), NULL), 0, ?)
            """,
            (
                interpreted.query_id,
                interpreted.natural_language,
                interpreted.model_dump_json(),
                interpreted.query_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.commit()


def load_interpretation(query_id: str, settings: Optional[Settings] = None) -> Optional[InterpretedQuery]:
    with _connect(settings) as connection:
        row = connection.execute(
            "SELECT interpreted_json FROM query_cache WHERE query_id = ?",
            (query_id,),
        ).fetchone()
    if row is None:
        return None
    return InterpretedQuery.model_validate_json(row[0])


def store_result(result: QueryResult, *, confirmed: bool, settings: Optional[Settings] = None) -> None:
    with _connect(settings) as connection:
        connection.execute(
            """
            UPDATE query_cache
            SET result_json = ?, confirmed = ?
            WHERE query_id = ?
            """,
            (result.model_dump_json(), int(confirmed), result.query_id),
        )
        connection.commit()


def load_result(query_id: str, settings: Optional[Settings] = None) -> Optional[QueryResult]:
    with _connect(settings) as connection:
        row = connection.execute(
            "SELECT result_json, confirmed FROM query_cache WHERE query_id = ?",
            (query_id,),
        ).fetchone()
    if row is None or row[0] is None or not row[1]:
        return None
    result = QueryResult.model_validate_json(row[0])
    result.cached = True
    return result
