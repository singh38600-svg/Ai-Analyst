"""
Evaluation harness against eval/golden_set.json.

Honest status: this computes citation-rate and compliance-block
accuracy directly (no extra dependencies, runs anywhere) rather than
Ragas's faithfulness/context-precision/context-recall metrics, which
require the `ragas` package + an LLM judge call — not installable in
an offline sandbox, and something Rohit should add once he has
network/API access:

    pip install ragas
    # then score `answer` vs `contexts` vs `ground_truth` per
    # https://docs.ragas.io/ for faithfulness >0.90 and the other
    # PRD Section 5 targets.

Also note: eval/golden_set.json currently ships with 10 example
questions as a template. The PRD's target is a 50-question set
reviewed by an actual SEBI-registered analyst for ground-truth
correctness — expanding that list (with real filing data, not the
placeholder TCS/2024 examples used in tests) is real remaining work,
not something to fabricate here.

Usage (after the API is running locally):
    python eval/run_eval.py --base-url http://localhost:8000 --analyst-id 1
"""
import argparse
import json
import sys
from pathlib import Path

import httpx


def run(base_url: str, analyst_id: int, golden_path: str) -> None:
    golden = json.loads(Path(golden_path).read_text())

    correct_block_decisions = 0
    citation_hits = 0
    citation_eligible = 0

    for item in golden:
        resp = httpx.post(
            f"{base_url}/analyze",
            json={
                "query": item["query"],
                "ticker": item.get("ticker"),
                "fiscal_year": item.get("fiscal_year"),
                "analyst_id": analyst_id,
            },
            timeout=30,
        )
        body = resp.json()
        was_blocked = body.get("blocked", False)

        if was_blocked == item["expects_block"]:
            correct_block_decisions += 1
        else:
            print(f"[BLOCK MISMATCH] '{item['query']}' -> expected block={item['expects_block']}, got={was_blocked}")

        if item["expects_citation"] and not was_blocked:
            citation_eligible += 1
            if body.get("citations"):
                citation_hits += 1

    n = len(golden)
    print(f"\nBlock-decision accuracy: {correct_block_decisions}/{n} ({100*correct_block_decisions/n:.1f}%)")
    if citation_eligible:
        print(f"Citation rate on citable queries: {citation_hits}/{citation_eligible} "
              f"({100*citation_hits/citation_eligible:.1f}%)")
    else:
        print("No citable queries were eligible to score (index may be empty).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--analyst-id", type=int, required=True)
    parser.add_argument("--golden-path", default=str(Path(__file__).parent / "golden_set.json"))
    args = parser.parse_args()
    run(args.base_url, args.analyst_id, args.golden_path)
