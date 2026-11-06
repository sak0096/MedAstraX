"""Strip identifiers and answer keys before a payload leaves the server."""

from __future__ import annotations

from typing import Any, Dict, Iterable

PROTECTED_KEYS = {
    "correct_ranking",
    "correct_index",
    "active_manipulation",
    "active_manipulations",
    "recommendation_correctness",
    "manipulation_catalog",
    "manipulation_applied",
    "manipulation_type",
    "ground_truth",
    "ground_truth_id",
    "prolific_id",
    "prolific_pid",
    "email",
    "ip",
    "ip_address",
    "geolocation",
    "authorization",
    "cookie",
    "launch_token",
    "session_cookie",
    "session_hash",
    "token",
    "access_token",
}

PROTECTED_PREFIXES = ("_",)


def redact_mapping(payload: Dict[str, Any], *, extra_keys: Iterable[str] = ()) -> Dict[str, Any]:
    blocked = PROTECTED_KEYS | set(extra_keys)
    cleaned: Dict[str, Any] = {}
    for key, value in payload.items():
        if key in blocked or key.startswith(PROTECTED_PREFIXES):
            continue
        if isinstance(value, dict):
            cleaned[key] = redact_mapping(value)
        elif isinstance(value, list):
            cleaned[key] = [
                redact_mapping(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            cleaned[key] = value
    return cleaned


def contains_protected_key(payload: Any) -> bool:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in PROTECTED_KEYS or str(key).startswith("_"):
                return True
            if contains_protected_key(value):
                return True
        return False
    if isinstance(payload, list):
        return any(contains_protected_key(item) for item in payload)
    return False
