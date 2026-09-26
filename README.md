# 🛡️ ClauseShield

**An accessible, GenAI-powered legal document analyzer and assistant.**

ClauseShield helps everyday users and freelancers understand, compare, and
navigate legal agreements — without replacing licensed legal counsel. Upload
a contract and get a plain-English explanation, a red-flag risk radar,
grounded document Q&A, side-by-side contract comparison, and a
ready-to-print "Ask a Lawyer" prep kit.

> ⚠️ **ClauseShield provides informational guidance only and is not a
> substitute for licensed legal counsel.** See the in-app disclaimer.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📖 Plain-English Explainer | Summarizes dense legal contracts in layman's terms |
| 🚨 Risk & Obligation Radar | Flags one-sided clauses, unlimited liability, aggressive IP terms, non-competes, obligations, and deadlines — with Low/Medium/High badges |
| 💬 Interactive Document Q&A | RAG-powered chat that answers questions using only the document, with excerpt citations |
| 🔀 Contract Comparison | Compares two agreements/versions and highlights material differences and risk shift |
| 📋 Ask-a-Lawyer Prep Kit | Exports a chronological brief, top concerns, and tailored attorney questions as Markdown |

---

## 🏗️ Architecture

```
                         ┌─────────────────────────┐
                         │      Streamlit UI        │
                         │        (app.py)          │
                         │  ┌─────┬─────┬─────┬───┐ │
                         │  │Anlyz│ Q&A │Comp │Exp│ │
                         │  └─────┴─────┴─────┴───┘ │
                         └────────────┬─────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
      ┌───────────────┐      ┌───────────────┐      ┌──────────────────┐
      │  loaders.py    │      │ guardrails.py │      │    prompts.py     │
      │ PDF/DOCX/TXT   │─────▶│ Is it legal?  │      │ Centralized       │
      │ extraction     │      │ heuristic+LLM │      │ system prompts    │
      └───────────────┘      └───────────────┘      └─────────┬─────────┘
                                                                │
              ┌─────────────────────────────────────────────────┴──────┐
              ▼                       ▼                       ▼        ▼
      ┌───────────────┐      ┌───────────────┐      ┌───────────────┐┌──────────────┐
      │    rag.py      │      │  analyzer.py  │      │ comparator.py ││ lawyer_kit.py │
      │ chunk + FAISS  │◀────▶│ summary +     │      │ 2-doc diff +  ││ prep kit gen  │
      │ (in-memory)    │      │ risk radar    │      │ risk shift    ││ + MD export   │
      └───────────────┘      └───────────────┘      └───────────────┘└──────────────┘
              │                       │                       │              │
              └───────────────────────┴───────────┬───────────┴──────────────┘
                                                    ▼
                                          ┌───────────────────┐
                                          │  config.py          │
                                          │  OpenAI / Gemini     │
                                          │  provider factory    │
                                          └───────────────────┘
```

**Why this stays lightweight:** the FAISS vector index is built fresh each
session and held only in `st.session_state` — it is never written to disk
or committed to git. Embeddings are computed via API call (OpenAI
`text-embedding-3-small` or Gemini `embedding-001`), so no local embedding
model weights are bundled. The entire repository — code, prompts, and
sample contracts — is plain text and stays well under the 10 MB hackathon
limit.

---

## 🚀 Quickstart

```bash
# 1. Clone and enter the repo
git clone <your-repo-url> clauseshield
cd clauseshield

# 2. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your API key
cp .env.example .env
# then edit .env and add your OPENAI_API_KEY (or GOOGLE_API_KEY + LLM_PROVIDER=gemini)

# 5. Run the app
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## 🧪 Testing Instructions for Judges

**No API key required** for the offline sanity tests:

```bash
pip install -r requirements.txt
pytest tests/ -v
```

This exercises the document loaders and the Stage-1 heuristic guardrail
(e.g. confirming a recipe is correctly rejected as "not a legal
document," and that both sample contracts pass).

**Full interactive demo (requires an API key):**

1. Run `streamlit run app.py`.
2. In the sidebar, click **⚠️ Risky Contract** to load the skewed demo
   agreement.
3. In the **Document Analyzer** tab, click **Generate Plain-English
   Summary**, then **Run Risk & Obligation Radar** — note the High-Risk
   badges on the uncapped indemnification, aggressive IP assignment,
   5-year global non-compete, and 90-day payment delay.
4. In the **Q&A Chat** tab, click **Index Document for Q&A**, then ask:
   *"How long is the non-compete and where does it apply?"* — the answer
   should cite the relevant excerpt.
5. In the **Compare Documents** tab, keep the risky contract as Document
   A and click **📄 Use Fair Sample as B**, then **Compare Documents** —
   review the side-by-side differences and overall risk shift.
6. In the **Export Prep Kit** tab, click **Generate Prep Kit** and
   download the Markdown brief.
7. To test the guardrail live: try uploading a non-legal `.txt` file
   (e.g. a recipe or a short note) — ClauseShield should reject it with
   an explanation instead of attempting analysis.

---

## 📁 Project Structure

```
clauseshield/
├── app.py                   # Streamlit UI (all 4 tabs)
├── core/
│   ├── config.py              # LLM provider config (OpenAI/Gemini)
│   ├── loaders.py              # PDF/DOCX/TXT extraction
│   ├── guardrails.py           # legal-document validation
│   ├── rag.py                  # chunking + in-memory FAISS
│   ├── prompts.py               # all system prompts
│   ├── analyzer.py               # summary + risk radar + Q&A
│   ├── comparator.py              # contract comparison
│   └── lawyer_kit.py               # prep kit generation + export
├── samples/
│   ├── freelance_agreement_fair.txt
│   └── freelance_agreement_risky.txt
├── tests/
│   └── test_guardrails.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## ⚙️ Configuration Notes

- Switch providers anytime by changing `LLM_PROVIDER` in `.env` to
  `openai` or `gemini` — no code changes needed.
- `MAX_FILE_MB` and chunking parameters (`CHUNK_SIZE`, `CHUNK_OVERLAP`,
  `RETRIEVAL_K`) are tunable in `core/config.py`.
- This build does not perform OCR — scanned/image-only PDFs will be
  rejected with a clear error message rather than silently failing.

## 🛑 Disclaimer

ClauseShield is a hackathon proof-of-concept. It is not a law firm, does
not provide legal advice, and using it does not create an
attorney-client relationship. Always consult a licensed attorney for
decisions with legal or financial consequences.
