import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import AuditLog, Base, log_event, verify_audit_chain


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_chain_is_intact_after_normal_writes(db_session):
    log_event(db_session, "search", {"query": "test"}, actor="analyst:1")
    log_event(db_session, "query", {"report_id": 1}, actor="analyst:1")
    log_event(db_session, "ingest", {"document_id": 1}, actor="system")
    assert verify_audit_chain(db_session) is True


def test_chain_breaks_if_a_row_is_tampered(db_session):
    log_event(db_session, "search", {"query": "test"}, actor="analyst:1")
    log_event(db_session, "query", {"report_id": 1}, actor="analyst:1")

    # Simulate someone editing a row directly in the DB, bypassing log_event.
    row = db_session.query(AuditLog).first()
    row.payload_json = '{"query": "tampered"}'
    db_session.commit()

    assert verify_audit_chain(db_session) is False


def test_chain_breaks_if_a_row_is_deleted(db_session):
    log_event(db_session, "search", {"query": "a"}, actor="analyst:1")
    log_event(db_session, "search", {"query": "b"}, actor="analyst:1")
    log_event(db_session, "search", {"query": "c"}, actor="analyst:1")

    middle = db_session.query(AuditLog).order_by(AuditLog.id.asc()).all()[1]
    db_session.delete(middle)
    db_session.commit()

    assert verify_audit_chain(db_session) is False
