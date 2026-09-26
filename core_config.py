"""
core/config.py

Centralized configuration for ClauseShield.
Handles LLM provider selection (OpenAI or Google Gemini) so the rest of the
codebase never has to care which one is active.

Set LLM_PROVIDER in your .env to either "openai" or "gemini".
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ---------------------------------------------------------------------------
# Model names
# ---------------------------------------------------------------------------
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-1.5-flash")
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "models/embedding-001")

# ---------------------------------------------------------------------------
# RAG / chunking constants
# ---------------------------------------------------------------------------
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
RETRIEVAL_K = 5  # number of chunks pulled per Q&A query

# ---------------------------------------------------------------------------
# App constants
# ---------------------------------------------------------------------------
MAX_FILE_MB = 15
SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt")

DISCLAIMER_TEXT = (
    "⚠️ **ClauseShield provides informational guidance only and is NOT a "
    "substitute for licensed legal counsel.** AI-generated analysis may be "
    "incomplete or inaccurate. Always consult a qualified attorney before "
    "making legal or financial decisions based on any contract."
)

RISK_LEVELS = ("Low", "Medium", "High")


def get_chat_model(temperature: float = 0.2):
    """
    Returns a LangChain chat model instance for whichever provider is
    configured. Kept as a factory function (not a module-level singleton)
    so Streamlit's rerun model doesn't hold on to stale clients.
    """
    if LLM_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not GOOGLE_API_KEY:
            raise EnvironmentError(
                "GOOGLE_API_KEY is not set. Add it to your .env file."
            )
        return ChatGoogleGenerativeAI(
            model=GEMINI_CHAT_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=temperature,
            convert_system_message_to_human=True,
        )

    # default: openai
    from langchain_openai import ChatOpenAI

    if not OPENAI_API_KEY:
        raise EnvironmentError("OPENAI_API_KEY is not set. Add it to your .env file.")
    return ChatOpenAI(
        model=OPENAI_CHAT_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=temperature,
    )


def get_embeddings():
    """Returns a LangChain embeddings instance for the configured provider."""
    if LLM_PROVIDER == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        if not GOOGLE_API_KEY:
            raise EnvironmentError(
                "GOOGLE_API_KEY is not set. Add it to your .env file."
            )
        return GoogleGenerativeAIEmbeddings(
            model=GEMINI_EMBEDDING_MODEL, google_api_key=GOOGLE_API_KEY
        )

    from langchain_openai import OpenAIEmbeddings

    if not OPENAI_API_KEY:
        raise EnvironmentError("OPENAI_API_KEY is not set. Add it to your .env file.")
    return OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL, api_key=OPENAI_API_KEY)


def provider_ready() -> tuple[bool, str]:
    """Quick check used by the UI to show a friendly setup message."""
    if LLM_PROVIDER == "gemini":
        if not GOOGLE_API_KEY:
            return False, "GOOGLE_API_KEY missing — add it to your .env file."
        return True, "Gemini configured."
    if not OPENAI_API_KEY:
        return False, "OPENAI_API_KEY missing — add it to your .env file."
    return True, "OpenAI configured."
