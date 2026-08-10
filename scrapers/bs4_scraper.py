# BS4 Scraper
import httpx
from bs4 import BeautifulSoup
import logging

class BS4Scraper:
    """Static HTML scraper using httpx and BeautifulSoup."""

    async def fetch(self, url: str, timeout: int = 30) -> tuple[str, str]:
        """Return raw HTML and final URL after redirects.

        Args:
            url: Target page URL.
            timeout: Seconds before giving up.
        """
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
            final_url = str(response.url)
        return html, final_url
