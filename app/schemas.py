from typing import List, Optional

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=1)
    ticker: Optional[str] = None
    fiscal_year: Optional[str] = None
    analyst_id: int


class CitationOut(BaseModel):
    chunk_id: int
    ticker: Optional[str]
    fiscal_year: Optional[str]
    page_number: Optional[int]


class AnalyzeResponse(BaseModel):
    answer: str
    citations: List[CitationOut]
    numbers_verified: bool
    unverified_numbers: List[str]
    disclosure: str
    low_confidence: bool = False


class ComplianceBlockedResponse(BaseModel):
    blocked: bool = True
    disclaimer: str
    reason: str


class IngestResponse(BaseModel):
    document_id: int
    ticker: str
    fiscal_year: str
    chunks_indexed: int
    pages_processed: int
    skipped_pages_no_text_layer: List[int] = []


class FeedbackRequest(BaseModel):
    report_id: int
    flagged_by: str
    reason: str


class AnalystCreate(BaseModel):
    name: str
    sebi_reg_no: str
    disclosed_holdings: Optional[str] = ""
