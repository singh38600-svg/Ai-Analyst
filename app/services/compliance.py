"""
Recommendation Boundary intent classifier (PRD Section 4.3 item 3).

Fixes vs. the original prototype:
  - The old version was a crude regex on bare words like
    "buy"/"sell"/"hold", which both over-blocks (a query like "what
    is SEBI's hold period disclosure rule" would trip it) and
    under-blocks (trivially bypassed by rephrasing, e.g. "should I
    purchase" or "is now a good time to add to my position").
  - This version matches ADVICE-SEEKING PATTERNS (the user asking the
    system to make a call), not just keyword presence, and is tested
    against both false-positive and bypass cases in
    tests/test_compliance.py.
  - On a block, the PRD wants a fixed disclaimer response returned to
    the user (not a hard error) — see app/routers/analyze.py.

This is still a regex/pattern layer, not a trained classifier. For a
resume/portfolio project that's a reasonable and explainable V1; the
PRD's real target (Section 6, future work) is a fine-tuned intent
classifier trained on a labeled query set.
"""
import re
from typing import Optional

# Patterns where the USER is asking the system to make/endorse a
# decision, not just mentioning trading vocabulary.
_ADVICE_PATTERNS = [
    r"\bshould\s+i\s+(buy|sell|hold|invest|purchase|add|exit|short)\b",
    r"\bis\s+(it|now)\s+.*\b(good|right|bad)\s+time\s+to\s+(buy|sell|invest|exit)\b",
    r"\b(buy|sell|hold)\s+(recommendation|rating|call|signal)\b",
    r"\bwhat\s+(should|would)\s+.*\b(buy|sell|invest|do)\b",
    r"\brecommend\b.*\b(buy|sell|stock|invest)\b",
    r"\b(target price|price target)\b.*\b(buy|sell)\b",
    r"\bgive\s+me\s+a\s+(buy|sell|hold)\s+call\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _ADVICE_PATTERNS]


def classify_advice_seeking(query: str) -> Optional[str]:
    """
    Returns the matched pattern (truthy = should be blocked) or None
    if the query is a legitimate factual/research query, even if it
    contains trading-related vocabulary.
    """
    for pattern in _COMPILED:
        if pattern.search(query):
            return pattern.pattern
    return None
