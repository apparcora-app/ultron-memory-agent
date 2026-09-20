"""
security/sanitizer.py — Boundary PII & Secret Redaction Engine.

Provides:
  1. Automated deterministic pre-serialization scrubbing for logs, spans, DLQ records,
     and error traces.
  2. Strict regex patterns detecting:
     - US Social Security Numbers (SSN / ITIN): \\b\\d{3}-\\d{2}-\\d{4}\\b -> [REDACTED_SSN]
     - Employer Identification Numbers (EIN): \\b\\d{2}-\\d{7}\\b -> [REDACTED_EIN]
     - Credit Card Numbers / PANs (13-16 digits with optional dashes/spaces) -> [REDACTED_CC]
     - API Keys & Auth Tokens (Anthropic, OpenAI, Bearer tokens, JWTs, generic secrets) -> [REDACTED_TOKEN]
  3. Recursive object sanitization for dicts, lists, tuples, and string payloads.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple, Union


# ── Compiled Regular Expressions for Sensitive Patterns ───────────────────────

# US Social Security Number (SSN) / ITIN: 3 digits, hyphen, 2 digits, hyphen, 4 digits
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Employer Identification Number (EIN): 2 digits, hyphen, 7 digits
EIN_PATTERN = re.compile(r"\b\d{2}-\d{7}\b")

# Credit Card Numbers / PANs:
# 13 to 16 digits, with optional single spaces or hyphens between 4-digit groups
CC_PATTERN = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b|\b\d{13,16}\b")

# API Keys & Auth Tokens
# Matches Anthropic, OpenAI, Bearer headers, JWTs, and key=val assignments
ANTHROPIC_KEY_PATTERN = re.compile(r"\bsk-ant-[a-zA-Z0-9_\-\.]{10,}\b")
OPENAI_KEY_PATTERN = re.compile(r"\bsk-[a-zA-Z0-9_\-\.]{20,}\b")
BEARER_TOKEN_PATTERN = re.compile(r"\bBearer\s+[a-zA-Z0-9_\-\.\~]{15,}\b", re.IGNORECASE)
JWT_PATTERN = re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b")
GENERIC_SECRET_PATTERN = re.compile(
    r"(?i)\b(?:api[_-]?key|secret(?:[_-]?key)?|access[_-]?token|auth[_-]?token|private[_-]?key)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{16,})['\"]?"
)


def luhn_check(card_number_str: str) -> bool:
    """Verifies whether a numeric string satisfies the Luhn algorithm checksum."""
    digits = [int(c) for c in card_number_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, d in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = d * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += d
    return checksum % 10 == 0


class DataSanitizer:
    """
    High-performance boundary sanitizer intercepting raw strings and complex data payloads.
    """

    def __init__(self) -> None:
        self.ssn_pattern = SSN_PATTERN
        self.ein_pattern = EIN_PATTERN
        self.cc_pattern = CC_PATTERN
        self.anthropic_key_pattern = ANTHROPIC_KEY_PATTERN
        self.openai_key_pattern = OPENAI_KEY_PATTERN
        self.bearer_token_pattern = BEARER_TOKEN_PATTERN
        self.jwt_pattern = JWT_PATTERN
        self.generic_secret_pattern = GENERIC_SECRET_PATTERN

    def sanitize_text(self, text: str) -> str:
        """
        Deterministically scrubs all sensitive PII and secret patterns from a string.
        """
        if not text or not isinstance(text, str):
            return text

        scrubbed = text

        # 1. API Keys and Tokens (scrub before digits/hyphen patterns)
        scrubbed = self.anthropic_key_pattern.sub("[REDACTED_TOKEN]", scrubbed)
        scrubbed = self.openai_key_pattern.sub("[REDACTED_TOKEN]", scrubbed)
        scrubbed = self.bearer_token_pattern.sub("Bearer [REDACTED_TOKEN]", scrubbed)
        scrubbed = self.jwt_pattern.sub("[REDACTED_TOKEN]", scrubbed)

        # Scrub generic secret key assignments like api_key = "..."
        def _replace_generic_secret(match: re.Match) -> str:
            full = match.group(0)
            secret_val = match.group(1)
            return full.replace(secret_val, "[REDACTED_TOKEN]")

        scrubbed = self.generic_secret_pattern.sub(_replace_generic_secret, scrubbed)

        # 2. SSN / ITIN
        scrubbed = self.ssn_pattern.sub("[REDACTED_SSN]", scrubbed)

        # 3. EIN
        scrubbed = self.ein_pattern.sub("[REDACTED_EIN]", scrubbed)

        # 4. Credit Card Numbers
        # Replace matches that either match 16-digit blocks or pass Luhn validation
        def _replace_cc(match: re.Match) -> str:
            candidate = match.group(0)
            digits = re.sub(r"\D", "", candidate)
            # If 13-16 digits and Luhn valid, or formatted 16 digits
            if len(digits) in (13, 14, 15, 16) and (len(digits) == 16 or luhn_check(digits)):
                return "[REDACTED_CC]"
            return candidate

        scrubbed = self.cc_pattern.sub(_replace_cc, scrubbed)

        return scrubbed

    def sanitize_payload(self, payload: Any) -> Any:
        """
        Recursively traverses nested dictionaries, lists, and tuples,
        scrubbing all string values and string keys.
        """
        if isinstance(payload, str):
            return self.sanitize_text(payload)

        elif isinstance(payload, dict):
            sanitized_dict: Dict[str, Any] = {}
            for k, v in payload.items():
                sanitized_key = self.sanitize_text(str(k))
                sanitized_dict[sanitized_key] = self.sanitize_payload(v)
            return sanitized_dict

        elif isinstance(payload, list):
            return [self.sanitize_payload(item) for item in payload]

        elif isinstance(payload, tuple):
            return tuple(self.sanitize_payload(item) for item in payload)

        elif hasattr(payload, "model_dump") and callable(payload.model_dump):
            # Pydantic v2 support
            return self.sanitize_payload(payload.model_dump())

        elif hasattr(payload, "__dict__"):
            return self.sanitize_payload(payload.__dict__)

        return payload


# Global default sanitizer
default_sanitizer = DataSanitizer()


def sanitize_text(text: str) -> str:
    return default_sanitizer.sanitize_text(text)


def sanitize_payload(payload: Any) -> Any:
    return default_sanitizer.sanitize_payload(payload)
