from fastapi import FastAPI

from app.config import settings
from app.database import init_db
from app.routers import analyze, compliance, feedback, ingest, market_data

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Compliance-first RAG platform for SEBI-registered equity research analysts. "
        "Retrieves and cites facts from indexed filings; never issues investment advice."
    ),
    version="0.2.0",
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}


app.include_router(compliance.router)
app.include_router(ingest.router)
app.include_router(analyze.router)
app.include_router(feedback.router)
app.include_router(market_data.router)
