"""Destructive PostgreSQL persistence smoke test for an empty test database.

Usage:
  HC_DATABASE_URL=postgresql://... python scripts/postgres_smoke.py

Never point this script at a participant or shared database.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from hc_analytics.persistence.repository import (
    CapExceeded,
    StateConflict,
    StudyRepository,
)


def main() -> None:
    dsn = os.environ.get("HC_DATABASE_URL")
    if not dsn:
        raise SystemExit("HC_DATABASE_URL is required")
    repository = StudyRepository("postgres", dsn)
    try:
        repository.ensure_schema()
    except Exception:
        runtime_ddl_refused = True
    else:
        runtime_ddl_refused = False
    assert runtime_ddl_refused
    repository.migrate()
    repository.ensure_schema()

    def allocate(index: int):
        worker = StudyRepository("postgres", dsn)
        try:
            return worker.launch(
                namespace="test",
                study="study1",
                survey_id="SV_POSTGRES_SMOKE",
                survey_version="test-only",
                nonce=f"postgres-race-{index}",
                enrollment_reference=None,
                environment="local",
                purpose="study_launch",
                ttl_seconds=60,
                cap_per_study=3,
                cap_total=3,
            )
        except CapExceeded:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        allocations = [item for item in pool.map(allocate, range(8)) if item]
    codes = {item["participant_code"] for item in allocations}
    assert len(allocations) == 3
    assert len(codes) == 3
    assert all(code.startswith("TEST-") for code in codes)

    issued = allocations[0]
    repository.consume_launch_token(
        issued["launch_token"],
        environment="local",
        purpose="study_launch",
        session_ttl_seconds=60,
    )
    try:
        repository.consume_launch_token(
            issued["launch_token"],
            environment="local",
            purpose="study_launch",
            session_ttl_seconds=60,
        )
    except StateConflict:
        replay_rejected = True
    else:
        replay_rejected = False
    assert replay_rejected

    repository.store_query(
        query_id="postgres-owner-test",
        owner_id=issued["enrollment_id"],
        natural_language="synthetic smoke query",
        interpreted_json="{}",
        parent_query_id=None,
        status="interpreted",
        lineage_json=None,
    )
    restarted = StudyRepository("postgres", dsn)
    restarted.ensure_schema()
    assert restarted.load_query("postgres-owner-test", owner_id=issued["enrollment_id"]) is not None
    assert restarted.load_query("postgres-owner-test", owner_id="other") is None

    print(
        {
            "postgres_schema": "ok",
            "runtime_ddl_refused": runtime_ddl_refused,
            "concurrent_allocations": len(allocations),
            "unique_codes": len(codes),
            "token_replay_rejected": replay_rejected,
            "restart_query_read": True,
            "query_owner_isolated": True,
        }
    )


if __name__ == "__main__":
    main()
