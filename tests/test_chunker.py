from app.services.chunker import chunk_with_metadata, extract_financial_tables, recursive_financial_splitter


def test_table_extracted_as_single_unit():
    text = (
        "Revenue grew this quarter.\n\n"
        "| Metric | FY23 | FY24 |\n"
        "|--------|------|------|\n"
        "| Revenue | 100 | 120 |\n"
        "| Profit | 20 | 25 |\n\n"
        "Profit margins improved as a result."
    )
    tables = extract_financial_tables(text)
    assert len(tables) == 1
    assert "Revenue" in tables[0]["content"]
    assert "Profit" in tables[0]["content"]


def test_table_not_split_across_chunks():
    text = (
        "| Metric | FY23 | FY24 |\n"
        "|--------|------|------|\n"
        "| Revenue | 100 | 120 |\n"
    )
    chunks = recursive_financial_splitter(text, chunk_size=2, chunk_overlap=0)
    # Even with a tiny chunk_size, the table must survive as one chunk.
    assert any("Revenue" in c and "120" in c for c in chunks)


def test_chunk_with_metadata_tags_table_type():
    text = (
        "Some narrative text before the table describing performance.\n\n"
        "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
        "Some narrative text after."
    )
    typed = chunk_with_metadata(text)
    types = {c["chunk_type"] for c in typed}
    assert "table" in types
    assert "text" in types


def test_long_text_splits_with_overlap():
    text = "word " * 2000
    chunks = recursive_financial_splitter(text, chunk_size=800, chunk_overlap=100)
    assert len(chunks) > 1
