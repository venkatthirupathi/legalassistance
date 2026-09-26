"""
core/guardrails.py

Two-stage validation so we don't waste LLM calls (or embarrass ourselves)
analyzing a recipe as if it were a contract:

  Stage 1 — fast, free, keyword/heuristic scoring on the raw text.
  Stage 2 — if Stage 1 is ambiguous, a cheap LLM classification call.

Also includes generic input sanitation helpers (empty prompts, oversized
input, etc.) used across the app.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core_prompts import DOCUMENT_CLASSIFIER_PROMPT

# Words/phrases that show up disproportionately often in legal agreements.
_LEGAL_SIGNAL_TERMS = [
    r"\bwhereas\b",
    r"\bhereinafter\b",
    r"\bindemnif\w*\b",
    r"\bliabilit\w*\b",
    r"\bgoverning law\b",
    r"\bjurisdiction\b",
    r"\bconfidential\w*\b",
    r"\btermination\b",
    r"\bagreement\b",
    r"\bparty\b|\bparties\b",
    r"\bshall\b",
    r"\bwarrant\w*\b",
    r"\bnon-compete\b|\bnoncompete\b",
    r"\bintellectual property\b",
    r"\beffective date\b",
    r"\bin witness whereof\b",
    r"\bbreach\b",
    r"\bgoverning\b",
    r"\bnotwithstanding\b",
    r"\bcovenant\w*\b",
]

_MIN_LENGTH_CHARS = 200
_HEURISTIC_HIT_THRESHOLD = 3  # distinct signal terms required to auto-pass
_HEURISTIC_AMBIGUOUS_FLOOR = 1  # below this, auto-reject without LLM call


@dataclass
class GuardrailResult:
    is_legal_document: bool
    confidence: str  # "heuristic" or "llm"
    reason: str
    signal_hits: int = 0


def _heuristic_score(text: str) -> int:
    lowered = text.lower()
    hits = 0
    for pattern in _LEGAL_SIGNAL_TERMS:
        if re.search(pattern, lowered):
            hits += 1
    return hits


def validate_not_empty(text: str, field_name: str = "input") -> None:
    """Raise ValueError if a user-provided string is empty/whitespace."""
    if text is None or not text.strip():
        raise ValueError(f"Your {field_name} appears to be empty. Please provide some text.")


def check_is_legal_document(text: str, llm=None) -> GuardrailResult:
    """
    Determines whether `text` is plausibly a legal/contractual document.

    Cheap heuristic first; only escalates to an LLM call when the heuristic
    is genuinely ambiguous, to save API cost/latency on obvious cases.
    """
    if len(text.strip()) < _MIN_LENGTH_CHARS:
        return GuardrailResult(
            is_legal_document=False,
            confidence="heuristic",
            reason=(
                "The document is too short to be a meaningful legal "
                "agreement (fewer than 200 characters of content)."
            ),
        )

    hits = _heuristic_score(text)

    if hits >= _HEURISTIC_HIT_THRESHOLD:
        return GuardrailResult(
            is_legal_document=True,
            confidence="heuristic",
            reason=f"Detected {hits} legal-language signal terms.",
            signal_hits=hits,
        )

    if hits < _HEURISTIC_AMBIGUOUS_FLOOR:
        return GuardrailResult(
            is_legal_document=False,
            confidence="heuristic",
            reason=(
                "The document doesn't contain typical legal/contractual "
                "language (e.g. 'agreement', 'liability', 'termination', "
                "'shall'). It looks like it may not be a legal document."
            ),
            signal_hits=hits,
        )

    # Ambiguous zone (1-2 hits): fall back to LLM if available
    if llm is None:
        # No LLM handy (e.g. offline test) — be lenient rather than block
        return GuardrailResult(
            is_legal_document=True,
            confidence="heuristic",
            reason=f"Ambiguous heuristic score ({hits} hits); allowing by default.",
            signal_hits=hits,
        )

    try:
        sample = text[:3000]  # keep the classification call cheap
        response = llm.invoke(
            DOCUMENT_CLASSIFIER_PROMPT.format(document_excerpt=sample)
        )
        content = (response.content or "").strip().upper()
        is_legal = content.startswith("YES")
        return GuardrailResult(
            is_legal_document=is_legal,
            confidence="llm",
            reason=(
                "The AI classifier determined this does not appear to be a "
                "legal or contractual document."
                if not is_legal
                else "The AI classifier confirmed this appears to be a legal document."
            ),
            signal_hits=hits,
        )
    except Exception:
        # If the LLM call itself fails, don't hard-block the user — fall
        # back to a lenient heuristic decision and let downstream analysis
        # surface any real issues.
        return GuardrailResult(
            is_legal_document=hits >= _HEURISTIC_AMBIGUOUS_FLOOR,
            confidence="heuristic-fallback",
            reason="Could not reach the AI classifier; used heuristic fallback.",
            signal_hits=hits,
        )
