from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Feedback, ResearchReport
from app.schemas import FeedbackRequest

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("")
def flag_report(payload: FeedbackRequest, db: Session = Depends(get_db)):
    """
    'Flag as incorrect' — PRD Section 6.2 data flywheel entry point.
    Root-cause tagging happens in weekly review (not automated here by
    design; forcing a human to categorize the failure is the point of
    a flywheel, not something to auto-guess).
    """
    report = db.query(ResearchReport).filter(ResearchReport.id == payload.report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    fb = Feedback(
        report_id=payload.report_id,
        flagged_by=payload.flagged_by,
        reason=payload.reason,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return {"id": fb.id, "status": "queued_for_review"}


@router.get("/queue")
def review_queue(db: Session = Depends(get_db)):
    """Unresolved flags, oldest first — the weekly review queue."""
    items = (
        db.query(Feedback)
        .filter(Feedback.resolved == False)  # noqa: E712
        .order_by(Feedback.created_at.asc())
        .all()
    )
    return [
        {"id": i.id, "report_id": i.report_id, "reason": i.reason, "flagged_by": i.flagged_by,
          "root_cause_tag": i.root_cause_tag, "created_at": i.created_at.isoformat()}
        for i in items
    ]
