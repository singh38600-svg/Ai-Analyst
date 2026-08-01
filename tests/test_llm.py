from app.services.llm import verify_numbers, extract_numbers, _mock_synthesize


def test_extract_numbers_handles_currency_and_percent():
    nums = extract_numbers("Revenue was ₹1,200 crore, up 15%.")
    assert "1200" in nums
    assert "15" in nums


def test_verify_numbers_passes_when_all_present_in_context():
    answer = "Revenue grew 15% to ₹1,200 crore."
    context = ["Revenue grew 15% to ₹1,200 crore driven by cloud."]
    verified, unverified = verify_numbers(answer, context)
    assert verified is True
    assert unverified == []


def test_verify_numbers_flags_hallucinated_number():
    answer = "Revenue grew 42% this year."
    context = ["Revenue grew 15% year over year."]
    verified, unverified = verify_numbers(answer, context)
    assert verified is False
    assert "42" in unverified


def test_mock_synthesize_never_invents_content_with_no_context():
    result = _mock_synthesize("What was revenue?", [])
    assert "No relevant information" in result


def test_mock_synthesize_includes_citations():
    chunks = [{"chunk_id": 1, "ticker": "TCS", "fiscal_year": "2024", "page_number": 12, "text": "Revenue grew 15%."}]
    result = _mock_synthesize("What was revenue growth?", chunks)
    assert "TCS" in result
    assert "p.12" in result
