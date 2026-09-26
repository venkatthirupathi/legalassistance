"""
core/comparator.py

Compares two contracts (two versions of the same agreement, or two
different agreements of the same type) and returns structured differences,
inconsistencies, and a risk-shift assessment.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, ValidationError

from core_config import get_chat_model
from core_prompts import COMPARISON_PROMPT

# Cap per-document input to keep comparison calls affordable & within
# context limits on longer contracts. Generous enough for most freelance /
# NDA / employment agreements.
_MAX_CHARS_PER_DOC = 12000


class DifferenceItem(BaseModel):
    topic: str = ""
    document_a_position: str = "Not addressed"
    document_b_position: str = "Not addressed"
    materiality: str = "Medium"
    analysis: str = ""


class ComparisonResult(BaseModel):
    summary: str = ""
    differences: list[DifferenceItem] = Field(default_factory=list)
    risk_shift: str = ""


class ComparisonError(Exception):
    pass


def _extract_json(raw_text: str) -> dict:
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        text = text[first_brace : last_brace + 1]
    return json.loads(text)


def compare_documents(
    doc_a_text: str,
    doc_a_name: str,
    doc_b_text: str,
    doc_b_name: str,
) -> ComparisonResult:
    """Runs the LLM-based comparison and returns a validated structured result."""
    if not doc_a_text.strip() or not doc_b_text.strip():
        raise ValueError("Both documents must contain text to compare.")

    truncated_a = doc_a_text[:_MAX_CHARS_PER_DOC]
    truncated_b = doc_b_text[:_MAX_CHARS_PER_DOC]

    llm = get_chat_model(temperature=0.1)
    prompt = COMPARISON_PROMPT.format(
        doc_a_name=doc_a_name,
        document_a_text=truncated_a,
        doc_b_name=doc_b_name,
        document_b_text=truncated_b,
    )

    last_error = None
    for attempt in range(2):
        try:
            response = llm.invoke(prompt)
            parsed = _extract_json(response.content or "")
            return ComparisonResult(**parsed)
        except (json.JSONDecodeError, ValidationError, AttributeError) as e:
            last_error = e
            if attempt == 0:
                prompt += (
                    "\n\nIMPORTANT: Return ONLY the JSON object, no markdown "
                    "fences, no commentary."
                )
                continue
        except Exception as e:
            raise ComparisonError(f"Comparison failed due to an API error: {e}") from e

    raise ComparisonError(
        "The comparison model returned data that couldn't be parsed after "
        f"retrying ({last_error.__class__.__name__}). Please try again."
    )
