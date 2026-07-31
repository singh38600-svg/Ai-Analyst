# Enterprise AI Investment Analyst Platform (EIAP)

An enterprise-grade, compliance-first Retrieval-Augmented Generation (RAG) platform tailored for institutional equity research in India, meticulously aligned with **SEBI (Research Analyst) Regulations, 2014**.

---

## 📈 Executive Summary

In institutional equity research, regulatory compliance and tabular precision are non-negotiable. 

### Persona: Priya, India Equity Analyst
Priya is a Senior Equity Analyst at a SEBI-registered brokerage in Mumbai. She covers India’s high-growth technology and financial sectors. Every day, Priya analyzes vast corpora of corporate filings, quarterly earnings transcripts, and annual reports to draft investment notes. Under the SEBI Research Analyst (RA) regulations:
* **The Disclosure Mandate:** Every research report she publishes must strictly attach automated disclosures regarding SEBI registration credentials, analyst holdings, financial interests, and standard market disclaimers.
* **The Record-Keeping Mandate:** Every search, document ingested, and query processed must be archived in an immutable, tamper-proof compliance log for a **minimum of 5 years**.
* **The Recommendation Boundary:** Unauthorised or non-reviewed automated recommendations (e.g., direct "buy" / "sell" / "hold" triggers generated dynamically by models) are strictly prohibited to avoid systemic compliance risk.

The **Enterprise AI Investment Analyst Platform (EIAP)** is built to supercharge Priya's productivity. It isolates complex financial tables seamlessly, filters RAG contexts precisely by stock tickers and fiscal years, and actively intercepts unauthorized recommendations—all while maintaining an ironclad audit trail to guarantee compliance with SEBI's rigid audit parameters.

---

## ⚙️ System Architecture

The following sequence details how documents are ingested and how user queries are classified, filtered, and synthesized securely through the EIAP:

```mermaid
graph TD
    A[Analyst User / Priya] -->|1. Raw Financial Upload| B[Data Ingest Endpoint]
    B -->|2. Table Preservation| C[Table-Aware Splitter]
    C -->|3. Index with Ticker/FY| D[(Vector Store with Pre-Filtering)]
    
    A -->|4. Send Query| E[FastAPI /analyze/query]
    E -->|5. SEBI Guardrail| F{SEBI Compliance Classifier}
    F -->|PROHIBITED: Direct Buy/Sell/Hold| G[Intercept & Generate 400 Bad Request]
    G -->|6a. Log Violation| H[(Immutable Audit Logs)]
    
    F -->|PERMITTED: Trend Analysis / Search| I[(Vector Store Search)]
    I -->|6b. Strict Metadata Pre-Filter: Ticker & FY| D
    D -->|7. Highly-Relevant Chunks Only| J[RAG Context Aggregator]
    J -->|8. Structured Context| K[LLM Synthesis Engine]
    K -->|9. Inject SEBI Disclosures & Disclaimers| L[Analysis Response]
    L -->|10. Log Permitted Action| H
    L -->|11. Fully-Compliant Output| A
