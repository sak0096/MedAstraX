"""DDL for the canonical study store.

The same statements run on PostgreSQL and on the local SQLite compatibility
backend. PostgreSQL is the production store. SQLite is refused when HC_ENV is
production.
"""

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS schema_meta (
        id INTEGER PRIMARY KEY,
        version TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS roster_counters (
        namespace TEXT NOT NULL,
        study TEXT NOT NULL,
        next_slot INTEGER NOT NULL,
        PRIMARY KEY (namespace, study)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS launch_nonces (
        nonce_hash TEXT PRIMARY KEY,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS enrollments (
        enrollment_id TEXT PRIMARY KEY,
        participant_code TEXT NOT NULL UNIQUE,
        namespace TEXT NOT NULL,
        study TEXT NOT NULL,
        status TEXT NOT NULL,
        stage TEXT NOT NULL,
        condition_order_json TEXT NOT NULL,
        case_sets_json TEXT NOT NULL,
        error_slots_json TEXT NOT NULL,
        survey_id TEXT,
        survey_version TEXT,
        consent_authorized INTEGER NOT NULL CHECK (consent_authorized IN (0, 1)),
        consent_at TEXT,
        enrollment_reference TEXT,
        exit_reason TEXT,
        payment_stage TEXT,
        payment_amount_cents INTEGER,
        retention_choice TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS launch_tokens (
        token_hash TEXT PRIMARY KEY,
        enrollment_id TEXT NOT NULL REFERENCES enrollments(enrollment_id),
        purpose TEXT NOT NULL,
        environment TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        consumed_at TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS study_sessions (
        session_hash TEXT PRIMARY KEY,
        enrollment_id TEXT NOT NULL REFERENCES enrollments(enrollment_id),
        stage TEXT NOT NULL,
        condition TEXT,
        block_index INTEGER NOT NULL CHECK (block_index IN (0, 1)),
        current_task_id TEXT,
        expires_at TEXT NOT NULL,
        revoked_at TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS comprehension_attempts (
        attempt_id TEXT PRIMARY KEY,
        enrollment_id TEXT NOT NULL REFERENCES enrollments(enrollment_id),
        study TEXT NOT NULL,
        idempotency_key TEXT NOT NULL UNIQUE,
        attempt_number INTEGER NOT NULL,
        correct_count INTEGER NOT NULL,
        question_count INTEGER NOT NULL,
        passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS task_trials (
        trial_id TEXT PRIMARY KEY,
        enrollment_id TEXT NOT NULL REFERENCES enrollments(enrollment_id),
        session_hash TEXT NOT NULL,
        task_id TEXT NOT NULL,
        block_index INTEGER NOT NULL CHECK (block_index IN (0, 1)),
        phase TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS task_responses (
        response_id TEXT PRIMARY KEY,
        enrollment_id TEXT NOT NULL REFERENCES enrollments(enrollment_id),
        trial_id TEXT NOT NULL REFERENCES task_trials(trial_id),
        task_id TEXT NOT NULL,
        phase TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        confidence INTEGER CHECK (confidence BETWEEN 0 AND 100),
        created_at TEXT NOT NULL,
        UNIQUE (trial_id, phase)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS query_versions (
        query_id TEXT PRIMARY KEY,
        owner_id TEXT,
        natural_language TEXT NOT NULL,
        interpreted_json TEXT NOT NULL,
        result_json TEXT,
        confirmed INTEGER NOT NULL DEFAULT 0 CHECK (confirmed IN (0, 1)),
        parent_query_id TEXT,
        status TEXT NOT NULL,
        lineage_json TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS canonical_events (
        event_id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        enrollment_id TEXT,
        session_hash TEXT,
        task_id TEXT,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS deletion_ledger (
        participant_code TEXT PRIMARY KEY,
        enrollment_id TEXT NOT NULL,
        requested_at TEXT NOT NULL,
        applied_at TEXT NOT NULL,
        qualtrics_status TEXT NOT NULL,
        payment_stage TEXT,
        counts_toward_cap INTEGER NOT NULL CHECK (counts_toward_cap IN (0, 1))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS integration_callbacks (
        callback_nonce_hash TEXT PRIMARY KEY,
        enrollment_id TEXT NOT NULL REFERENCES enrollments(enrollment_id),
        callback_type TEXT NOT NULL,
        from_stage TEXT NOT NULL,
        to_stage TEXT NOT NULL,
        survey_id TEXT NOT NULL,
        survey_version TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
)

INDEX_STATEMENTS = (
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_enrollment_reference
    ON enrollments(enrollment_reference)
    """,
)
