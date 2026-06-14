"""
LLM prompt versioning and response validation for SecureNet SOC.

Stores prompt templates externally so they can be iterated without code deploys.
Validates LLM responses against expected schemas to reject malformed output.

Usage:
    from shared.llm_config import get_prompt, validate_llm_response, LLM_PROMPT_VERSION

    system_prompt = get_prompt("system")
    user_prompt = get_prompt("user", alert=alert_dict)
    validated = validate_llm_response(raw_json)
"""

import os
import json
import logging
from typing import Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# Current prompt version — update when modifying prompts
LLM_PROMPT_VERSION = "v2"

# ---------------------------------------------------------------------------
# Prompt templates (externalized for iteration without code changes)
# ---------------------------------------------------------------------------

PROMPTS = {
    "v1": {
        "system": (
            "You are a cybersecurity IDS analyst. Analyze network traffic alerts "
            "and classify them. Respond ONLY with valid JSON — no markdown, no explanation "
            'outside the JSON.\n\n'
            'Output exactly: {"attack_type":"string","severity":"low|medium|high|critical",'
            '"explanation":"string (2 sentences max)","recommendation":"string (1 sentence)"}'
        ),
        "user": (
            "Alert for IP {src_ip}:\n"
            "- Packets/sec: {pps:.1f}\n"
            "- Bytes/sec: {bps:.1f}\n"
            "- Avg Packet Size: {avg_size:.0f} bytes\n"
            "- ML Confidence: {confidence:.1%}\n\n"
            "Classify the attack type, severity, explain why, recommend action."
        ),
    },
    "v2": {
        "system": (
            "You are a senior SOC analyst for an Intrusion Detection System. "
            "Analyze the network traffic alert below and classify the threat.\n\n"
            "RULES:\n"
            "1. Respond ONLY with valid JSON — no markdown, no explanation outside JSON.\n"
            "2. severity MUST be one of: low, medium, high, critical\n"
            "3. explanation must be 1-2 sentences maximum\n"
            "4. recommendation must be 1 actionable sentence\n\n"
            "OUTPUT FORMAT:\n"
            '{"attack_type":"string","severity":"low|medium|high|critical",'
            '"explanation":"string","recommendation":"string"}'
        ),
        "user": (
            "ALERT — Source IP: {src_ip}\n"
            "Packets/sec: {pps:.1f} | Bytes/sec: {bps:.1f}\n"
            "Avg Packet Size: {avg_size:.0f}B | ML Confidence: {confidence:.1%}\n"
            "Classify this traffic pattern."
        ),
    },
}


def get_prompt(prompt_type: str, version: str = LLM_PROMPT_VERSION, **kwargs) -> str:
    """
    Get a prompt template by type and version, optionally formatted with kwargs.

    Args:
        prompt_type: 'system' or 'user'
        version: Prompt version (defaults to current)
        **kwargs: Values to format into the user prompt (src_ip, pps, bps, avg_size, confidence)
    """
    prompts = PROMPTS.get(version, PROMPTS[LLM_PROMPT_VERSION])
    template = prompts.get(prompt_type, "")

    if kwargs and prompt_type == "user":
        return template.format(**kwargs)
    return template


def build_user_prompt_from_alert(alert: dict, version: str = LLM_PROMPT_VERSION) -> str:
    """Build a formatted user prompt from an alert dict."""
    return get_prompt(
        "user",
        version=version,
        src_ip=alert.get("src_ip", "unknown"),
        pps=float(alert.get("packets_per_sec", 0)),
        bps=float(alert.get("bytes_per_sec", 0)),
        avg_size=float(alert.get("avg_packet_size", 0)),
        confidence=float(alert.get("prediction_confidence", 0)),
    )


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------

VALID_SEVERITIES = {"low", "medium", "high", "critical"}


class LLMAnalysisResponse(BaseModel):
    """Validated LLM analysis response."""
    attack_type: str = Field(..., min_length=1, max_length=100)
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    explanation: str = Field(..., min_length=1, max_length=500)
    recommendation: str = Field(..., min_length=1, max_length=500)

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in VALID_SEVERITIES:
            raise ValueError(f"severity must be one of {VALID_SEVERITIES}")
        return v


def validate_llm_response(raw_json: str | dict) -> Optional[dict]:
    """
    Validate and sanitize an LLM response against the expected schema.

    Returns:
        Validated dict if valid, None if malformed.
    """
    try:
        if isinstance(raw_json, str):
            # Handle markdown code blocks
            text = raw_json.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            data = json.loads(text)
        else:
            data = raw_json

        validated = LLMAnalysisResponse(**data)
        return validated.model_dump()

    except Exception as e:
        logger.warning(f"LLM response validation failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Model fallback chain configuration
# ---------------------------------------------------------------------------

if os.getenv("GROQ_API_KEY"):
    MODEL_FALLBACK_CHAIN = [
        {"model": "llama-3.3-70b-versatile", "cost_tier": "free"},
        {"model": "llama3-8b-8192", "cost_tier": "free"},
        {"model": "mixtral-8x7b-32768", "cost_tier": "free"},
    ]
else:
    MODEL_FALLBACK_CHAIN = [
        {"model": "openai/gpt-4o-mini", "cost_tier": "low"},
        {"model": "meta-llama/llama-3-8b-instruct:free", "cost_tier": "free"},
    ]


def get_model_for_attempt(attempt: int) -> str:
    """Get the model to use for a given retry attempt (fallback chain)."""
    if attempt < len(MODEL_FALLBACK_CHAIN):
        return MODEL_FALLBACK_CHAIN[attempt]["model"]
    return MODEL_FALLBACK_CHAIN[-1]["model"]
