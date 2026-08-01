from app.services.compliance import classify_advice_seeking


def test_blocks_direct_advice_request():
    assert classify_advice_seeking("Should I buy Reliance now?") is not None


def test_blocks_rephrased_bypass_attempt():
    # The old keyword-only version was bypassable by avoiding "buy"/"sell"
    # verbatim; this must still catch common rephrasings.
    assert classify_advice_seeking("Is it a good time to add to my position in TCS?") is not None
    assert classify_advice_seeking("What should I do with my Infosys shares?") is not None


def test_does_not_block_legitimate_factual_query_with_trading_vocabulary():
    # This must NOT be blocked — false positives break the tool's core use case.
    assert classify_advice_seeking("What is SEBI's minimum holding period disclosure requirement?") is None
    assert classify_advice_seeking("What was the company's revenue in FY24?") is None
    assert classify_advice_seeking("Summarize the risk factors section of the annual report.") is None


def test_blocks_recommendation_rating_phrasing():
    assert classify_advice_seeking("Give me a buy call on HDFC Bank") is not None
    assert classify_advice_seeking("What's your buy rating on this stock?") is not None
