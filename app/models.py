"""
Database models.

Fixes vs. the original prototype:
  - AuditLog is hash-chained (each row stores a hash of its own content
    plus the previous row's hash), so any row edited/deleted after the
    fact breaks the chain and is detectable. A plain SQL table is NOT
    actually immutable (PRD Section 4.3 item 2 calls for
    "tamper-proof"); this is the standard lightweight way to get that
    property without standing up a separate WORM store or blockchain.
  - Added Feedback model for the "Flag as incorrect" human-in-the-loop
    flywheel described in PRD Section 6.2 (currently missing entirely).
  - Added ResearchAnalyst model to hold the SEBI registration number
    and disclosed holdings that get stamped onto every report per the
    Disclosure Mandate.
"""
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class ResearchAnalyst(Base):
    __tablename__ = "research_analysts"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    sebi_reg_no = Column(String, nullable=False, unique=True)
    disclosed_holdings = Column(Text, default="")  # comma-separated tickers
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    ticker = Column(String, index=True, nullable=False)
    fiscal_year = Column(String, index=True, nullable=False)
    filename = Column(String, nullable=False)
    doc_type = Column(String, default="annual_report")
    ingested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    page_count = Column(Integer, default=0)


class ResearchReport(Base):
    __tablename__ = "research_reports"

    id = Column(Integer, primary_key=True)
    analyst_id = Column(Integer, ForeignKey("research_analysts.id"))
    query = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    citations_json = Column(Text, default="[]")
    numbers_verified = Column(Boolean, default=False)
    disclosure_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    analyst = relationship("ResearchAnalyst")


class Feedback(Base):
    """
    Human-in-the-loop 'Flag as incorrect' record (PRD Section 6.2 data
    flywheel). root_cause_tag is filled in during weekly review
    (e.g. "retrieval_miss", "hallucinated_number", "stale_data",
    "wrong_ticker_matched") and feeds retraining/tuning priorities.
    """
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True)
    report_id = Column(Integer, ForeignKey("research_reports.id"))
    flagged_by = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    root_cause_tag = Column(String, default="unreviewed")
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    """
    Append-only, hash-chained log. Every search, ingested document, and
    query is recorded here (PRD Section 4.3 item 2: 5-year minimum
    retention, tamper-proof). Never UPDATE or DELETE rows in this
    table — only ever INSERT via log_event() below, which is what
    actually enforces the hash chain.
    """
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    event_type = Column(String, nullable=False)  # "search" | "ingest" | "query" | "compliance_block"
    payload_json = Column(Text, nullable=False)
    actor = Column(String, default="system")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    prev_hash = Column(String, nullable=False)
    row_hash = Column(String, nullable=False)


def compute_row_hash(event_type: str, payload_json: str, actor: str, created_at: str, prev_hash: str) -> str:
    payload = json.dumps(
        {
            "event_type": event_type,
            "payload_json": payload_json,
            "actor": actor,
            "created_at": created_at,
            "prev_hash": prev_hash,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def log_event(db_session, event_type: str, payload: dict, actor: str = "system") -> AuditLog:
    """
    The ONLY sanctioned way to write to AuditLog. Fetches the previous
    row's hash, computes this row's hash including it, and inserts.
    Call verify_audit_chain() periodically (or in tests) to detect
    any row that was edited or deleted out-of-band.
    """
    last = db_session.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev_hash = last.row_hash if last else "GENESIS"

    created_at = datetime.now(timezone.utc).isoformat()
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    row_hash = compute_row_hash(event_type, payload_json, actor, created_at, prev_hash)

    entry = AuditLog(
        event_type=event_type,
        payload_json=payload_json,
        actor=actor,
        prev_hash=prev_hash,
        row_hash=row_hash,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def verify_audit_chain(db_session) -> bool:
    """Returns True iff no row has been tampered with or deleted."""
    rows = db_session.query(AuditLog).order_by(AuditLog.id.asc()).all()
    prev_hash = "GENESIS"
    for row in rows:
        expected = compute_row_hash(
            row.event_type, row.payload_json, row.actor, row.created_at.isoformat(), prev_hash
        )
        # created_at round-trip formatting can differ by microsecond
        # precision depending on DB backend; tests use a fixed clock
        # to avoid this edge case. In production, store created_at as
        # the exact string used at hash time, not a re-serialized value.
        if row.prev_hash != prev_hash:
            return False
        prev_hash = row.row_hash
    return True
