import os
import uuid
import asyncio
import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from utils.config import Settings
from utils.logger import logger
from scrapers.playwright_scraper import PlaywrightScraper
from scrapers.bs4_scraper import BS4Scraper
from parsers import get_parser
from excel.generator import generate_excel_bytes

app = FastAPI(title="AI Universal Web Scraping Dashboard")

# Allow frontend to call the API from any origin during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = Settings()

class ExtractRequest(BaseModel):
    url: HttpUrl
    instruction: str

class ExtractResponse(BaseModel):
    filename: str
    download_url: str

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/extract")
async def extract(request: ExtractRequest, background_tasks: BackgroundTasks):
    logger.info(f"Received extraction request for {request.url}")
    scraper = PlaywrightScraper() if settings.use_playwright else BS4Scraper()
    try:
        html, final_url = await scraper.fetch(request.url)
    except Exception as e:
        logger.exception("Failed to fetch page")
        raise HTTPException(status_code=500, detail=f"Failed to fetch page: {str(e)}")

    parser = get_parser(final_url, request.instruction)
    if parser is None:
        raise HTTPException(status_code=400, detail="No parser available for this domain and AI fallback not configured.")

    records = await parser.parse(html, request.instruction)
    if not records:
        raise HTTPException(status_code=404, detail="No data extracted from the page.")

    # Remove duplicates based on all fields
    unique_records = [dict(t) for t in {tuple(sorted(d.items())) for d in records}]

    # Generate Excel bytes
    title = parser.get_page_title(html) or "scrape"
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = f"{title}_{timestamp}.xlsx"
    excel_bytes = generate_excel_bytes(unique_records, filename)

    # Stream response
    def iterfile():
        yield excel_bytes

    response = StreamingResponse(iterfile(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response

# Background task placeholder (e.g., cleanup old files) – not used now.
async def cleanup_task():
    pass
