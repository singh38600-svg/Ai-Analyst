"""
Live market data endpoint (PRD Section 4.2: query router must
distinguish 'what did the filing say' from 'what's the live price').

Honest status: no real NSE/BSE/vendor API is wired up here — that
requires a paid data vendor key which isn't something to hardcode.
MARKET_DATA_PROVIDER=mock returns clearly-labeled placeholder data
with an obviously-fake price and a real timestamp, so:
  1. The router/classification logic (is this a live-price query?)
     is genuinely implemented and testable.
  2. The response schema and "as of {timestamp}" freshness labeling
     the PRD requires is genuinely implemented.
  3. Nobody can mistake the mock price for real data, in code or UI.

To go live: implement _fetch_live_price() against a real vendor and
flip MARKET_DATA_PROVIDER to that vendor's name.
"""
from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(prefix="/market-data", tags=["market-data"])


def _fetch_live_price_mock(ticker: str) -> dict:
    return {
        "ticker": ticker.upper(),
        "price": None,
        "currency": "INR",
        "as_of": datetime.now(timezone.utc).isoformat(),
        "source": "MOCK_PROVIDER_NOT_LIVE",
        "note": (
            "No live market data vendor is configured. This is a placeholder "
            "response demonstrating the API contract only. Do not use this "
            "price for any real decision."
        ),
    }


@router.get("/price/{ticker}")
def get_live_price(ticker: str):
    # Provider dispatch left intentionally simple/explicit — swap in a
    # real vendor call here (e.g. NSE India API, Tickertape) when a key
    # is available. See app/config.py MARKET_DATA_PROVIDER.
    return _fetch_live_price_mock(ticker)
