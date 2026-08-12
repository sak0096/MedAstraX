"""OpenAI-compatible chat provider for freeze-time grounded narrative polishing."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import httpx

from hc_analytics.config import Settings
from hc_analytics.explainability.bundles import EvidenceBundle
from hc_analytics.language.summaries import FEATURE_LABELS, build_template_narrative

PROMPT_VERSION = "grounded-polish-v1"


def _claim_lines(bundle: EvidenceBundle) -> list[str]:
    lines = []
    for claim in bundle.grounded.claims:
        sources = ", ".join(FEATURE_LABELS.get(field, field) for field in claim.source_fields)
        lines.append(f"- {claim.statement} [sources: {sources}]")
    return lines


def build_polish_prompt(bundle: EvidenceBundle, template_narrative: str) -> Dict[str, str]:
    system = (
        "You rewrite healthcare analytics summaries for care managers. "
        "Use ONLY the provided facts and source fields. Do not invent numbers, diagnoses, "
        "or events. Keep the meaning of every claim. Write 2-4 short sentences in plain English. "
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
        response = client.post(_endpoint(settings), headers=headers, json=payload)
        response.raise_for_status()
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
