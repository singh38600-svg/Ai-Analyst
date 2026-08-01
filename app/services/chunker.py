"""
Table-aware financial text chunker.

`extract_financial_tables` and `recursive_financial_splitter` are kept
byte-for-byte compatible with the original prototype (same behavior,
defaults now sourced from app.config so PRD Section 4.1's 800/100
token spec is the actual default instead of the old 500/100).

`chunk_with_metadata` is new: it returns typed chunks (text vs. table)
instead of bare strings, which app/services/pdf_loader.py uses to
attach page_number + chunk_type to each chunk before it reaches the
vector store — needed for the {source_doc, page_number, chunk_id}
citation format required by PRD Section 4.1.
"""
import re
from typing import Any, Dict, List

from app.config import settings


def extract_financial_tables(text: str) -> List[Dict[str, Any]]:
    """
    Finds tabular markdown structure or simple pipe-separated tables in
    financial texts to treat them as single entities.
    """
    tables = []
    pattern = r"((?:^[^\n]*\|[^\n]*\n)(?:^[ \t]*\|?[ \t]*:?-+:?[ \t]*\|[^\n]*\n)(?:^[^\n]*\|[^\n]*(?:\n|$))+)"
    for match in re.finditer(pattern, text, re.MULTILINE):
        tables.append({
            "content": match.group(1).strip(),
            "start_idx": match.start(),
            "end_idx": match.end(),
            "type": "markdown_table",
        })
    return tables


def recursive_financial_splitter(
    text: str,
    chunk_size: int = settings.CHUNK_SIZE_TOKENS,
    chunk_overlap: int = settings.CHUNK_OVERLAP_TOKENS,
) -> List[str]:
    """
    Splits text by cleanly isolating financial tables as distinct
    chunks, preventing any table lines from spilling into general
    paragraph chunks. Word count is used as a token-count proxy
    (adequate for this project's scale; swap for a real tokenizer,
    e.g. tiktoken, if chasing exact token budgets in production).
    """
    tables = extract_financial_tables(text)

    def split_segment(segment: str, max_sz: int, overlap: int) -> List[str]:
        lines = [line.strip() for line in segment.split("\n") if line.strip()]
        clean_lines = [line for line in lines if not line.startswith("|")]
        segment_cleaned = "\n".join(clean_lines)

        words = segment_cleaned.split()
        if len(words) <= max_sz:
            return [segment_cleaned] if segment_cleaned.strip() else []

        chunks = []
        step = max_sz - overlap
        if step <= 0:
            step = max_sz // 2

        i = 0
        while i < len(words):
            chunk_words = words[i:i + max_sz]
            chunks.append(" ".join(chunk_words))
            i += step
            if i >= len(words):
                break
        return chunks

    if not tables:
        return split_segment(text, chunk_size, chunk_overlap)

    chunks = []
    last_idx = 0
    for tbl in tables:
        before_text = text[last_idx:tbl["start_idx"]]
        if before_text.strip():
            chunks.extend(split_segment(before_text, chunk_size, chunk_overlap))
        chunks.append(tbl["content"])
        last_idx = tbl["end_idx"]

    after_text = text[last_idx:]
    if after_text.strip():
        chunks.extend(split_segment(after_text, chunk_size, chunk_overlap))

    return chunks


def chunk_with_metadata(
    text: str,
    chunk_size: int = settings.CHUNK_SIZE_TOKENS,
    chunk_overlap: int = settings.CHUNK_OVERLAP_TOKENS,
) -> List[Dict[str, Any]]:
    """
    Same splitting logic as recursive_financial_splitter, but returns
    [{"text": ..., "chunk_type": "table"|"text"}, ...] so callers can
    tag each chunk's type in the vector store and citations.
    """
    tables = extract_financial_tables(text)
    table_contents = {t["content"] for t in tables}

    raw_chunks = recursive_financial_splitter(text, chunk_size, chunk_overlap)
    typed_chunks = []
    for chunk in raw_chunks:
        chunk_type = "table" if chunk in table_contents else "text"
        typed_chunks.append({"text": chunk, "chunk_type": chunk_type})
    return typed_chunks
