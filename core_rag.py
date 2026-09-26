"""
core/rag.py

Lightweight, fully in-memory RAG pipeline:
  1. Split document text into clause-aware chunks.
  2. Embed chunks and build a FAISS index — held only in memory
     (st.session_state), never written to disk, never committed to git.
  3. Retrieve top-k relevant chunks for a given question, with metadata
     that lets the Q&A layer cite "Excerpt N" back to the user.

Nothing in this module touches the filesystem for persistence.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from core_config import CHUNK_OVERLAP, CHUNK_SIZE, RETRIEVAL_K, get_embeddings

# Separators ordered from "most clause-like" to "last resort", so the
# splitter prefers breaking on section/clause boundaries before falling
# back to plain paragraph or sentence breaks.
_LEGAL_SEPARATORS = [
    "\n\nSection ",
    "\n\nSECTION ",
    "\n\nArticle ",
    "\n\nARTICLE ",
    "\n\nClause ",
    "\n\n",
    "\n",
    ". ",
    " ",
    "",
]


@dataclass
class RetrievedChunk:
    excerpt_number: int
    text: str
    source: str
    chunk_index: int


def chunk_text(text: str, source_name: str) -> list[Document]:
    """Splits raw document text into overlapping, clause-aware chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=_LEGAL_SEPARATORS,
    )
    raw_chunks = splitter.split_text(text)
    documents = []
    for i, chunk in enumerate(raw_chunks):
        documents.append(
            Document(
                page_content=chunk,
                metadata={"source": source_name, "chunk_index": i},
            )
        )
    return documents


def build_vector_store(text: str, source_name: str = "document"):
    """
    Builds an in-memory FAISS vector store from document text.
    Returns the FAISS store object — caller is responsible for stashing it
    in st.session_state (never write it to disk).
    """
    from langchain_community.vectorstores import FAISS

    if not text or not text.strip():
        raise ValueError("Cannot build a vector store from empty text.")

    documents = chunk_text(text, source_name)
    if not documents:
        raise ValueError("Document produced no chunks — text may be too short.")

    embeddings = get_embeddings()
    vector_store = FAISS.from_documents(documents, embeddings)
    return vector_store


def retrieve_relevant_chunks(vector_store, query: str, k: int = RETRIEVAL_K) -> list[RetrievedChunk]:
    """Retrieves the top-k most relevant chunks for a query, numbered for citation."""
    if vector_store is None:
        raise ValueError("No document has been indexed yet.")
    if not query or not query.strip():
        raise ValueError("Question cannot be empty.")

    results = vector_store.similarity_search(query, k=k)
    retrieved = []
    for i, doc in enumerate(results, start=1):
        retrieved.append(
            RetrievedChunk(
                excerpt_number=i,
                text=doc.page_content,
                source=doc.metadata.get("source", "document"),
                chunk_index=doc.metadata.get("chunk_index", -1),
            )
        )
    return retrieved


def format_chunks_as_context(chunks: list[RetrievedChunk]) -> str:
    """Formats retrieved chunks into the numbered context block the QA prompt expects."""
    parts = []
    for chunk in chunks:
        parts.append(f"[Excerpt {chunk.excerpt_number}]\n{chunk.text}")
    return "\n\n".join(parts)


def get_all_chunks_text(text: str, source_name: str = "document", max_chars: int | None = None) -> str:
    """
    Returns the full document text, optionally truncated, for full-document
    operations (summary, risk radar) that don't need retrieval — they
    reason over the whole document rather than a similarity-searched
    subset, since risk analysis needs global context, not just top-k hits.
    """
    if max_chars and len(text) > max_chars:
        return text[:max_chars] + "\n\n[... document truncated for length ...]"
    return text
