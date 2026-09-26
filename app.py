"""
app.py

ClauseShield — Streamlit entrypoint.

Tabs:
  1. Document Analyzer  — upload, plain-English summary, risk radar, badges
  2. Q&A Chat           — RAG-based question answering with citations
  3. Compare Documents   — two-document diff & risk-shift analysis
  4. Export Prep Kit     — "Ask a Lawyer" brief generation & download

All heavy state (vector store, analysis results) lives in st.session_state
for the duration of the browser session only — nothing is persisted to
disk, keeping the deployment stateless and the repo footprint tiny.
"""

from __future__ import annotations

import os

import streamlit as st

from core_analyzer import (
    AnalysisError,
    generate_plain_english_summary,
    generate_risk_radar,
    answer_question,
)
from core_comparator import ComparisonError, compare_documents
from core_config import DISCLAIMER_TEXT, MAX_FILE_MB, provider_ready
from core_guardrails import GuardrailResult, check_is_legal_document, validate_not_empty
from core_lawyer_kit import export_prep_kit_as_markdown, generate_lawyer_prep_kit
from core_loaders import DocumentLoadError, load_document
from core_rag import build_vector_store

st.set_page_config(
    page_title="ClauseShield — AI Legal Document Analyzer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

RISK_BADGE_COLORS = {
    "Low": "#1e7e34",
    "Medium": "#b8860b",
    "High": "#c0392b",
}

SAMPLES_DIR = os.path.dirname(__file__)


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
def _init_state():
    defaults = {
        "doc_text": None,
        "doc_name": None,
        "vector_store": None,
        "summary_text": None,
        "risk_result": None,
        "qa_history": [],  # list[(question, answer)]
        "compare_a": None,  # (name, text)
        "compare_b": None,
        "comparison_result": None,
        "prep_kit": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


_init_state()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def risk_badge(level: str) -> str:
    color = RISK_BADGE_COLORS.get(level, "#6c757d")
    return (
        f'<span style="background-color:{color}; color:white; padding:3px 12px; '
        f'border-radius:12px; font-size:0.85em; font-weight:600;">{level} Risk</span>'
    )


def load_sample(filename: str) -> tuple[str, str]:
    path = os.path.join(SAMPLES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return filename, f.read()


def process_uploaded_file(uploaded_file) -> tuple[str, str] | None:
    """Loads + guardrail-validates an uploaded file. Returns (name, text) or None on failure."""
    if uploaded_file is None:
        return None

    size_mb = uploaded_file.size / (1024 * 1024)
    if size_mb > MAX_FILE_MB:
        st.error(f"'{uploaded_file.name}' is {size_mb:.1f} MB, which exceeds the {MAX_FILE_MB} MB limit.")
        return None

    try:
        loaded = load_document(uploaded_file.getvalue(), uploaded_file.name)
    except DocumentLoadError as e:
        st.error(f"⚠️ Couldn't read this file: {e}")
        return None

    for warning in loaded.warnings:
        st.warning(warning)

    with st.spinner("Checking this looks like a legal document..."):
        try:
            from core_config import get_chat_model

            classifier_llm = get_chat_model(temperature=0)
        except Exception:
            classifier_llm = None
        result: GuardrailResult = check_is_legal_document(loaded.text, llm=classifier_llm)

    if not result.is_legal_document:
        st.error(
            f"⚠️ This doesn't look like a legal document. {result.reason} "
            "ClauseShield is designed for contracts and agreements — please "
            "upload one, or continue at your own risk by using the sample "
            "documents in the sidebar."
        )
        return None

    return loaded.filename, loaded.text


def reset_document_state():
    st.session_state.doc_text = None
    st.session_state.doc_name = None
    st.session_state.vector_store = None
    st.session_state.summary_text = None
    st.session_state.risk_result = None
    st.session_state.qa_history = []
    st.session_state.prep_kit = None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🛡️ ClauseShield")
    st.caption("AI legal document analyzer & assistant")

    ready, status_msg = provider_ready()
    if ready:
        st.success(status_msg, icon="✅")
    else:
        st.error(status_msg, icon="🔑")
        st.info(
            "Copy `.env.example` to `.env` and add your API key, or set "
            "`LLM_PROVIDER=gemini` if you're using a Google API key instead."
        )

    st.divider()
    st.subheader("📂 Load a Document")

    uploaded = st.file_uploader(
        "Upload a contract (PDF, DOCX, or TXT)",
        type=["pdf", "docx", "txt"],
        key="main_uploader",
    )

    if uploaded is not None and uploaded.name != st.session_state.doc_name:
        result = process_uploaded_file(uploaded)
        if result:
            reset_document_state()
            st.session_state.doc_name, st.session_state.doc_text = result
            st.rerun()

    st.markdown("**Or try a demo contract:**")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📄 Fair Contract", use_container_width=True):
            reset_document_state()
            st.session_state.doc_name, st.session_state.doc_text = load_sample(
                "sample_freelance_agreement_fair.txt"
            )
            st.rerun()
    with col_b:
        if st.button("⚠️ Risky Contract", use_container_width=True):
            reset_document_state()
            st.session_state.doc_name, st.session_state.doc_text = load_sample(
                "sample_freelance_agreement_risky.txt"
            )
            st.rerun()

    if st.session_state.doc_name:
        st.divider()
        st.markdown(f"**Loaded:** `{st.session_state.doc_name}`")
        if st.button("🗑️ Clear Document", use_container_width=True):
            reset_document_state()
            st.rerun()

    st.divider()
    st.caption("Built for hackathon demo purposes. Not a law firm. Not legal advice.")


# ---------------------------------------------------------------------------
# Header + mandatory disclaimer (always visible)
# ---------------------------------------------------------------------------
st.title("ClauseShield")
st.markdown(
    """
    <div style="background-color:#fff3cd; border-left: 5px solid #ffb300; padding: 12px 16px; border-radius: 6px; margin-bottom: 1rem;">
    """
    + DISCLAIMER_TEXT
    + "</div>",
    unsafe_allow_html=True,
)

if not st.session_state.doc_text:
    st.info("👈 Upload a contract or load a demo document from the sidebar to get started.")
    st.stop()

tab_analyze, tab_qa, tab_compare, tab_export = st.tabs(
    ["📄 Document Analyzer", "💬 Q&A Chat", "🔀 Compare Documents", "📋 Export Prep Kit"]
)


# ---------------------------------------------------------------------------
# TAB 1 — Document Analyzer (Plain-English + Risk Radar)
# ---------------------------------------------------------------------------
with tab_analyze:
    st.subheader(f"Analyzing: {st.session_state.doc_name}")

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("🔍 Generate Plain-English Summary", type="primary"):
            with st.spinner("Reading through the document..."):
                try:
                    st.session_state.summary_text = generate_plain_english_summary(
                        st.session_state.doc_text
                    )
                except AnalysisError as e:
                    st.error(str(e))

    with col2:
        if st.button("🚨 Run Risk & Obligation Radar", type="primary"):
            with st.spinner("Scanning for red flags, obligations, and deadlines..."):
                try:
                    st.session_state.risk_result = generate_risk_radar(st.session_state.doc_text)
                except AnalysisError as e:
                    st.error(str(e))

    st.divider()

    if st.session_state.summary_text:
        st.markdown("### 📖 Plain-English Explainer")
        st.markdown(st.session_state.summary_text)
        st.divider()

    if st.session_state.risk_result:
        risk = st.session_state.risk_result
        st.markdown("### 🚨 Risk & Obligation Radar")

        header_col1, header_col2 = st.columns([3, 1])
        with header_col1:
            st.markdown(risk.overall_summary)
        with header_col2:
            st.markdown(risk_badge(risk.overall_risk_level), unsafe_allow_html=True)

        if risk.risks:
            st.markdown("#### Flagged Clauses")
            for item in risk.risks:
                with st.container(border=True):
                    top_col1, top_col2 = st.columns([4, 1])
                    with top_col1:
                        st.markdown(f"**{item.category}** — _{item.clause_reference}_")
                    with top_col2:
                        st.markdown(risk_badge(item.risk_level), unsafe_allow_html=True)
                    st.markdown(item.explanation)
                    if item.suggested_action:
                        st.caption(f"💡 Suggested action: {item.suggested_action}")
        else:
            st.success("No significant risk flags detected.")

        col_ob, col_dates = st.columns(2)
        with col_ob:
            st.markdown("#### 📌 Obligations")
            if risk.obligations:
                for ob in risk.obligations:
                    st.markdown(f"- **{ob.description}**")
                    st.caption(f"  Trigger/Deadline: {ob.deadline_or_trigger} · Responsible: {ob.responsible_party}")
            else:
                st.caption("No specific obligations extracted.")

        with col_dates:
            st.markdown("#### 📅 Key Dates")
            if risk.key_dates:
                for d in risk.key_dates:
                    st.markdown(f"- **{d.date_or_timeframe}** — {d.event}")
            else:
                st.caption("No specific dates extracted.")

    with st.expander("📄 View Extracted Document Text"):
        st.text(st.session_state.doc_text[:5000] + ("..." if len(st.session_state.doc_text) > 5000 else ""))


# ---------------------------------------------------------------------------
# TAB 2 — Q&A Chat (RAG with citations)
# ---------------------------------------------------------------------------
with tab_qa:
    st.subheader("Ask Questions About This Document")
    st.caption("Answers are grounded in the document's actual text, with citations to the relevant excerpt.")

    if st.session_state.vector_store is None:
        if st.button("⚙️ Index Document for Q&A", type="primary"):
            with st.spinner("Building search index (embedding document chunks)..."):
                try:
                    st.session_state.vector_store = build_vector_store(
                        st.session_state.doc_text, st.session_state.doc_name
                    )
                    st.success("Document indexed. Ask away!")
                except Exception as e:
                    st.error(f"Couldn't index the document: {e}")
    else:
        st.success("✅ Document is indexed and ready for questions.", icon="✅")

        for q, a in st.session_state.qa_history:
            with st.chat_message("user"):
                st.markdown(q)
            with st.chat_message("assistant"):
                st.markdown(a)

        question = st.chat_input("Ask about payment terms, termination, liability, etc.")
        if question:
            try:
                validate_not_empty(question, "question")
            except ValueError as e:
                st.error(str(e))
            else:
                with st.chat_message("user"):
                    st.markdown(question)
                with st.chat_message("assistant"):
                    with st.spinner("Searching the document..."):
                        try:
                            answer, chunks = answer_question(st.session_state.vector_store, question)
                            st.markdown(answer)
                            with st.expander("📎 View cited excerpts"):
                                for c in chunks:
                                    st.markdown(f"**Excerpt {c.excerpt_number}:**")
                                    st.caption(c.text[:600] + ("..." if len(c.text) > 600 else ""))
                            st.session_state.qa_history.append((question, answer))
                        except (AnalysisError, ValueError) as e:
                            st.error(str(e))


# ---------------------------------------------------------------------------
# TAB 3 — Compare Documents
# ---------------------------------------------------------------------------
with tab_compare:
    st.subheader("Compare Two Documents")
    st.caption("Upload a second document to compare against the currently loaded one, or upload two fresh documents below.")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Document A**")
        use_loaded = st.checkbox("Use currently loaded document as A", value=True)
        if use_loaded:
            st.session_state.compare_a = (st.session_state.doc_name, st.session_state.doc_text)
            st.caption(f"Using: `{st.session_state.doc_name}`")
        else:
            file_a = st.file_uploader("Upload Document A", type=["pdf", "docx", "txt"], key="compare_a_upload")
            if file_a is not None:
                result = process_uploaded_file(file_a)
                if result:
                    st.session_state.compare_a = result

    with col_b:
        st.markdown("**Document B**")
        file_b = st.file_uploader("Upload Document B", type=["pdf", "docx", "txt"], key="compare_b_upload")
        if file_b is not None:
            result = process_uploaded_file(file_b)
            if result:
                st.session_state.compare_b = result
        st.caption("Or load the risky sample for a quick demo:")
        if st.button("⚠️ Use Risky Sample as B"):
            st.session_state.compare_b = load_sample("sample_freelance_agreement_risky.txt")
        if st.button("📄 Use Fair Sample as B"):
            st.session_state.compare_b = load_sample("sample_freelance_agreement_fair.txt")

    st.divider()

    if st.session_state.compare_a and st.session_state.compare_b:
        if st.button("🔀 Compare Documents", type="primary"):
            with st.spinner("Comparing documents clause by clause..."):
                try:
                    name_a, text_a = st.session_state.compare_a
                    name_b, text_b = st.session_state.compare_b
                    st.session_state.comparison_result = compare_documents(text_a, name_a, text_b, name_b)
                except (ComparisonError, ValueError) as e:
                    st.error(str(e))
    else:
        st.info("Load both Document A and Document B to enable comparison.")

    if st.session_state.comparison_result:
        result = st.session_state.comparison_result
        st.markdown("### Comparison Summary")
        st.markdown(result.summary)

        st.markdown("### Risk Shift")
        st.info(result.risk_shift)

        st.markdown("### Detailed Differences")
        for diff in result.differences:
            with st.container(border=True):
                top_col1, top_col2 = st.columns([4, 1])
                with top_col1:
                    st.markdown(f"**{diff.topic}**")
                with top_col2:
                    st.markdown(risk_badge(diff.materiality), unsafe_allow_html=True)
                dc1, dc2 = st.columns(2)
                with dc1:
                    st.markdown("**Document A:**")
                    st.caption(diff.document_a_position)
                with dc2:
                    st.markdown("**Document B:**")
                    st.caption(diff.document_b_position)
                st.markdown(f"_{diff.analysis}_")


# ---------------------------------------------------------------------------
# TAB 4 — Export "Ask a Lawyer" Prep Kit
# ---------------------------------------------------------------------------
with tab_export:
    st.subheader("Ask-a-Lawyer Prep Kit")
    st.caption(
        "Generates an organized brief — chronological timeline, top concerns, "
        "and tailored questions — so you can make the most of time with an attorney."
    )

    if st.session_state.risk_result is None:
        st.warning("Run the Risk & Obligation Radar in the Document Analyzer tab first.")
    else:
        if st.button("📋 Generate Prep Kit", type="primary"):
            with st.spinner("Assembling your attorney brief..."):
                try:
                    st.session_state.prep_kit = generate_lawyer_prep_kit(
                        st.session_state.risk_result, st.session_state.qa_history
                    )
                except Exception as e:
                    st.error(f"Couldn't generate the prep kit: {e}")

        if st.session_state.prep_kit:
            kit = st.session_state.prep_kit

            st.markdown("### Document Overview")
            st.markdown(kit.document_overview)

            st.markdown("### Chronological Timeline")
            for item in kit.chronological_timeline:
                st.markdown(f"- **{item.date_or_stage}** — {item.event}")

            st.markdown("### Top Concerns")
            for c in kit.top_concerns:
                with st.container(border=True):
                    st.markdown(f"**[{c.priority}] {c.concern}**")
                    st.caption(c.why_it_matters)

            st.markdown("### Questions for Your Attorney")
            for i, q in enumerate(kit.questions_for_attorney, start=1):
                st.markdown(f"{i}. {q}")

            markdown_export = export_prep_kit_as_markdown(kit, st.session_state.doc_name)
            st.divider()
            st.download_button(
                label="⬇️ Download Prep Kit (Markdown)",
                data=markdown_export,
                file_name=f"lawyer_prep_kit_{st.session_state.doc_name.rsplit('.', 1)[0]}.md",
                mime="text/markdown",
                type="primary",
            )
