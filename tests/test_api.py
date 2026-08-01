"""
End-to-end API test: register analyst -> index a chunk directly (bypassing
PDF ingestion for test speed) -> query /analyze -> assert compliance block,
citations, and disclosure all work together.

NOTE: requires fastapi/httpx/sqlalchemy installed (see requirements.txt).
This sandbox could not install them (no network egress), so this test is
written correctly but has not been executed here — run `pytest` after
`pip install -r requirements.txt` locally / in CI before trusting it.
"""
import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_eiap.db"

from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.vector_store import vector_store  # noqa: E402


@pytest.fixture(autouse=True)
def setup_and_teardown():
    init_db()
    vector_store.clear()
    yield
    if os.path.exists("./test_eiap.db"):
        os.remove("./test_eiap.db")
    vector_store.clear()


client = TestClient(app)


def _register_analyst():
    resp = client.post("/compliance/analysts", json={
        "name": "Priya Sharma",
        "sebi_reg_no": "INH000012345",
        "disclosed_holdings": "",
    })
    assert resp.status_code == 200
    return resp.json()["id"]


def test_advice_seeking_query_is_blocked_not_500d():
    analyst_id = _register_analyst()
    resp = client.post("/analyze", json={
        "query": "Should I buy TCS right now?",
        "analyst_id": analyst_id,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["blocked"] is True
    assert "disclaimer" in body


def test_factual_query_returns_cited_answer():
    analyst_id = _register_analyst()
    vector_store.add_chunk(
        chunk_id=1,
        text="Revenue grew 15% year over year to ₹1,200 crore, driven by the cloud segment.",
        doc_id=1,
        ticker="TCS",
        fiscal_year="2024",
        page_number=42,
        chunk_type="text",
    )
    resp = client.post("/analyze", json={
        "query": "What was TCS revenue growth?",
        "ticker": "TCS",
        "fiscal_year": "2024",
        "analyst_id": analyst_id,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["low_confidence"] is False
    assert len(body["citations"]) > 0
    assert body["citations"][0]["page_number"] == 42
    assert "SEBI" in body["disclosure"]


def test_no_match_returns_low_confidence_not_hallucination():
    analyst_id = _register_analyst()
    resp = client.post("/analyze", json={
        "query": "What was the dividend yield?",
        "ticker": "NONEXISTENT",
        "fiscal_year": "2024",
        "analyst_id": analyst_id,
    })
    assert resp.status_code == 200
    assert resp.json()["low_confidence"] is True


def test_audit_chain_stays_intact_through_normal_use():
    analyst_id = _register_analyst()
    client.post("/analyze", json={"query": "Should I sell?", "analyst_id": analyst_id})
    resp = client.get("/compliance/audit-log/verify")
    assert resp.json()["chain_intact"] is True
    assert resp.json()["total_events"] >= 1
