"""
Hybrid retrieval vector store.

Fixes vs. the original prototype:
  1. Real corpus-driven TF-IDF + BM25 hybrid scoring instead of a fixed
     10-keyword mock vector (see services/embeddings.py).
  2. Ticker + fiscal-year metadata pre-filtering happens BEFORE any
     scoring, exactly matching PRD Section 4.1's "non-negotiable"
     requirement, and unit-tested in tests/test_vector_store.py.
  3. Confidence thresholding (PRD Section 4.3 item 4): if the best
     match is below CONFIDENCE_THRESHOLD, the store returns an empty
     result set with a low_confidence flag instead of forcing a weak
     answer.
  4. Simple JSON-file persistence so the index survives a restart
     (the original was a pure in-memory list). For a real production
     system, swap this for pgvector / Chroma / FAISS — the interface
     (`add_chunk` / `search`) is designed to be a drop-in replacement.
  5. page_number is tracked per chunk so citations can be rendered as
     {source_doc, page_number, chunk_id} per PRD Section 4.1.
"""
import json
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.services.embeddings import Corpus, bm25_score, cosine_sparse, tfidf_vector, tokenize


@dataclass
class IndexedChunk:
    chunk_id: int
    text: str
    doc_id: int
    ticker: Optional[str]
    fiscal_year: Optional[str]
    page_number: Optional[int]
    chunk_type: str  # "table" | "text"


class VectorStoreEmulator:
    """
    Despite the name (kept for API compatibility with the earlier
    prototype), this is a real hybrid lexical/TF-IDF retriever, not a
    mock. Persisted to a JSON file next to the SQLite DB.
    """

    def __init__(self, persist_path: str = "./vector_index.json"):
        self.persist_path = persist_path
        self.corpus = Corpus()
        self.chunks: Dict[int, IndexedChunk] = {}
        self._load()

    # ---- persistence ----
    def _load(self) -> None:
        if os.path.exists(self.persist_path):
            with open(self.persist_path, "r") as f:
                data = json.load(f)
            for row in data:
                chunk = IndexedChunk(**row)
                self.chunks[chunk.chunk_id] = chunk
                self.corpus.add(chunk.chunk_id, chunk.text)

    def _save(self) -> None:
        with open(self.persist_path, "w") as f:
            json.dump([asdict(c) for c in self.chunks.values()], f)

    def clear(self) -> None:
        self.corpus = Corpus()
        self.chunks = {}
        if os.path.exists(self.persist_path):
            os.remove(self.persist_path)

    # ---- indexing ----
    def add_chunk(
        self,
        chunk_id: int,
        text: str,
        doc_id: int,
        ticker: Optional[str] = None,
        fiscal_year: Optional[str] = None,
        page_number: Optional[int] = None,
        chunk_type: str = "text",
    ) -> None:
        chunk = IndexedChunk(
            chunk_id=chunk_id,
            text=text,
            doc_id=doc_id,
            ticker=ticker.upper() if ticker else None,
            fiscal_year=str(fiscal_year) if fiscal_year else None,
            page_number=page_number,
            chunk_type=chunk_type,
        )
        self.chunks[chunk_id] = chunk
        self.corpus.add(chunk_id, text)
        self._save()

    # ---- retrieval ----
    def search(
        self,
        query: str,
        top_k: int = 5,
        ticker: Optional[str] = None,
        fiscal_year: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
    ) -> Tuple[List[Tuple[Dict[str, Any], float]], bool]:
        """
        Returns (results, low_confidence).
        results is a list of (chunk_dict, score) sorted best-first.
        low_confidence is True if the best available score is below
        the configured threshold — callers should treat this as "no
        good answer" per PRD Section 4.3.
        """
        threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else settings.CONFIDENCE_THRESHOLD
        )

        # 1. Strict pre-filter on ticker + fiscal year (non-negotiable,
        #    prevents cross-company data contamination).
        target_ticker = ticker.upper() if ticker else None
        target_fy = str(fiscal_year) if fiscal_year else None

        candidate_ids = [
            cid
            for cid, c in self.chunks.items()
            if (target_ticker is None or c.ticker == target_ticker)
            and (target_fy is None or c.fiscal_year == target_fy)
        ]
        if not candidate_ids:
            return [], True

        # 2. Hybrid scoring: TF-IDF cosine (dense-ish/semantic proxy)
        #    + BM25 (lexical/exact-match), matching PRD's hybrid retrieval.
        query_tokens = tokenize(query)
        query_vec = tfidf_vector(query_tokens, self.corpus)

        scored: List[Tuple[IndexedChunk, float]] = []
        for cid in candidate_ids:
            chunk = self.chunks[cid]
            doc_tokens = self.corpus.doc_tokens.get(cid, [])
            doc_vec = tfidf_vector(doc_tokens, self.corpus)
            dense_score = cosine_sparse(query_vec, doc_vec)
            lexical_score = bm25_score(query_tokens, cid, self.corpus)
            # Normalize BM25 into a comparable ~0-1 range so it doesn't
            # dominate; weighting is tunable via the flywheel (Section 6.2).
            normalized_bm25 = lexical_score / (lexical_score + 5.0)
            combined = 0.6 * dense_score + 0.4 * normalized_bm25
            scored.append((chunk, combined))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        if not top or top[0][1] < threshold:
            return [], True

        results = [
            (
                {
                    "chunk_id": c.chunk_id,
                    "text": c.text,
                    "doc_id": c.doc_id,
                    "ticker": c.ticker,
                    "fiscal_year": c.fiscal_year,
                    "page_number": c.page_number,
                    "chunk_type": c.chunk_type,
                },
                score,
            )
            for c, score in top
        ]
        return results, False


vector_store = VectorStoreEmulator()
