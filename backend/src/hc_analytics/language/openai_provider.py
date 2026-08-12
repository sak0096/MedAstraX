"""OpenAI-compatible chat provider for freeze-time grounded narrative polishing."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import httpx

from hc_analytics.config import Settings
from hc_analytics.explainability.bundles import EvidenceBundle
from hc_analytics.language.summaries import FEATURE_LABELS, build_template_narrative

PROMPT_VERSION = "grounded-polish-v4"
NON_RETRYABLE_429_CODES = {"credit_balance_exhausted", "insufficient_quota"}


def _claim_lines(bundle: EvidenceBundle) -> list[str]:
    lines = []
    for claim in bundle.grounded.claims:
        sources = ", ".join(FEATURE_LABELS.get(field, field) for field in claim.source_fields)
        lines.append(f"- {claim.statement} [sources: {sources}]")
    return lines


def build_polish_prompt(bundle: EvidenceBundle, template_narrative: str) -> Dict[str, str]:
    system = (
        "You rewrite healthcare analytics summaries for care managers. Use ONLY the template "
        "and allowed claims. Write exactly three short sentences in plain English: one each for "
        "hospitalization, high utilization, and elevated cost, in that order. Preserve every "
        "risk percentage and every driver label and raised/lowered direction supplied in the "
        "template. Do not include the raw driver values in the narrative; they remain available "
        "in the linked evidence details. "
        "Describe effects on the prediction, not causes of a person's health or utilization. "
        "Do not turn a contribution direction into an unsupported characterization such as high, "
        "low, higher, lower, more, fewer, older, or younger. Do not use causal phrases such as "
        "because of, due to, caused by, or helped. Apart from a number embedded in a supplied "
        "driver label (for example, 30-day readmissions), the only numbers in the narrative must "
        "be the three supplied risk percentages. Do not invent numbers, diagnoses, or events. "
        "Do not mention SHAP, XGBoost, model family names, or stability badges."
    )
    user = (
        f"Beneficiary ID: {bundle.bene_id}\n"
        f"Analytic year: {bundle.analytic_year}\n\n"
        f"Template draft:\n{template_narrative}\n\n"
        "Allowed claims (must remain supported):\n"
        + "\n".join(_claim_lines(bundle))
        + "\n\nReturn JSON only: {\"narrative\": \"...\"}"
    )
    return {"system": system, "user": user, "prompt_version": PROMPT_VERSION}


def _endpoint(settings: Settings) -> str:
    provider = (settings.llm_provider or "").strip().lower()
    if provider in {"openai", "openai_compatible"}:
        return "https://api.openai.com/v1/chat/completions"
    if provider in {"azure", "azure_openai"}:
        raise ValueError("Azure OpenAI requires a custom endpoint; set HC_LLM_PROVIDER=openai_compatible and pass full URL via model config.")
    # Allow custom base URL style providers that still speak OpenAI chat schema.
    if provider.startswith("http://") or provider.startswith("https://"):
        return provider.rstrip("/") + "/chat/completions"
    return "https://api.openai.com/v1/chat/completions"


def _error_details(response: httpx.Response) -> tuple[Optional[str], str]:
    try:
        error = response.json().get("error", {})
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None, "No structured error message was returned."
    code = error.get("code") or error.get("type")
    message = str(error.get("message") or "No error message was returned.")
    return str(code) if code else None, message


def _is_retryable(response: httpx.Response) -> bool:
    if response.status_code == 429:
        code, _ = _error_details(response)
        return code not in NON_RETRYABLE_429_CODES
    return response.status_code in {408, 409, 500, 502, 503, 504}


def _retry_delay_seconds(
    response: httpx.Response,
    *,
    attempt_index: int,
    base_seconds: float,
    cap_seconds: float,
) -> float:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return min(cap_seconds, max(0.0, float(retry_after)))
        except ValueError:
            pass
    return min(cap_seconds, base_seconds * (2**attempt_index))


def _raise_sanitized_api_error(response: httpx.Response) -> None:
    code, message = _error_details(response)
    code_label = f", code={code}" if code else ""
    raise RuntimeError(
        f"LLM request failed (HTTP {response.status_code}{code_label}): {message}"
    )


def polish_narrative_with_llm(
    bundle: EvidenceBundle,
    *,
    settings: Settings,
    timeout_s: float = 60.0,
) -> Dict[str, Any]:
    if not (settings.llm_api_key and settings.llm_model):
        raise RuntimeError("LLM provider is not configured (HC_LLM_API_KEY / HC_LLM_MODEL).")

    template = build_template_narrative(bundle)
    prompt = build_polish_prompt(bundle, template)
    payload = {
        "model": settings.llm_model,
        "temperature": float(settings.llm_temperature),
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"]},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=timeout_s) as client:
        response: Optional[httpx.Response] = None
        max_attempts = max(1, settings.llm_max_attempts)
        for attempt_index in range(max_attempts):
            response = client.post(_endpoint(settings), headers=headers, json=payload)
            try:
                response.raise_for_status()
                break
            except httpx.HTTPStatusError:
                if attempt_index + 1 >= max_attempts or not _is_retryable(response):
                    _raise_sanitized_api_error(response)
                time.sleep(
                    _retry_delay_seconds(
                        response,
                        attempt_index=attempt_index,
                        base_seconds=max(0.0, settings.llm_retry_base_seconds),
                        cap_seconds=max(0.0, settings.llm_retry_cap_seconds),
                    )
                )
        if response is None:  # pragma: no cover - guarded by max_attempts >= 1
            raise RuntimeError("LLM request did not produce a response.")
        body = response.json()

    content = body["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    narrative = str(parsed.get("narrative") or "").strip()
    if not narrative:
        raise RuntimeError("LLM returned an empty narrative.")
    return {
        "narrative": narrative,
        "template_narrative": template,
        "prompt_version": PROMPT_VERSION,
        "raw_response": body,
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
    }
