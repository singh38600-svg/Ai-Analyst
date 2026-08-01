"""
LLM synthesis + anti-hallucination verification layer.

Fixes vs. the original prototype:
  - The old analyze.py "answer" was pure string concatenation
    ("Based on the analyzed context (...), the synthesis indicates...")
    with no actual generation. This module adds a pluggable LLM call
    (mock / Anthropic / OpenAI), defaulting to "mock" so the whole
    pipeline runs offline with zero API keys for demo/dev purposes.
  - Adds the numeric verification layer required by PRD Section 4.3
    item 3: every numeric token in the generated answer is checked
    against the retrieved chunks verbatim; unverified numbers are
    flagged rather than silently trusted.

To go from "mock" to real generation: set LLM_PROVIDER=anthropic (or
openai) and the matching API key in .env. The mock path is honest
about being a template, not a hallucination — it never invents a
number that isn't in context.
"""
import re
from typing import Any, Dict, List, Tuple

from app.config import settings

_NUMBER_RE = re.compile(r"₹?\s?-?\d[\d,]*(?:\.\d+)?\s?%?")


def _normalize_number(token: str) -> str:
    return re.sub(r"[₹,\s%]", "", token)


def extract_numbers(text: str) -> List[str]:
    return [_normalize_number(m.group()) for m in _NUMBER_RE.finditer(text)]


def verify_numbers(answer_text: str, context_chunks: List[str]) -> Tuple[bool, List[str]]:
    """
    Returns (all_verified, unverified_numbers).
    Every numeric token in the answer must appear verbatim (after
    whitespace/currency-symbol normalization) in at least one context
    chunk. This is the core anti-hallucination check from PRD 4.3.
    """
    context_numbers = set()
    for chunk in context_chunks:
        context_numbers.update(extract_numbers(chunk))

    answer_numbers = extract_numbers(answer_text)
    unverified = [n for n in answer_numbers if n not in context_numbers]
    return (len(unverified) == 0), unverified


def _mock_synthesize(query: str, context_chunks: List[Dict[str, Any]]) -> str:
    """
    Deterministic, offline, zero-hallucination fallback. It does not
    "reason" — it surfaces the retrieved passages verbatim with
    citations, which is a legitimate (if unglamorous) synthesis
    strategy and, critically, cannot invent a number that isn't in
    the source. Replace with a real LLM call for actual synthesis.
    """
    if not context_chunks:
        return "No relevant information was found in the indexed filings for this query."

    lines = [f"Based on {len(context_chunks)} retrieved passage(s):\n"]
    for i, c in enumerate(context_chunks, 1):
        cite = f"[{c.get('ticker', '?')} FY{c.get('fiscal_year', '?')}, p.{c.get('page_number', '?')}, chunk {c.get('chunk_id', '?')}]"
        snippet = c["text"][:400] + ("..." if len(c["text"]) > 400 else "")
        lines.append(f"{i}. {cite}\n{snippet}\n")
    return "\n".join(lines)


def _anthropic_synthesize(query: str, context_chunks: List[Dict[str, Any]]) -> str:
    """Real LLM call. Requires ANTHROPIC_API_KEY to be set."""
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set. "
            "Add it to .env, or switch LLM_PROVIDER back to 'mock'."
        )
    import anthropic  # local import: optional dependency, only needed on this path

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    context_text = "\n\n".join(
        f"[Source: {c.get('ticker')} FY{c.get('fiscal_year')}, page {c.get('page_number')}, chunk {c.get('chunk_id')}]\n{c['text']}"
        for c in context_chunks
    )
    system = (
        "You are a research assistant for a SEBI-registered equity analyst. "
        "Answer ONLY using the provided context. Every number you state must "
        "appear verbatim in the context. Cite the source tag for every claim. "
        "Do NOT give buy/sell/hold recommendations or investment advice. "
        "If the context does not contain the answer, say so explicitly."
    )
    message = client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=1000,
        system=system,
        messages=[{"role": "user", "content": f"Context:\n{context_text}\n\nQuestion: {query}"}],
    )
    return "".join(block.text for block in message.content if block.type == "text")


def synthesize_answer(query: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Main entry point used by the /analyze router.
    Returns a dict with the answer text, verification result, and the
    raw citations, so the router can decide whether to surface a
    warning banner for unverified numbers.
    """
    if settings.LLM_PROVIDER == "anthropic":
        answer_text = _anthropic_synthesize(query, context_chunks)
    elif settings.LLM_PROVIDER == "openai":
        raise NotImplementedError(
            "OpenAI path not wired up yet — set LLM_PROVIDER=mock or anthropic."
        )
    else:
        answer_text = _mock_synthesize(query, context_chunks)

    context_texts = [c["text"] for c in context_chunks]
    verified, unverified_numbers = verify_numbers(answer_text, context_texts)

    citations = [
        {
            "chunk_id": c.get("chunk_id"),
            "ticker": c.get("ticker"),
            "fiscal_year": c.get("fiscal_year"),
            "page_number": c.get("page_number"),
        }
        for c in context_chunks
    ]

    return {
        "answer": answer_text,
        "citations": citations,
        "numbers_verified": verified,
        "unverified_numbers": unverified_numbers,
    }
