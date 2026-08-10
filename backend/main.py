import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
import re
import json
import datetime
from io import BytesIO, StringIO
from typing import Optional
from urllib.parse import urlparse, urljoin

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl

from utils.config import Settings
from utils.logger import logger
from scrapers.playwright_scraper import PlaywrightScraper
from scrapers.bs4_scraper import BS4Scraper
from parsers import get_parser
from parsers.smart_filter import SmartFilter
from excel.generator import generate_excel_bytes

app = FastAPI(title="DataForge — Universal Web Scraping Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = Settings()

# ──────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────

class PreviewRequest(BaseModel):
    url: HttpUrl

class ExtractRequest(BaseModel):
    url: HttpUrl
    instruction: str
    format: str = "json"  # "json" | "excel" | "csv"

class ExtractResponse(BaseModel):
    records: list
    total: int
    keywords: list
    filename: str
    page_title: str

# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "ok", "app": "DataForge"}


@app.post("/proxy")
async def proxy_website(request: PreviewRequest):
    """Fetch a website and return its HTML so it can render in an iframe.
    Rewrites relative URLs to absolute so assets load correctly.
    """
    url_str = str(request.url)
    logger.info(f"Proxying website: {url_str}")

    scraper = PlaywrightScraper() if settings.use_playwright else BS4Scraper()
    try:
        html, final_url = await scraper.fetch(url_str)
    except Exception as e:
        logger.exception("Failed to proxy page")
        raise HTTPException(status_code=500, detail=f"Failed to load page: {str(e)}")

    # Parse the base URL for rewriting relative paths
    parsed = urlparse(final_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # Inject <base> tag so relative URLs resolve correctly
    base_tag = f'<base href="{base_url}/" target="_blank">'
    if "<head>" in html.lower():
        html = re.sub(
            r'(<head[^>]*>)',
            rf'\1{base_tag}',
            html,
            count=1,
            flags=re.IGNORECASE
        )
    else:
        html = base_tag + html

    # Remove X-Frame-Options and CSP headers that block iframe embedding
    # (handled by serving from our own origin)

    return Response(
        content=html,
        media_type="text/html",
        headers={
            "X-Frame-Options": "ALLOWALL",
            "Content-Security-Policy": "",
            "Access-Control-Allow-Origin": "*",
        }
    )


@app.post("/extract")
async def extract(request: ExtractRequest):
    """Extract structured data from any website.
    
    Supports 3 output formats:
    - json: Returns JSON with records + metadata (for preview table)
    - excel: Returns downloadable .xlsx file
    - csv: Returns downloadable .csv file
    """
    url_str = str(request.url)
    logger.info(f"Extraction request: {url_str} | format={request.format}")

    # 1. Fetch the page
    scraper = PlaywrightScraper() if settings.use_playwright else BS4Scraper()
    try:
        html, final_url = await scraper.fetch(url_str)
    except Exception as e:
        logger.exception("Failed to fetch page")
        raise HTTPException(status_code=500, detail=f"Failed to fetch page: {str(e)}")

    # 2. Parse the page
    parser = get_parser(final_url, request.instruction)
    records = await parser.parse(html, request.instruction)

    if not records:
        raise HTTPException(status_code=404, detail="No data could be extracted from this page.")

    # 3. Smart filter by instruction
    smart_filter = SmartFilter(request.instruction)
    filtered_records = smart_filter.filter(records)
    keywords = smart_filter.get_keywords()

    # 4. Remove duplicates
    unique_records = []
    seen = set()
    for r in filtered_records:
        key = tuple(sorted(r.items()))
        if key not in seen:
            seen.add(key)
            unique_records.append(r)

    # 5. Generate page title for filename
    page_title = parser.get_page_title(html) or "scraped_data"
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base_filename = f"{page_title}_{timestamp}"

    # 6. Return in requested format
    if request.format == "excel":
        excel_bytes = generate_excel_bytes(unique_records, f"{base_filename}.xlsx")
        return StreamingResponse(
            iter([excel_bytes]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={base_filename}.xlsx"}
        )

    elif request.format == "csv":
        import pandas as pd
        df = pd.DataFrame(unique_records)
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_bytes = csv_buffer.getvalue().encode("utf-8")
        return StreamingResponse(
            iter([csv_bytes]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={base_filename}.csv"}
        )

    else:  # json (default — for preview table)
        return JSONResponse({
            "records": unique_records,
            "total": len(unique_records),
            "keywords": keywords,
            "filename": base_filename,
            "page_title": page_title,
        })
