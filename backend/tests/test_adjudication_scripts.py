from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
APPLY_SCRIPT = REPO_ROOT / "scripts" / "apply_adjudication.py"


def _write_inputs(tmp_path: Path, *, reviewer_type: str) -> tuple[Path, Path]:
    queue_path = tmp_path / "queue.json"
    summaries_path = tmp_path / "summaries.json"
    queue_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "bene_id": "B1",
                        "analytic_year": 2022,
                        "provider": "openai",
                        "template_narrative": "Template narrative.",
                        "candidate_narrative": "Candidate narrative.",
                        "status": "pending",
                        "decision": "accept_candidate",
                        "reviewer": "Reviewer",
                        "reviewer_type": reviewer_type,
                        "reviewed_at": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    summaries_path.write_text(
        json.dumps(
            {
                "summaries": {
                    "B1:2022": {
                        "narrative": "Template narrative.",
                        "provider": "template",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return queue_path, summaries_path


def _run_apply(queue_path: Path, summaries_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(APPLY_SCRIPT),
            "--queue",
            str(queue_path),
            "--summaries",
            str(summaries_path),
            *extra,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_ai_audit_applies_candidate_but_preserves_human_review_flag(tmp_path: Path) -> None:
    queue_path, summaries_path = _write_inputs(tmp_path, reviewer_type="ai_assisted")
    result = _run_apply(queue_path, summaries_path)
    assert result.returncode == 0, result.stderr

    summaries = json.loads(summaries_path.read_text(encoding="utf-8"))
    assert summaries["summaries"]["B1:2022"]["narrative"] == "Candidate narrative."
    assert summaries["technical_adjudication_required"] is False
    assert summaries["human_adjudication_required"] is True
    assert summaries["adjudication_required"] is True


def test_human_review_satisfies_require_complete(tmp_path: Path) -> None:
    queue_path, summaries_path = _write_inputs(tmp_path, reviewer_type="human")
    result = _run_apply(queue_path, summaries_path, "--require-complete")
    assert result.returncode == 0, result.stderr

    summaries = json.loads(summaries_path.read_text(encoding="utf-8"))
    assert summaries["human_adjudication_required"] is False
    assert summaries["adjudication_required"] is False
