"""
core/analyzer.py

Orchestrates the two full-document analyses:
  - Plain-English Explainer (free text)
  - Risk & Obligation Radar (structured JSON -> pydantic models)

Also exposes the RAG-based Q&A call. Every LLM call here is wrapped with
defensive parsing: if the model returns malformed JSON (rare but it
happens), we retry once with a stricter reminder before giving up
gracefully instead of crashing the Streamlit app.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, ValidationError

from core_config import get_chat_model
from core_prompts import (
    PLAIN_ENGLISH_SUMMARY_PROMPT,
    QA_SYSTEM_PROMPT,
    RISK_RADAR_PROMPT,
)
from core_rag import format_chunks_as_context, retrieve_relevant_chunks


# ---------------------------------------------------------------------------
# Structured output models
# ---------------------------------------------------------------------------
class RiskItem(BaseModel):
    clause_reference: str = ""
    category: str = "Other"
    risk_level: str = "Medium"
    explanation: str = ""
    suggested_action: str = ""


class ObligationItem(BaseModel):
    description: str = ""
    deadline_or_trigger: str = "Not specified"
    responsible_party: str = "Not specified"


class KeyDateItem(BaseModel):
    event: str = ""
    date_or_timeframe: str = ""


class RiskRadarResult(BaseModel):
    overall_risk_level: str = "Medium"
    overall_summary: str = ""
    risks: list[RiskItem] = Field(default_factory=list)
    obligations: list[ObligationItem] = Field(default_factory=list)
    key_dates: list[KeyDateItem] = Field(default_factory=list)


class AnalysisError(Exception):
    """Raised when the LLM analysis pipeline fails in a user-facing way."""


def _extract_json(raw_text: str) -> dict:
    """
    Strips markdown code fences and any stray preamble/postamble the model
    might add despite instructions, then parses JSON.
    """
    text = raw_text.strip()
    # Strip ```json ... ``` or ``` ... ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # If there's still leading/trailing junk, try to grab the outermost {...}
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        text = text[first_brace : last_brace + 1]

    return json.loads(text)


def generate_plain_english_summary(document_text: str) -> str:
    """Returns a plain-English markdown summary of the full document."""
    llm = get_chat_model(temperature=0.3)
    prompt = PLAIN_ENGLISH_SUMMARY_PROMPT.format(document_text=document_text)
    try:
        response = llm.invoke(prompt)
    except Exception as e:
        raise AnalysisError(
            f"Couldn't generate the summary due to an API error: {e}"
        ) from e

    content = (response.content or "").strip()
    if not content:
        raise AnalysisError("The model returned an empty summary. Please try again.")
    return content


def generate_risk_radar(document_text: str) -> RiskRadarResult:
    """Returns structured risk analysis, retrying once on malformed JSON."""
    llm = get_chat_model(temperature=0.1)  # low temp: we want consistent structure
    prompt = RISK_RADAR_PROMPT.format(document_text=document_text)

    last_error = None
    for attempt in range(2):
        try:
            response = llm.invoke(prompt)
            parsed = _extract_json(response.content or "")
            return RiskRadarResult(**parsed)
        except (json.JSONDecodeError, ValidationError, AttributeError) as e:
            last_error = e
            if attempt == 0:
                prompt = (
                    RISK_RADAR_PROMPT.format(document_text=document_text)
                    + "\n\nIMPORTANT: Your previous response was not valid JSON. "
                    "Return ONLY the JSON object, with no markdown fences and no "
                    "explanatory text before or after it."
                )
                continue
        except Exception as e:
            raise AnalysisError(
                f"Couldn't complete risk analysis due to an API error: {e}"
            ) from e

    raise AnalysisError(
        "The risk analysis model returned data ClauseShield couldn't parse "
        f"after retrying ({last_error.__class__.__name__}). Please try again."
    )


def answer_question(vector_store, question: str) -> tuple[str, list]:
    """
    RAG Q&A: retrieves relevant chunks, asks the LLM to answer using only
    those chunks, and returns (answer_text, retrieved_chunks) so the UI can
    show citations alongside the answer.
    """
    if not question or not question.strip():
        raise ValueError("Please enter a question.")

    chunks = retrieve_relevant_chunks(vector_store, question)
    if not chunks:
        raise AnalysisError("No relevant content could be retrieved from the document.")

    context = format_chunks_as_context(chunks)
    llm = get_chat_model(temperature=0.2)
    prompt = QA_SYSTEM_PROMPT.format(context=context, question=question)

    try:
        response = llm.invoke(prompt)
    except Exception as e:
        raise AnalysisError(f"Couldn't answer the question due to an API error: {e}") from e

    answer = (response.content or "").strip()
    if not answer:
        raise AnalysisError("The model returned an empty answer. Please try again.")

    return answer, chunks
