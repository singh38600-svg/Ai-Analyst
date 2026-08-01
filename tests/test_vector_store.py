import os

import pytest

from app.services.vector_store import VectorStoreEmulator


@pytest.fixture
def store(tmp_path):
    path = str(tmp_path / "test_index.json")
    vs = VectorStoreEmulator(persist_path=path)
    vs.add_chunk(1, "Revenue grew 15% year over year driven by cloud segment.", doc_id=1, ticker="TCS", fiscal_year="2024")
    vs.add_chunk(2, "Net profit margin contracted due to rising input costs.", doc_id=1, ticker="TCS", fiscal_year="2024")
    vs.add_chunk(3, "Revenue grew 8% year over year in the retail division.", doc_id=2, ticker="INFY", fiscal_year="2024")
    vs.add_chunk(4, "Revenue grew 15% year over year driven by cloud segment.", doc_id=3, ticker="TCS", fiscal_year="2023")
    yield vs
    if os.path.exists(path):
        os.remove(path)


def test_ticker_prefilter_excludes_other_companies(store):
    results, low_conf = store.search("revenue growth", ticker="TCS", fiscal_year="2024", confidence_threshold=0.0)
    tickers = {r[0]["ticker"] for r in results}
    assert tickers == {"TCS"}
    assert all(r[0]["fiscal_year"] == "2024" for r in results)


def test_no_cross_year_contamination(store):
    results, low_conf = store.search("cloud segment revenue", ticker="TCS", fiscal_year="2024", confidence_threshold=0.0)
    assert all(r[0]["chunk_id"] != 4 for r in results)  # chunk 4 is FY2023


def test_confidence_threshold_triggers_refusal(store):
    # An absurdly high threshold should force a low_confidence refusal
    # even though relevant text exists.
    results, low_conf = store.search("revenue growth", ticker="TCS", fiscal_year="2024", confidence_threshold=0.999)
    assert low_conf is True
    assert results == []


def test_no_matching_ticker_returns_low_confidence(store):
    results, low_conf = store.search("revenue growth", ticker="WIPRO", fiscal_year="2024")
    assert low_conf is True
    assert results == []


def test_relevant_query_ranks_above_irrelevant(store):
    results, low_conf = store.search("net profit margin", ticker="TCS", fiscal_year="2024", confidence_threshold=0.0)
    assert results[0][0]["chunk_id"] == 2
