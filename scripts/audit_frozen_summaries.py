#!/usr/bin/env python3
"""Validate frozen LLM narratives and optionally record an AI-assisted evidence audit."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from hc_analytics.language.summaries import FEATURE_LABELS

FORBIDDEN_PHRASES = (
    "because of",
    "due to",
    "caused by",
    "helped",
    "higher",
    "lower ",
    "more ",
    "fewer",
    "older",
    "younger",
    "shap",
    "xgboost",
    "model family",
    "stability badge",
)


def _sentences(narrative: str) -> list[str]:
    return [part for part in re.split(r"(?<=[.!?])\s+", narrative.strip()) if part]


def validate_item(item: dict) -> list[str]:
    narrative = str(item.get("candidate_narrative") or "")
    template = str(item.get("template_narrative") or "")
    claims = item.get("claims") or []
    issues: list[str] = []
    sentences = _sentences(narrative)

    if item.get("provider") != "openai":
        issues.append(f"provider is {item.get('provider')!r}, expected 'openai'")
    if len(sentences) != 3:
        issues.append(f"expected 3 sentences, found {len(sentences)}")

    expected_risks = re.findall(r"\b(?:100|\d{1,2})%", template)
    actual_risks = re.findall(r"\b(?:100|\d{1,2})%", narrative)
    if actual_risks != expected_risks:
        issues.append(f"risk percentages differ: expected {expected_risks}, found {actual_risks}")
    numeric_residue = re.sub(r"\b(?:100|\d{1,2})%", "", narrative).replace("30-day", "thirty-day")
    if re.search(r"\d", numeric_residue):
        issues.append("contains a number other than an outcome risk percentage")

    lowered = narrative.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lowered:
            issues.append(f"contains forbidden phrase {phrase!r}")

    if len(claims) != 9:
        issues.append(f"expected 9 grounded claims, found {len(claims)}")
    elif len(sentences) == 3:
        for index, claim in enumerate(claims):
            sentence = sentences[index // 3].lower()
            source_fields = claim.get("source_fields") or []
            if len(source_fields) != 1:
                issues.append(f"claim {index + 1} does not have exactly one source field")
                continue
            field = source_fields[0]
            label = FEATURE_LABELS.get(field, field.replace("_", " ")).lower()
            if label not in sentence:
                issues.append(f"claim {index + 1} is missing driver label {label!r}")
            statement = str(claim.get("statement") or "")
            expected_words = ("raised", "raising") if " increased " in f" {statement} " else ("lowered", "lowering")
            if not any(word in sentence for word in expected_words):
                issues.append(f"claim {index + 1} is missing direction {expected_words}")

    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--queue",
        type=Path,
        default=REPO_ROOT / "study" / "adjudication_queue.json",
    )
    parser.add_argument("--record-decisions", action="store_true")
    parser.add_argument("--reviewer", default="Codex AI evidence audit")
    args = parser.parse_args()

    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    failures: dict[str, list[str]] = {}
    for item in queue.get("items", []):
        issues = validate_item(item)
        if issues:
            failures[item.get("case_id", "<unknown>")] = issues

    if failures:
        for case_id, issues in failures.items():
            print(f"{case_id}: {'; '.join(issues)}")
        raise SystemExit(f"Evidence audit failed for {len(failures)} item(s).")

    print(f"Evidence audit passed for {len(queue.get('items', []))} item(s).")
    if not args.record_decisions:
        return

    reviewed_at = datetime.now(timezone.utc).isoformat()
    note = (
        "AI-assisted evidence audit verified three outcomes, exact risk percentages, all grounded "
        "driver labels and directions, and absence of prohibited causal/model jargon. Independent "
        "human co-review remains required before confirmatory use."
    )
    for item in queue.get("items", []):
        item["decision"] = "accept_candidate"
        item["reviewer"] = args.reviewer
        item["reviewer_type"] = "ai_assisted"
        item["reviewed_at"] = reviewed_at
        item["notes"] = note
    queue["schema_version"] = "1.1"
    queue["ai_evidence_audit"] = "complete"
    queue["ai_evidence_audit_at"] = reviewed_at
    queue["human_review"] = "pending"
    args.queue.write_text(json.dumps(queue, indent=2), encoding="utf-8")
    print(f"Recorded AI-assisted decisions in {args.queue}.")


if __name__ == "__main__":
    main()
