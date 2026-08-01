from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog, ResearchAnalyst, verify_audit_chain
from app.schemas import AnalystCreate

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.post("/analysts")
def register_analyst(payload: AnalystCreate, db: Session = Depends(get_db)):
    existing = db.query(ResearchAnalyst).filter(
        ResearchAnalyst.sebi_reg_no == payload.sebi_reg_no
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="An analyst with this SEBI registration number already exists.")

    analyst = ResearchAnalyst(
        name=payload.name,
        sebi_reg_no=payload.sebi_reg_no,
        disclosed_holdings=payload.disclosed_holdings or "",
    )
    db.add(analyst)
    db.commit()
    db.refresh(analyst)
    return {"id": analyst.id, "name": analyst.name, "sebi_reg_no": analyst.sebi_reg_no}


@router.get("/audit-log/verify")
def verify_audit_log(db: Session = Depends(get_db)):
    """
    Confirms the hash chain is unbroken (PRD Section 4.3 item 2:
    tamper-proof audit log). Returns False if any row was edited or
    deleted outside of models.log_event().
    """
    intact = verify_audit_chain(db)
    count = db.query(AuditLog).count()
    return {"chain_intact": intact, "total_events": count}
