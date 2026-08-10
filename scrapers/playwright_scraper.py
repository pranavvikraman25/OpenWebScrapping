import asyncio
from playwright.async_api import async_playwright
import logging


class PlaywrightScraper:
    """Scrape a page using Playwright for dynamic content."""

    async def fetch(self, url: str, timeout: int = 30) -> tuple[str, str]:
        """Return the page HTML and the final URL after redirects.

        Automatically handles:
        - Dynamic JS-rendered content (waits for networkidle)
        - Infinite scroll pages (scrolls down to trigger lazy loading)
        - Site-specific wait selectors
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            await page.goto(url, timeout=timeout * 1000)

            # Wait for page to settle
            await page.wait_for_load_state("domcontentloaded")
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass

            # Auto-scroll for infinite scroll / lazy-loaded pages
            # Scroll down 3 times to trigger content loading
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                try:
                    await asyncio.sleep(1)
                except Exception:
                    pass

            # Scroll back to top
            await page.evaluate("window.scrollTo(0, 0)")
            
            # Brief wait for any final renders
            try:
                await page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass

            # Site-specific waits
            if "available-inventions.umich.edu" in url:
                try:
                    await page.wait_for_selector(".card-product, a[href*='/product/']", timeout=10000)
                except Exception:
                    pass

            html = await page.content()
            final_url = page.url
            await browser.close()
        return html, final_url
