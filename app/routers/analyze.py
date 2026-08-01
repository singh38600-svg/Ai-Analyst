from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import ResearchAnalyst, ResearchReport, log_event
from app.schemas import AnalyzeRequest, AnalyzeResponse, ComplianceBlockedResponse
from app.services.compliance import classify_advice_seeking
from app.services.llm import synthesize_answer
from app.services.vector_store import vector_store

router = APIRouter(prefix="/analyze", tags=["analyze"])

_FIXED_DISCLAIMER = (
    "This system cannot provide investment recommendations, price targets, "
    "or buy/sell/hold calls. It can only retrieve and cite factual "
    "information from indexed filings. Please consult a SEBI-registered "
    "Research Analyst or Investment Adviser for personalized advice. "
    "(SEBI RA Regulations, 2014 — Recommendation Boundary)"
)


@router.post("", response_model=None)
def analyze(req: AnalyzeRequest, db: Session = Depends(get_db)):
    # 1. Compliance gate FIRST, before any retrieval/LLM cost is spent
    #    (PRD Section 4.3 item 3: intent classifier runs before the LLM).
    matched_pattern = classify_advice_seeking(req.query)
    if matched_pattern:
        log_event(
            db,
            event_type="compliance_block",
            payload={"query": req.query, "matched_pattern": matched_pattern, "analyst_id": req.analyst_id},
            actor=f"analyst:{req.analyst_id}",
        )
        return ComplianceBlockedResponse(
            disclaimer=_FIXED_DISCLAIMER,
            reason="advice_seeking_query_detected",
        )

    analyst = db.query(ResearchAnalyst).filter(ResearchAnalyst.id == req.analyst_id).first()
    if not analyst:
        raise HTTPException(status_code=404, detail="Unknown analyst_id. Register the analyst first via /compliance/analysts.")

    # 2. Hybrid retrieval with strict ticker/FY pre-filter + confidence gate
    results, low_confidence = vector_store.search(
        query=req.query,
        top_k=settings.RETRIEVAL_FINAL_TOP_K,
        ticker=req.ticker,
        fiscal_year=req.fiscal_year,
    )
    log_event(
        db,
        event_type="search",
        payload={"query": req.query, "ticker": req.ticker, "fiscal_year": req.fiscal_year,
                  "n_results": len(results), "low_confidence": low_confidence},
        actor=f"analyst:{req.analyst_id}",
    )

    if low_confidence or not results:
        disclosure = settings.AUTOMATED_DISCLOSURE_TEMPLATE.format(
            analyst_name=analyst.name,
            sebi_reg_no=analyst.sebi_reg_no,
            has_interest_disclosing_statement="may" if analyst.disclosed_holdings else "does not",
        )
        return AnalyzeResponse(
            answer="No sufficiently confident match was found in the indexed filings for this query. "
                   "Refusing to answer rather than risk an unsupported claim.",
            citations=[],
            numbers_verified=True,
            unverified_numbers=[],
            disclosure=disclosure,
            low_confidence=True,
        )

    context_chunks = [r[0] for r in results]

    # 3. Synthesis + numeric verification
    synth = synthesize_answer(req.query, context_chunks)

    disclosure = settings.AUTOMATED_DISCLOSURE_TEMPLATE.format(
        analyst_name=analyst.name,
        sebi_reg_no=analyst.sebi_reg_no,
        has_interest_disclosing_statement="may" if analyst.disclosed_holdings else "does not",
    )

    report = ResearchReport(
        analyst_id=analyst.id,
        query=req.query,
        answer=synth["answer"],
        citations_json=str(synth["citations"]),
        numbers_verified=synth["numbers_verified"],
        disclosure_text=disclosure,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    log_event(
        db,
        event_type="query",
        payload={"report_id": report.id, "numbers_verified": synth["numbers_verified"]},
        actor=f"analyst:{req.analyst_id}",
    )

    return AnalyzeResponse(
        answer=synth["answer"],
        citations=synth["citations"],
        numbers_verified=synth["numbers_verified"],
        unverified_numbers=synth["unverified_numbers"],
        disclosure=disclosure,
        low_confidence=False,
    )
