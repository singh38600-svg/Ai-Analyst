import shutil
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, log_event
from app.schemas import IngestResponse
from app.services.pdf_loader import ingest_pdf
from app.services.vector_store import vector_store

router = APIRouter(prefix="/ingest", tags=["ingest"])

_next_chunk_id = [1]  # simple in-process counter; fine at this project's scale


@router.post("", response_model=IngestResponse)
async def ingest_document(
    ticker: str,
    fiscal_year: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF filings are supported in V1.")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    chunks = ingest_pdf(tmp_path, ticker=ticker, fiscal_year=fiscal_year)
    skipped_pages = []
    indexed = 0
    pages_seen = set()

    doc = Document(ticker=ticker.upper(), fiscal_year=str(fiscal_year), filename=file.filename)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    for chunk in chunks:
        if "_ingest_warnings" in chunk:
            skipped_pages = chunk["_ingest_warnings"].get("skipped_pages_no_text_layer", [])
        if not chunk["text"].strip():
            continue
        chunk_id = _next_chunk_id[0]
        _next_chunk_id[0] += 1
        vector_store.add_chunk(
            chunk_id=chunk_id,
            text=chunk["text"],
            doc_id=doc.id,
            ticker=chunk["ticker"],
            fiscal_year=chunk["fiscal_year"],
            page_number=chunk["page_number"],
            chunk_type=chunk["chunk_type"],
        )
        indexed += 1
        if chunk["page_number"]:
            pages_seen.add(chunk["page_number"])

    doc.page_count = len(pages_seen) + len(skipped_pages)
    db.commit()

    log_event(
        db,
        event_type="ingest",
        payload={"document_id": doc.id, "ticker": ticker, "fiscal_year": fiscal_year,
                  "chunks_indexed": indexed, "skipped_pages": skipped_pages},
        actor="system",
    )

    return IngestResponse(
        document_id=doc.id,
        ticker=ticker.upper(),
        fiscal_year=str(fiscal_year),
        chunks_indexed=indexed,
        pages_processed=len(pages_seen),
        skipped_pages_no_text_layer=skipped_pages,
    )
