# Enterprise AI Investment Analyst Platform (EIAP)

An enterprise-grade, compliance-first Retrieval-Augmented Generation (RAG)
platform for institutional equity research in India, built around **SEBI
(Research Analyst) Regulations, 2014**.

## The problem

A Research Analyst at a SEBI-registered brokerage must ground every claim
in a filing, attach mandatory disclosures to every report, retain a
tamper-proof audit trail for 5+ years, and never let an automated system
issue an unauthorized buy/sell/hold call. EIAP is a RAG backend built
around those constraints from the ground up, rather than bolting compliance
onto a generic chatbot afterward.

## Architecture

```
PDF filing --> pdf_loader.py (page-level extraction)
           --> chunker.py (table-aware chunking, 800/100 tokens)
           --> vector_store.py (hybrid TF-IDF + BM25, ticker/FY pre-filter)
                     |
User query --> compliance.py (advice-seeking intent classifier) --[blocked]--> fixed disclaimer
           --> vector_store.search() --[low confidence]--> refusal, not a guess
           --> llm.py (synthesis + numeric verification against source chunks)
           --> models.py (hash-chained audit log, disclosure-stamped report)
```

## What's genuinely implemented

- **Table-aware chunking** — tables are never split mid-row; isolated as
  their own chunks (`app/services/chunker.py`)
- **Hybrid retrieval** — corpus-driven TF-IDF (dense proxy) + real BM25
  (lexical), not a hardcoded keyword list, with strict ticker + fiscal-year
  pre-filtering before any scoring happens (`app/services/vector_store.py`)
- **Confidence thresholding** — below a configurable cosine-similarity
  floor, the system refuses to answer instead of guessing
- **Numeric hallucination check** — every number in a generated answer is
  verified against the retrieved source text verbatim before being returned
  (`app/services/llm.py`)
- **Page-level citations** — `{ticker, fiscal_year, page_number, chunk_id}`
  on every claim, from real PDF page extraction (`app/services/pdf_loader.py`)
- **Recommendation-boundary intent classifier** — pattern-based, tested
  against both false positives ("what is SEBI's holding period rule") and
  bypass attempts ("is it a good time to add to my position"), not a
  bare "buy"/"sell" keyword check (`app/services/compliance.py`)
- **Tamper-evident audit log** — hash-chained rows (each row hashes its own
  content + the previous row's hash); editing or deleting a row breaks the
  chain, detectable via `GET /compliance/audit-log/verify`
  (`app/models.py`)
- **Human-in-the-loop feedback flywheel** — `/feedback` endpoint + review
  queue for flagged answers (`app/routers/feedback.py`)
- **Full test suite** covering chunking, compliance classification, hybrid
  retrieval pre-filtering, numeric verification, audit chain tampering, and
  an end-to-end API flow (`tests/`)

## What's intentionally mocked (and why)

- **LLM synthesis** defaults to a deterministic template (`LLM_PROVIDER=mock`
  in `.env`) that surfaces retrieved passages with citations and can never
  hallucinate a number, so the whole pipeline runs offline with zero API
  keys. Set `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` for real generation.
- **Live market price data** returns a clearly-labeled placeholder
  (`app/routers/market_data.py`) — wiring a real NSE/BSE vendor requires a
  paid API key that shouldn't be hardcoded into a public repo.
- **Embeddings** are TF-IDF/BM25, not a transformer model — dependency-free
  and fully offline-testable. Swappable for a real embedding API in
  `app/services/embeddings.py`.
- **Ragas faithfulness/context-precision scoring** isn't run here (requires
  the `ragas` package + an LLM judge call); `eval/run_eval.py` computes
  citation-rate and compliance-block accuracy directly instead, and
  documents how to add real Ragas scoring on top.

## Known remaining work

- Expand `eval/golden_set.json` from 10 example questions to the PRD's
  target 50, reviewed against real filings by someone who can confirm
  ground truth
- Frontend/UI (this is a backend API only, exposed via FastAPI + OpenAPI docs)
- OCR fallback for scanned (image-only) PDF filings
- A real embedding model once API/network access is available
- A real market data vendor integration

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
# API docs: http://localhost:8000/docs
```

```bash
pytest
```

## API summary

| Endpoint | Purpose |
|---|---|
| `POST /compliance/analysts` | Register a SEBI-registered analyst |
| `POST /ingest` | Upload + index a PDF filing |
| `POST /analyze` | Ask a question; returns cited answer or compliance-blocked disclaimer |
| `GET /compliance/audit-log/verify` | Confirm the audit log hash chain is intact |
| `POST /feedback` | Flag an answer as incorrect |
| `GET /feedback/queue` | Weekly review queue of flagged answers |
| `GET /market-data/price/{ticker}` | Live price lookup (mock provider by default) |

## Regulatory grounding

Built against SEBI (Research Analyst) Regulations, 2014 — specifically the
disclosure mandate, 5-year record-keeping requirement, and the boundary on
automated recommendations. This is a portfolio/demo project, not a
SEBI-registered or legally reviewed compliance system — see disclaimers in
`app/config.py`.
