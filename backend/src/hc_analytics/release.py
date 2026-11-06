"""Participant-release manifest verification."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from hc_analytics.config import Settings, get_settings


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_blockers(settings: Settings | None = None) -> list[str]:
    runtime = settings or get_settings()
    path = runtime.release_manifest
    if not path.is_file():
        return ["Release manifest is missing."]
    try:
        manifest: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["Release manifest is unreadable."]
    blockers: list[str] = []
    if manifest.get("schema") != "medastrax-release-v1":
        blockers.append("Release manifest schema is not supported.")
    for field in (
        "code_commit",
        "image_digest",
        "configuration_version",
        "schema_version",
        "assignment_version",
        "survey_version",
        "scoring_version",
    ):
        if not str(manifest.get(field) or "").strip():
            blockers.append(f"Release manifest field {field} is missing.")
    if not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("code_commit") or "")):
        blockers.append("Release manifest code commit is not a full SHA-1.")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(manifest.get("image_digest") or "")):
        blockers.append("Release manifest image digest is not immutable.")
    if manifest.get("human_adjudication_status") != "complete":
        blockers.append("Human adjudication is not complete.")
    if manifest.get("participant_release_approved") is not True:
        blockers.append("Participant release is not approved.")
    approvals = manifest.get("approvals")
    required_approvals = {
        "pi_release",
        "reviewed_source_comparison",
        "human_adjudication",
        "survey_branch_validation",
        "azure_security_operations",
    }
    approved_roles = {
        str(item.get("role"))
        for item in approvals or []
        if isinstance(item, dict)
        and item.get("status") == "approved"
        and str(item.get("evidence_ref") or "").strip()
    }
    missing_approvals = sorted(required_approvals - approved_roles)
    if missing_approvals:
        blockers.append("Release approvals are incomplete: " + ", ".join(missing_approvals))
    assets = manifest.get("assets")
    if not isinstance(assets, list) or not assets:
        blockers.append("Release manifest has no assets.")
        return blockers
    root = runtime.repo_root.resolve()
    for entry in assets:
        if not isinstance(entry, dict):
            blockers.append("Release manifest contains an invalid asset entry.")
            continue
        relative = str(entry.get("path") or "")
        expected = str(entry.get("sha256") or "")
        candidate = (root / relative).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            blockers.append(f"Release asset is missing: {relative}")
            continue
        if len(expected) != 64 or _sha256(candidate) != expected:
            blockers.append(f"Release asset hash mismatch: {relative}")
    return blockers
