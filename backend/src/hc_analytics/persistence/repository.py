"""Transactional repository for assignments, sessions, responses, and deletion."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, Optional

from hc_analytics.config import Settings, get_settings
from hc_analytics.persistence.schema import INDEX_STATEMENTS, SCHEMA_STATEMENTS

SCHEMA_VERSION = "2026-11-06.3"


class StudyStoreError(Exception):
    """Base error for canonical study state."""


class CapExceeded(StudyStoreError):
    """Enrollment would exceed a configured cap."""


class DuplicateNonce(StudyStoreError):
    """The integration nonce was already used."""


class StateConflict(StudyStoreError):
    """A write contradicts an already committed study fact."""


class AttemptsExhausted(StudyStoreError):
    """The comprehension retry allowance is already used."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def format_participant_code(namespace: str, slot: int) -> str:
    """Test launches never occupy production P001-P120 codes."""
    if namespace == "test":
        return f"TEST-{slot:03d}"
    if namespace == "pilot":
        return f"P{slot:03d}"
    raise StudyStoreError(f"Unknown enrollment namespace: {namespace}")


def _mapping(row: Any) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    return dict(row)


class StudyRepository:
    def __init__(self, backend: str, dsn: str) -> None:
        if backend not in {"sqlite", "postgres"}:
            raise StudyStoreError(f"Unsupported storage backend: {backend}")
        self.backend = backend
        self.dsn = dsn
        self._schema_ready = False

    @classmethod
    def from_settings(cls, settings: Optional[Settings] = None) -> "StudyRepository":
        runtime = settings or get_settings()
        if runtime.environment == "production" and runtime.storage_backend != "postgres":
            raise StudyStoreError("Production study state requires PostgreSQL.")
        if runtime.storage_backend == "postgres":
            if not runtime.database_url:
                raise StudyStoreError("HC_DATABASE_URL is required for PostgreSQL.")
            return cls("postgres", runtime.database_url)
        path = runtime.artifacts_path / "study_state.sqlite"
        path.parent.mkdir(parents=True, exist_ok=True)
        return cls("sqlite", str(path))

    def _adapt(self, sql: str) -> str:
        if self.backend == "postgres":
            return sql.replace("?", "%s")
        return sql

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        if self.backend == "sqlite":
            connection = sqlite3.connect(self.dsn, timeout=15, isolation_level=None)
            connection.row_factory = sqlite3.Row
            try:
                yield connection
            finally:
                connection.close()
            return
        import psycopg
        from psycopg.rows import dict_row

        connection = psycopg.connect(self.dsn, connect_timeout=10, row_factory=dict_row)
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        with self._connection() as connection:
            try:
                if self.backend == "sqlite":
                    connection.execute("BEGIN IMMEDIATE")
                    yield connection
                    connection.execute("COMMIT")
                else:
                    yield connection
                    connection.commit()
            except Exception:
                if self.backend == "sqlite":
                    connection.execute("ROLLBACK")
                else:
                    connection.rollback()
                raise

    def _execute(self, connection: Any, sql: str, params: tuple = ()) -> Any:
        return connection.execute(self._adapt(sql), params)

    def ensure_schema(self) -> None:
        if self._schema_ready:
            return
        if self.backend == "postgres":
            try:
                with self._connection() as connection:
                    existing = _mapping(
                        self._execute(
                            connection,
                            "SELECT version FROM schema_meta WHERE id = 1",
                        ).fetchone()
                    )
            except Exception as error:
                raise StudyStoreError(
                    "PostgreSQL schema is missing; run the migration with the deployment role."
                ) from error
            if existing is None or existing["version"] != SCHEMA_VERSION:
                raise StudyStoreError(f"PostgreSQL schema version {SCHEMA_VERSION} is required.")
            self._schema_ready = True
            return
        self.migrate()

    def migrate(self) -> None:
        """Create/update schema with a deployment role, never the runtime role."""
        with self.transaction() as connection:
            for statement in SCHEMA_STATEMENTS:
                self._execute(connection, statement)
            for statement in INDEX_STATEMENTS:
                self._execute(connection, statement)
            existing = _mapping(
                self._execute(connection, "SELECT version FROM schema_meta WHERE id = 1").fetchone()
            )
            if existing is None:
                try:
                    self._execute(
                        connection,
                        "INSERT INTO schema_meta (id, version) VALUES (1, ?)",
                        (SCHEMA_VERSION,),
                    )
                except Exception as error:
                    if not _is_integrity_error(error):
                        raise
            elif existing["version"] == "2026-11-06.2":
                self._execute(
                    connection,
                    """
                    ALTER TABLE task_trials
                    ADD COLUMN block_index INTEGER NOT NULL DEFAULT 0
                    """,
                )
                self._execute(
                    connection,
                    "UPDATE schema_meta SET version = ? WHERE id = 1",
                    (SCHEMA_VERSION,),
                )
            elif existing["version"] != SCHEMA_VERSION:
                raise StudyStoreError(
                    f"Unsupported schema upgrade from {existing['version']} to {SCHEMA_VERSION}."
                )
        self._schema_ready = True

    def launch(
        self,
        *,
        namespace: str,
        study: str,
        survey_id: str,
        survey_version: str,
        nonce: str,
        enrollment_reference: Optional[str],
        environment: str,
        purpose: str,
        ttl_seconds: int,
        cap_per_study: int,
        cap_total: int,
    ) -> Dict[str, Any]:
        """Commit an enrollment and a one-time launch token, or roll both back."""
        from hc_analytics.study.session import assign_manipulations, assignment_plan

        self.ensure_schema()
        now = _utcnow()
        nonce_hash = digest(nonce)
        token = uuid.uuid4().hex + uuid.uuid4().hex
        token_hash = digest(token)
        enrollment_id = str(uuid.uuid4())
        expires_at = _iso(now + timedelta(seconds=ttl_seconds))
        with self.transaction() as connection:
            existing_nonce = self._execute(
                connection,
                "SELECT nonce_hash FROM launch_nonces WHERE nonce_hash = ?",
                (nonce_hash,),
            ).fetchone()
            if existing_nonce is not None:
                raise DuplicateNonce("This launch nonce was already used.")
            self._execute(
                connection,
                "INSERT INTO launch_nonces (nonce_hash, created_at) VALUES (?, ?)",
                (nonce_hash, _iso(now)),
            )
            self._lock_counter(connection, namespace, "*")
            study_count = self._count(
                connection,
                "SELECT COUNT(*) AS n FROM enrollments WHERE namespace = ? AND study = ?",
                (namespace, study),
            )
            total_count = self._count(
                connection,
                "SELECT COUNT(*) AS n FROM enrollments WHERE namespace = ?",
                (namespace,),
            )
            if study_count >= cap_per_study or total_count >= cap_total:
                raise CapExceeded("Enrollment cap reached.")
            slot_row = _mapping(
                self._execute(
                    connection,
                    "SELECT next_slot FROM roster_counters WHERE namespace = ? AND study = ?",
                    (namespace, "*"),
                ).fetchone()
            )
            slot = int(slot_row["next_slot"]) if slot_row else 1
            participant_code = format_participant_code(namespace, slot)
            plan = assignment_plan(participant_code)
            order_key = "study1_order" if study == "study1" else "study2_order"
            condition_order = list(plan[order_key])
            case_sets = {
                "first": plan["case_set_first"],
                "second": plan["case_set_second"],
            }
            error_slots = assign_manipulations(participant_code)
            self._execute(
                connection,
                """
                INSERT INTO enrollments (
                    enrollment_id, participant_code, namespace, study, status, stage,
                    condition_order_json, case_sets_json, error_slots_json, survey_id,
                    survey_version, consent_authorized, consent_at, enrollment_reference,
                    exit_reason, payment_stage, payment_amount_cents, retention_choice, created_at
                ) VALUES (?, ?, ?, ?, 'enrolled', 'tutorial', ?, ?, ?, ?, ?, 1, ?, ?, NULL, NULL, NULL, NULL, ?)
                """,
                (
                    enrollment_id,
                    participant_code,
                    namespace,
                    study,
                    json.dumps(condition_order),
                    json.dumps(case_sets),
                    json.dumps(error_slots),
                    survey_id,
                    survey_version,
                    _iso(now),
                    enrollment_reference,
                    _iso(now),
                ),
            )
            self._execute(
                connection,
                """
                INSERT INTO launch_tokens (
                    token_hash, enrollment_id, purpose, environment, expires_at, consumed_at, created_at
                ) VALUES (?, ?, ?, ?, ?, NULL, ?)
                """,
                (token_hash, enrollment_id, purpose, environment, expires_at, _iso(now)),
            )
            self._increment_counter(connection, namespace, "*")
        return {
            "enrollment_id": enrollment_id,
            "participant_code": participant_code,
            "launch_token": token,
            "expires_at": expires_at,
            "study": study,
            "stage": "tutorial",
        }

    def next_slot(self, namespace: str, study: str) -> int:
        """Peek the next roster slot. Allocation itself happens inside launch()."""
        self.ensure_schema()
        with self.transaction() as connection:
            self._lock_counter(connection, namespace, study)
            row = _mapping(
                self._execute(
                    connection,
                    "SELECT next_slot FROM roster_counters WHERE namespace = ? AND study = ?",
                    (namespace, study),
                ).fetchone()
            )
        if row is None:
            return 1
        return int(row["next_slot"])

    def _lock_counter(self, connection: Any, namespace: str, study: str) -> None:
        if self.backend == "sqlite":
            self._execute(
                connection,
                "INSERT OR IGNORE INTO roster_counters (namespace, study, next_slot) VALUES (?, ?, 1)",
                (namespace, study),
            )
        else:
            self._execute(
                connection,
                """
                INSERT INTO roster_counters (namespace, study, next_slot) VALUES (?, ?, 1)
                ON CONFLICT (namespace, study) DO NOTHING
                """,
                (namespace, study),
            )
        if self.backend == "postgres":
            self._execute(
                connection,
                "SELECT next_slot FROM roster_counters WHERE namespace = ? AND study = ? FOR UPDATE",
                (namespace, study),
            ).fetchone()

    def _increment_counter(self, connection: Any, namespace: str, study: str) -> None:
        self._execute(
            connection,
            """
            UPDATE roster_counters SET next_slot = next_slot + 1
            WHERE namespace = ? AND study = ?
            """,
            (namespace, study),
        )

    def _count(self, connection: Any, sql: str, params: tuple) -> int:
        row = _mapping(self._execute(connection, sql, params).fetchone())
        if row is None:
            return 0
        return int(row["n"])

    def consume_launch_token(
        self, token: str, *, environment: str, purpose: str, session_ttl_seconds: int
    ) -> Dict[str, Any]:
        self.ensure_schema()
        now = _utcnow()
        token_hash = digest(token)
        session_secret = uuid.uuid4().hex + uuid.uuid4().hex
        session_hash = digest(session_secret)
        expires_at = _iso(now + timedelta(seconds=session_ttl_seconds))
        with self.transaction() as connection:
            row = _mapping(
                self._execute(
                    connection,
                    """
                    SELECT token_hash, enrollment_id, purpose, environment, expires_at, consumed_at
                    FROM launch_tokens WHERE token_hash = ?
                    """,
                    (token_hash,),
                ).fetchone()
            )
            if row is None or row["consumed_at"] is not None:
                raise StateConflict("Launch credential is not usable.")
            if row["purpose"] != purpose or row["environment"] != environment:
                raise StateConflict("Launch credential is not usable.")
            if _parse_time(str(row["expires_at"])) <= now:
                raise StateConflict("Launch credential is not usable.")
            updated = self._execute(
                connection,
                """
                UPDATE launch_tokens SET consumed_at = ?
                WHERE token_hash = ? AND consumed_at IS NULL
                """,
                (_iso(now), token_hash),
            )
            if getattr(updated, "rowcount", 1) == 0:
                raise StateConflict("Launch credential is not usable.")
            enrollment = self._enrollment_row(connection, str(row["enrollment_id"]))
            if enrollment is None or enrollment["status"] == "deleted":
                raise StateConflict("Launch credential is not usable.")
            self._execute(
                connection,
                """
                INSERT INTO study_sessions (
                    session_hash, enrollment_id, stage, condition, block_index, current_task_id,
                    expires_at, revoked_at, created_at
                ) VALUES (?, ?, ?, ?, 0, NULL, ?, NULL, ?)
                """,
                (
                    session_hash,
                    enrollment["enrollment_id"],
                    enrollment["stage"],
                    _first_condition(enrollment),
                    expires_at,
                    _iso(now),
                ),
            )
        session = self.get_active_session(session_secret)
        if session is None:
            raise StudyStoreError("Session was not committed.")
        session["session_cookie"] = session_secret
        return session

    def get_active_session(self, session_cookie: str) -> Optional[Dict[str, Any]]:
        self.ensure_schema()
        session_hash = digest(session_cookie)
        with self._connection() as connection:
            row = _mapping(
                self._execute(
                    connection,
                    """
                    SELECT session_hash, enrollment_id, stage, condition, block_index, current_task_id,
                           expires_at, revoked_at
                    FROM study_sessions WHERE session_hash = ?
                    """,
                    (session_hash,),
                ).fetchone()
            )
            if row is None or row["revoked_at"] is not None:
                return None
            if _parse_time(str(row["expires_at"])) <= _utcnow():
                return None
            enrollment = self._enrollment_row(connection, str(row["enrollment_id"]))
        if enrollment is None or enrollment["status"] == "deleted":
            return None
        return _public_binding(enrollment, row, session_hash)

    def _enrollment_row(self, connection: Any, enrollment_id: str) -> Optional[Dict[str, Any]]:
        return _mapping(
            self._execute(
                connection,
                "SELECT * FROM enrollments WHERE enrollment_id = ?",
                (enrollment_id,),
            ).fetchone()
        )

    def get_enrollment_by_code(self, participant_code: str) -> Optional[Dict[str, Any]]:
        self.ensure_schema()
        with self._connection() as connection:
            row = _mapping(
                self._execute(
                    connection,
                    "SELECT * FROM enrollments WHERE participant_code = ?",
                    (participant_code,),
                ).fetchone()
            )
        if row is None:
            return None
        return _hydrate_enrollment(row)

    def set_stage(
        self, enrollment_id: str, stage: str, *, exit_reason: Optional[str] = None
    ) -> None:
        self.ensure_schema()
        with self.transaction() as connection:
            self._execute(
                connection,
                "UPDATE enrollments SET stage = ?, exit_reason = COALESCE(?, exit_reason) WHERE enrollment_id = ?",
                (stage, exit_reason, enrollment_id),
            )
            self._execute(
                connection,
                "UPDATE study_sessions SET stage = ? WHERE enrollment_id = ? AND revoked_at IS NULL",
                (stage, enrollment_id),
            )

    def set_current_task(self, session_hash: str, task_id: str) -> None:
        self.ensure_schema()
        with self.transaction() as connection:
            self._execute(
                connection,
                "UPDATE study_sessions SET current_task_id = ? WHERE session_hash = ?",
                (task_id, session_hash),
            )

    def open_trial(self, *, enrollment_id: str, session_hash: str, task_id: str) -> str:
        self.ensure_schema()
        now = _iso(_utcnow())
        with self.transaction() as connection:
            session = _mapping(
                self._execute(
                    connection,
                    """
                    SELECT block_index FROM study_sessions
                    WHERE session_hash = ? AND enrollment_id = ? AND revoked_at IS NULL
                    """,
                    (session_hash, enrollment_id),
                ).fetchone()
            )
            if session is None:
                raise StateConflict("Study session is not active.")
            block_index = int(session["block_index"])
            existing = _mapping(
                self._execute(
                    connection,
                    """
                    SELECT trial_id FROM task_trials
                    WHERE enrollment_id = ? AND task_id = ? AND block_index = ?
                      AND phase != 'final_locked'
                    ORDER BY created_at DESC
                    """,
                    (enrollment_id, task_id, block_index),
                ).fetchone()
            )
            if existing is not None:
                trial_id = str(existing["trial_id"])
            else:
                trial_id = str(uuid.uuid4())
                self._execute(
                    connection,
                    """
                    INSERT INTO task_trials (
                        trial_id, enrollment_id, session_hash, task_id, block_index, phase, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'started', ?)
                    """,
                    (trial_id, enrollment_id, session_hash, task_id, block_index, now),
                )
            self._execute(
                connection,
                "UPDATE study_sessions SET current_task_id = ? WHERE session_hash = ?",
                (task_id, session_hash),
            )
        return trial_id

    def get_trial_for_enrollment(
        self, trial_id: str, enrollment_id: str
    ) -> Optional[Dict[str, Any]]:
        self.ensure_schema()
        with self._connection() as connection:
            return _mapping(
                self._execute(
                    connection,
                    """
                    SELECT * FROM task_trials WHERE trial_id = ? AND enrollment_id = ?
                    """,
                    (trial_id, enrollment_id),
                ).fetchone()
            )

    def get_response(self, trial_id: str, phase: str) -> Optional[Dict[str, Any]]:
        self.ensure_schema()
        with self._connection() as connection:
            row = _mapping(
                self._execute(
                    connection,
                    "SELECT * FROM task_responses WHERE trial_id = ? AND phase = ?",
                    (trial_id, phase),
                ).fetchone()
            )
        if row is None:
            return None
        row["payload"] = json.loads(row["payload_json"])
        return row

    def save_response(
        self,
        *,
        enrollment_id: str,
        trial_id: str,
        task_id: str,
        phase: str,
        payload: Dict[str, Any],
        confidence: Optional[int],
    ) -> Dict[str, Any]:
        self.ensure_schema()
        encoded = json.dumps(payload, sort_keys=True, default=str)
        now = _iso(_utcnow())
        with self.transaction() as connection:
            owned = self._execute(
                connection,
                "SELECT trial_id FROM task_trials WHERE trial_id = ? AND enrollment_id = ?",
                (trial_id, enrollment_id),
            ).fetchone()
            if owned is None:
                raise StateConflict("Trial is not part of this enrollment.")
            try:
                self._execute(
                    connection,
                    """
                    INSERT INTO task_responses (
                        response_id, enrollment_id, trial_id, task_id, phase, payload_json, confidence, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        enrollment_id,
                        trial_id,
                        task_id,
                        phase,
                        encoded,
                        confidence,
                        now,
                    ),
                )
            except Exception as error:
                if not _is_integrity_error(error):
                    raise
                existing = _mapping(
                    self._execute(
                        connection,
                        "SELECT payload_json, confidence FROM task_responses WHERE trial_id = ? AND phase = ?",
                        (trial_id, phase),
                    ).fetchone()
                )
                if (
                    existing is None
                    or existing["payload_json"] != encoded
                    or existing["confidence"] != confidence
                ):
                    raise StateConflict("The initial answer is already locked.") from error
                return {"idempotent": True, "phase": phase}
            if phase == "initial":
                self._execute(
                    connection,
                    "UPDATE task_trials SET phase = 'initial_locked' WHERE trial_id = ?",
                    (trial_id,),
                )
            elif phase in {"final", "single"}:
                self._execute(
                    connection,
                    "UPDATE task_trials SET phase = 'final_locked' WHERE trial_id = ?",
                    (trial_id,),
                )
        return {"idempotent": False, "phase": phase}

    def assert_task_available(
        self, enrollment_id: str, task_id: str, task_order: list[str]
    ) -> None:
        """Require the approved within-block order and a task-open stage."""
        self.ensure_schema()
        approved = [item for item in task_order if not item.endswith("-T0")]
        if task_id not in approved:
            raise StateConflict("Task is not in the approved participant sequence.")
        with self._connection() as connection:
            session = _mapping(
                self._execute(
                    connection,
                    """
                    SELECT stage, block_index FROM study_sessions
                    WHERE enrollment_id = ? AND revoked_at IS NULL
                    ORDER BY created_at DESC
                    """,
                    (enrollment_id,),
                ).fetchone()
            )
            if session is None or session["stage"] not in {"block1_tasks", "block2_tasks"}:
                raise StateConflict("Research tasks are not open.")
            completed_rows = self._execute(
                connection,
                """
                SELECT DISTINCT task_id FROM task_trials
                WHERE enrollment_id = ? AND block_index = ? AND phase = 'final_locked'
                """,
                (enrollment_id, int(session["block_index"])),
            ).fetchall()
        completed = {str(_mapping(row)["task_id"]) for row in completed_rows}
        expected = next((item for item in approved if item not in completed), None)
        if expected != task_id:
            raise StateConflict(
                "Complete the assigned tasks in order."
                if expected is not None
                else "This task block is already complete."
            )

    def close_task_block_if_complete(
        self, enrollment_id: str, task_order: list[str]
    ) -> Optional[str]:
        """Atomically move a completed task block to its survey handoff."""
        self.ensure_schema()
        approved = [item for item in task_order if not item.endswith("-T0")]
        with self.transaction() as connection:
            session = _mapping(
                self._execute(
                    connection,
                    """
                    SELECT session_hash, stage, block_index FROM study_sessions
                    WHERE enrollment_id = ? AND revoked_at IS NULL
                    ORDER BY created_at DESC
                    """,
                    (enrollment_id,),
                ).fetchone()
            )
            if session is None or session["stage"] not in {"block1_tasks", "block2_tasks"}:
                return None
            rows = self._execute(
                connection,
                """
                SELECT DISTINCT task_id FROM task_trials
                WHERE enrollment_id = ? AND block_index = ? AND phase = 'final_locked'
                """,
                (enrollment_id, int(session["block_index"])),
            ).fetchall()
            completed = {str(_mapping(row)["task_id"]) for row in rows}
            if not all(item in completed for item in approved):
                return None
            next_stage = (
                "post_condition_1_survey" if int(session["block_index"]) == 0 else "final_survey"
            )
            self._execute(
                connection,
                "UPDATE enrollments SET stage = ? WHERE enrollment_id = ?",
                (next_stage, enrollment_id),
            )
            self._execute(
                connection,
                """
                UPDATE study_sessions SET stage = ?, current_task_id = NULL
                WHERE enrollment_id = ? AND revoked_at IS NULL
                """,
                (next_stage, enrollment_id),
            )
        return next_stage

    def apply_survey_callback(
        self,
        *,
        participant_code: str,
        callback_type: str,
        nonce: str,
        survey_id: str,
        survey_version: str,
        retention_choice: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Apply an authenticated, replay-safe Qualtrics stage transition."""
        self.ensure_schema()
        nonce_hash = digest(nonce)
        now = _iso(_utcnow())
        with self.transaction() as connection:
            enrollment = _mapping(
                self._execute(
                    connection,
                    "SELECT * FROM enrollments WHERE participant_code = ?",
                    (participant_code,),
                ).fetchone()
            )
            if enrollment is None:
                raise StateConflict("Enrollment is not active.")
            existing = _mapping(
                self._execute(
                    connection,
                    """
                    SELECT enrollment_id, callback_type, to_stage, survey_id, survey_version
                    FROM integration_callbacks
                    WHERE callback_nonce_hash = ?
                    """,
                    (nonce_hash,),
                ).fetchone()
            )
            if existing is not None:
                if (
                    existing["callback_type"] != callback_type
                    or existing["enrollment_id"] != enrollment["enrollment_id"]
                    or existing["survey_id"] != survey_id
                    or existing["survey_version"] != survey_version
                ):
                    raise StateConflict("Callback nonce was already used.")
                return {
                    "stage": existing["to_stage"],
                    "callback_type": callback_type,
                    "idempotent": True,
                }
            if enrollment["status"] == "deleted":
                raise StateConflict("Enrollment is not active.")
            if (
                enrollment["survey_id"] != survey_id
                or enrollment["survey_version"] != survey_version
            ):
                raise StateConflict("Survey identity does not match the enrollment.")
            from_stage = str(enrollment["stage"])
            if callback_type == "post_condition_1_complete":
                if from_stage != "post_condition_1_survey":
                    raise StateConflict("The first condition survey is not open.")
                to_stage = "block2_tasks"
                block_index = 1
                condition_order = json.loads(enrollment["condition_order_json"])
                condition = condition_order[1]
            elif callback_type == "final_complete":
                if from_stage != "final_survey":
                    raise StateConflict("The final survey is not open.")
                if retention_choice not in {"retain", "delete"}:
                    raise StateConflict("A final retention choice is required.")
                to_stage = "complete"
                block_index = 1
                condition = None
            elif callback_type in {"withdrawn", "technical_stop"}:
                if from_stage in {"deleted", "retention_choice", "complete"}:
                    raise StateConflict("Enrollment is already closed.")
                to_stage = callback_type
                block_index = 0
                condition = None
            else:
                raise StateConflict("Unknown survey callback.")
            self._execute(
                connection,
                """
                UPDATE enrollments
                SET stage = ?, status = CASE WHEN ? IN ('withdrawn', 'technical_stop')
                                             THEN ? ELSE status END,
                    exit_reason = CASE WHEN ? IN ('withdrawn', 'technical_stop')
                                       THEN ? ELSE exit_reason END,
                    retention_choice = COALESCE(?, retention_choice)
                WHERE enrollment_id = ?
                """,
                (
                    to_stage,
                    to_stage,
                    to_stage,
                    to_stage,
                    to_stage,
                    retention_choice,
                    enrollment["enrollment_id"],
                ),
            )
            self._execute(
                connection,
                """
                UPDATE study_sessions
                SET stage = ?, block_index = ?, condition = COALESCE(?, condition),
                    current_task_id = NULL,
                    revoked_at = CASE WHEN ? IN ('withdrawn', 'technical_stop', 'complete')
                                      THEN ? ELSE revoked_at END
                WHERE enrollment_id = ? AND revoked_at IS NULL
                """,
                (
                    to_stage,
                    block_index,
                    condition,
                    to_stage,
                    now,
                    enrollment["enrollment_id"],
                ),
            )
            self._execute(
                connection,
                """
                INSERT INTO integration_callbacks (
                    callback_nonce_hash, enrollment_id, callback_type, from_stage, to_stage,
                    survey_id, survey_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    nonce_hash,
                    enrollment["enrollment_id"],
                    callback_type,
                    from_stage,
                    to_stage,
                    survey_id,
                    survey_version,
                    now,
                ),
            )
        return {"stage": to_stage, "callback_type": callback_type, "idempotent": False}

    def record_comprehension(
        self,
        *,
        enrollment_id: str,
        study: str,
        idempotency_key: str,
        correct_count: int,
        question_count: int,
        passed: bool,
        max_attempts: int = 2,
    ) -> Dict[str, Any]:
        self.ensure_schema()
        now = _iso(_utcnow())
        with self.transaction() as connection:
            existing = _mapping(
                self._execute(
                    connection,
                    """
                    SELECT attempt_number, correct_count, question_count, passed
                    FROM comprehension_attempts WHERE idempotency_key = ?
                    """,
                    (idempotency_key,),
                ).fetchone()
            )
            if existing is not None:
                return {
                    "attempt_number": int(existing["attempt_number"]),
                    "correct_count": int(existing["correct_count"]),
                    "question_count": int(existing["question_count"]),
                    "passed": bool(existing["passed"]),
                    "idempotent": True,
                    "research_tasks_ended": int(existing["attempt_number"]) >= max_attempts
                    and not bool(existing["passed"]),
                }
            attempt_number = (
                self._count(
                    connection,
                    "SELECT COUNT(*) AS n FROM comprehension_attempts WHERE enrollment_id = ? AND study = ?",
                    (enrollment_id, study),
                )
                + 1
            )
            if attempt_number > max_attempts:
                raise AttemptsExhausted("Comprehension retries are exhausted.")
            self._execute(
                connection,
                """
                INSERT INTO comprehension_attempts (
                    attempt_id, enrollment_id, study, idempotency_key, attempt_number,
                    correct_count, question_count, passed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    enrollment_id,
                    study,
                    idempotency_key,
                    attempt_number,
                    correct_count,
                    question_count,
                    int(passed),
                    now,
                ),
            )
            research_tasks_ended = attempt_number >= max_attempts and not passed
            if passed:
                self._execute(
                    connection,
                    "UPDATE enrollments SET stage = 'block1_tasks' WHERE enrollment_id = ?",
                    (enrollment_id,),
                )
                self._execute(
                    connection,
                    """
                    UPDATE study_sessions SET stage = 'block1_tasks'
                    WHERE enrollment_id = ? AND revoked_at IS NULL
                    """,
                    (enrollment_id,),
                )
            elif research_tasks_ended:
                self._execute(
                    connection,
                    """
                    UPDATE enrollments
                    SET stage = 'comprehension_failed', exit_reason = 'comprehension_failed_before_tasks',
                        payment_amount_cents = NULL
                    WHERE enrollment_id = ?
                    """,
                    (enrollment_id,),
                )
                self._execute(
                    connection,
                    """
                    UPDATE study_sessions SET stage = 'comprehension_failed'
                    WHERE enrollment_id = ? AND revoked_at IS NULL
                    """,
                    (enrollment_id,),
                )
        return {
            "attempt_number": attempt_number,
            "correct_count": correct_count,
            "question_count": question_count,
            "passed": passed,
            "idempotent": False,
            "research_tasks_ended": research_tasks_ended,
        }

    def set_retention(self, enrollment_id: str, choice: str) -> None:
        if choice not in {"retain", "delete"}:
            raise StateConflict("Retention choice must be retain or delete.")
        self.ensure_schema()
        with self.transaction() as connection:
            self._execute(
                connection,
                """
                UPDATE enrollments
                SET retention_choice = ?, stage = 'retention_choice'
                WHERE enrollment_id = ?
                """,
                (choice, enrollment_id),
            )

    def revoke_sessions(self, enrollment_id: str) -> None:
        self.ensure_schema()
        now = _iso(_utcnow())
        with self.transaction() as connection:
            self._execute(
                connection,
                "UPDATE study_sessions SET revoked_at = ? WHERE enrollment_id = ? AND revoked_at IS NULL",
                (now, enrollment_id),
            )

    def delete_participant(self, participant_code: str) -> Dict[str, Any]:
        """Remove research content. The code still occupies its enrollment cap."""
        self.ensure_schema()
        now = _iso(_utcnow())
        with self.transaction() as connection:
            enrollment = _mapping(
                self._execute(
                    connection,
                    "SELECT * FROM enrollments WHERE participant_code = ?",
                    (participant_code,),
                ).fetchone()
            )
            if enrollment is None:
                raise StateConflict("Unknown participant code.")
            already = _mapping(
                self._execute(
                    connection,
                    "SELECT participant_code, qualtrics_status FROM deletion_ledger WHERE participant_code = ?",
                    (participant_code,),
                ).fetchone()
            )
            enrollment_id = str(enrollment["enrollment_id"])
            payment_stage = enrollment["payment_stage"]
            self._execute(
                connection, "DELETE FROM task_responses WHERE enrollment_id = ?", (enrollment_id,)
            )
            self._execute(
                connection, "DELETE FROM task_trials WHERE enrollment_id = ?", (enrollment_id,)
            )
            self._execute(
                connection,
                "DELETE FROM comprehension_attempts WHERE enrollment_id = ?",
                (enrollment_id,),
            )
            self._execute(
                connection,
                "DELETE FROM query_versions WHERE owner_id = ?",
                (enrollment_id,),
            )
            self._execute(
                connection, "DELETE FROM canonical_events WHERE enrollment_id = ?", (enrollment_id,)
            )
            self._execute(
                connection,
                "UPDATE study_sessions SET revoked_at = ?, current_task_id = NULL WHERE enrollment_id = ?",
                (now, enrollment_id),
            )
            self._execute(
                connection,
                """
                UPDATE enrollments
                SET status = 'deleted', stage = 'deleted', error_slots_json = '{}',
                    case_sets_json = '{}', condition_order_json = '[]',
                    enrollment_reference = NULL, survey_id = NULL, survey_version = NULL
                WHERE enrollment_id = ?
                """,
                (enrollment_id,),
            )
            if already is None:
                self._execute(
                    connection,
                    """
                    INSERT INTO deletion_ledger (
                        participant_code, enrollment_id, requested_at, applied_at, qualtrics_status,
                        payment_stage, counts_toward_cap
                    ) VALUES (?, ?, ?, ?, 'pending', ?, 1)
                    """,
                    (participant_code, enrollment_id, now, now, payment_stage),
                )
        return {
            "participant_code": participant_code,
            "deleted": True,
            "idempotent": already is not None,
            "qualtrics_status": "pending",
            "payment_stage": payment_stage,
            "counts_toward_cap": True,
        }

    def reapply_deletions(self) -> int:
        self.ensure_schema()
        with self._connection() as connection:
            rows = self._execute(
                connection, "SELECT participant_code FROM deletion_ledger"
            ).fetchall()
        count = 0
        for row in rows:
            mapping = _mapping(row)
            if mapping is None:
                continue
            self.delete_participant(str(mapping["participant_code"]))
            count += 1
        return count

    def append_event(
        self,
        *,
        event_type: str,
        enrollment_id: Optional[str],
        session_hash: Optional[str],
        task_id: Optional[str],
        payload: Dict[str, Any],
        event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.ensure_schema()
        event_id = event_id or str(uuid.uuid4())
        now = _iso(_utcnow())
        encoded = json.dumps(payload, sort_keys=True, default=str)
        with self.transaction() as connection:
            existing = self._execute(
                connection,
                "SELECT event_id FROM canonical_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if existing is None:
                self._execute(
                    connection,
                    """
                    INSERT INTO canonical_events (
                        event_id, event_type, enrollment_id, session_hash, task_id, payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (event_id, event_type, enrollment_id, session_hash, task_id, encoded, now),
                )
        return {"event_id": event_id, "event_type": event_type, "created_at": now}

    def store_query(
        self,
        *,
        query_id: str,
        owner_id: Optional[str],
        natural_language: str,
        interpreted_json: str,
        parent_query_id: Optional[str],
        status: str,
        lineage_json: Optional[str],
    ) -> None:
        self.ensure_schema()
        with self.transaction() as connection:
            existing = self._execute(
                connection,
                "SELECT query_id FROM query_versions WHERE query_id = ?",
                (query_id,),
            ).fetchone()
            if existing is not None:
                raise StateConflict("Query version already exists.")
            self._execute(
                connection,
                """
                INSERT INTO query_versions (
                    query_id, owner_id, natural_language, interpreted_json, result_json,
                    confirmed, parent_query_id, status, lineage_json, created_at
                ) VALUES (?, ?, ?, ?, NULL, 0, ?, ?, ?, ?)
                """,
                (
                    query_id,
                    owner_id,
                    natural_language,
                    interpreted_json,
                    parent_query_id,
                    status,
                    lineage_json,
                    _iso(_utcnow()),
                ),
            )

    def load_query(self, query_id: str, *, owner_id: Optional[str]) -> Optional[Dict[str, Any]]:
        self.ensure_schema()
        with self._connection() as connection:
            row = _mapping(
                self._execute(
                    connection,
                    "SELECT * FROM query_versions WHERE query_id = ?",
                    (query_id,),
                ).fetchone()
            )
        if row is None:
            return None
        if row["owner_id"] is not None and row["owner_id"] != owner_id:
            return None
        return row

    def set_query_result(
        self,
        query_id: str,
        *,
        owner_id: Optional[str],
        result_json: str,
        confirmed: bool,
    ) -> None:
        self.ensure_schema()
        with self.transaction() as connection:
            row = _mapping(
                self._execute(
                    connection,
                    "SELECT owner_id FROM query_versions WHERE query_id = ?",
                    (query_id,),
                ).fetchone()
            )
            if row is None or (row["owner_id"] is not None and row["owner_id"] != owner_id):
                raise StateConflict("Unknown query version.")
            self._execute(
                connection,
                """
                UPDATE query_versions
                SET result_json = ?, confirmed = ?
                WHERE query_id = ?
                """,
                (result_json, int(confirmed), query_id),
            )

    def set_query_status(
        self,
        query_id: str,
        *,
        owner_id: Optional[str],
        status: str,
    ) -> None:
        self.ensure_schema()
        with self.transaction() as connection:
            row = _mapping(
                self._execute(
                    connection,
                    "SELECT owner_id FROM query_versions WHERE query_id = ?",
                    (query_id,),
                ).fetchone()
            )
            if row is None or (row["owner_id"] is not None and row["owner_id"] != owner_id):
                raise StateConflict("Unknown query version.")
            self._execute(
                connection,
                "UPDATE query_versions SET status = ? WHERE query_id = ?",
                (status, query_id),
            )


def _is_integrity_error(error: Exception) -> bool:
    if isinstance(error, sqlite3.IntegrityError):
        return True
    return error.__class__.__name__ == "IntegrityError"


def _first_condition(enrollment: Dict[str, Any]) -> Optional[str]:
    order = json.loads(enrollment["condition_order_json"])
    if isinstance(order, list) and order:
        return str(order[0])
    return None


def _hydrate_enrollment(row: Dict[str, Any]) -> Dict[str, Any]:
    hydrated = dict(row)
    hydrated["condition_order"] = json.loads(row["condition_order_json"])
    hydrated["case_sets"] = json.loads(row["case_sets_json"])
    hydrated["error_slots"] = json.loads(row["error_slots_json"])
    return hydrated


def _public_binding(
    enrollment: Dict[str, Any], session: Dict[str, Any], session_hash: str
) -> Dict[str, Any]:
    hydrated = _hydrate_enrollment(enrollment)
    return {
        "session_hash": session_hash,
        "enrollment_id": hydrated["enrollment_id"],
        "participant_code": hydrated["participant_code"],
        "namespace": hydrated["namespace"],
        "study": hydrated["study"],
        "stage": session["stage"],
        "condition": session["condition"],
        "block_index": session["block_index"],
        "current_task_id": session["current_task_id"],
        "status": hydrated["status"],
        "error_slots": hydrated["error_slots"],
        "condition_order": hydrated["condition_order"],
        "exit_reason": hydrated["exit_reason"],
        "payment_amount_cents": hydrated["payment_amount_cents"],
        "retention_choice": hydrated["retention_choice"],
    }
