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
🛡️ Core Guardrails
EIAP implements three strict non-negotiable guardrails directly at the core backend level:

1. Upfront SEBI Advice Interceptor
Unlike naive RAG systems that rely on post-hoc disclaimer generation or system prompt instructions, EIAP implements Active Prompt Interception.

Mechanism: Any query containing recommendation intents (e.g. buy, sell, hold, should I invest, buy target) is dynamically intercepted before running any vector search or consuming LLM tokens.
Log Immutability: The interception is instantly logged under a COMPLIANCE_VIOLATION_INTERCEPTED payload in our SQLite database, providing regulators with immediate audit capabilities.
Feedback: The platform immediately returns a 400 Bad Request explaining the exact regulatory rule violated.
2. Strict Ticker & Fiscal Year Metadata Pre-Filtering
General vector stores often match query embeddings across arbitrary documents, leading to catastrophic context contamination (e.g., retrieving FY23 metrics when querying about FY24, or mixing TCS metrics with Infosys).

Mechanism: EIAP enforces mandatory metadata tagging on document uploads. When an analyst queries the system, they provide a target ticker (e.g. TCS) and fiscal_year (e.g. 2024).
Enforcement: The Vector database pre-filters and drops all index chunks that do not strictly match the target parameters before doing any vector cosine similarity matching. This ensures 100% clean context isolation.
3. Table-Aware Financial Chunking
Corporate financial disclosures rely heavily on structured markdown/pipe tables. Standard text splitters slice through these structures arbitrarily, slicing numbers in half and severing columns from their headers.

Mechanism: EIAP's recursive splitter parses and extracts complete markdown table segments intact.
Isolation: It processes tables as their own complete, isolated chunks, ensuring tabular row alignments are preserved perfectly and are never mixed into unstructured text paragraph chunks.
🛠️ Tech Stack
Language: Python 3.12 (with typed signatures)
Framework: FastAPI (Asynchronous Web Gateway)
Validation: Pydantic V2 (Strict request schemas)
Database / Audit Layer: SQLAlchemy 2.0 ORM + SQLite
Search / RAG: VectorStoreEmulator (TF-IDF Similarity + Strict Metadata Filtering)
🔌 Integration Guide: Flowise & Dify
EIAP is built to integrate out of the box with modern enterprise LLM orchestrators like Flowise and Dify using its complete, standard Open API specifications.

Step-by-Step Integration with Flowise / Dify:
Retrieve OpenAPI Specification: Copy the generated openapi.json from this platform (available at the root directory or generated dynamically via /openapi.json).
Setup Custom Agent / Action in Orchestrator:
In Dify, go to Actions -> Create Custom Action. Paste the contents of openapi.json.
In Flowise, use the Custom Tool block or add an API Agent block and load the OpenAPI schema.
Configure Authentication / Headers: EIAP runs seamlessly inside enterprise secure VPCs. Set your Base URL pointing to the deployed Docker container (e.g. http://eiap-backend:8000).
Design the Agent Workflow:
Configure Dify/Flowise to first register Priya (or the licensed analyst) using the /compliance/analyst endpoint to retrieve a valid analyst ID.
Attach file uploading nodes directly to /ingest/document to tag documents with the appropriate Ticker and Fiscal Year.
Direct all user query prompts to /analyze/query to ensure automated guardrail interception and SEBI disclaimer generation are fully active.
