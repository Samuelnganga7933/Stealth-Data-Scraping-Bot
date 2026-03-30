"""
scrapers/generic.py — Universal website scraper
Handles any URL — auto-detects static vs dynamic
Extracts all useful data automatically
"""

import asyncio
from typing import Optional
from bs4 import BeautifulSoup
from loguru import logger

from core.browser import StealthBrowser
from core.fetcher import Fetcher
from core.extractor import Extractor, ExtractedData

# Sites that REQUIRE Playwright (JS-rendered)
JS_REQUIRED_DOMAINS = {
    "twitter.com", "x.com", "instagram.com", "facebook.com",
    "tiktok.com", "linkedin.com", "youtube.com", "airbnb.com",
    "zillow.com", "glassdoor.com", "indeed.com",
}


class GenericScraper:
    """
    Scrapes any URL.
    Auto-picks httpx (fast) or Playwright (JS-heavy).
    """

    def __init__(self, fetcher: Fetcher, browser: Optional[StealthBrowser] = None):
        self.fetcher   = fetcher
        self.browser   = browser
        self.extractor = Extractor()

    def _needs_js(self, url: str) -> bool:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.replace("www.", "")
        return any(d in domain for d in JS_REQUIRED_DOMAINS)

    async def scrape(self, url: str, keywords: list[str] = None, deep: bool = False) -> ExtractedData:
        """
        Scrape a URL and extract all data.
        deep=True follows internal links one level deeper.
        """
        if self._needs_js(url) and self.browser:
            data = await self._playwright_scrape(url, keywords)
        else:
            data = await self._fetch_scrape(url, keywords)

        if deep and data and data.links:
            # Scrape first 5 internal links
            from urllib.parse import urlparse
            base   = urlparse(url).netloc
            internal = [
                l for l in data.links
                if urlparse(l).netloc == base
            ][:5]

            for link in internal:
                logger.info(f"Deep scraping: {link}")
                sub = await self.scrape(link, keywords)
                if sub:
                    data.emails.extend(sub.emails)
                    data.phones.extend(sub.phones)
                    data.links.extend(sub.links)
                await asyncio.sleep(1.5)

            # Deduplicate
            data.emails = list(set(data.emails))
            data.phones = list(set(data.phones))
            data.links  = list(set(data.links))

        return data

    async def scrape_many(self, urls: list[str], keywords: list[str] = None) -> list[ExtractedData]:
        """Scrape multiple URLs."""
        results = []
        for url in urls:
            logger.info(f"Scraping: {url}")
            data = await self.scrape(url, keywords)
            if data:
                results.append(data)
            await asyncio.sleep(1.5)
        return results

    async def _fetch_scrape(self, url: str, keywords: list[str] = None) -> Optional[ExtractedData]:
        """Fast static scrape via httpx + BeautifulSoup."""
        soup = await self.fetcher.get_soup(url)
        if not soup:
            return None
        return self.extractor.extract_from_soup(soup, url=url, keywords=keywords)

    async def _playwright_scrape(self, url: str, keywords: list[str] = None) -> Optional[ExtractedData]:
        """Full browser scrape via Playwright."""
        if not self.browser:
            return await self._fetch_scrape(url, keywords)
        try:
            page = await self.browser.new_page()
            await self.browser.goto(page, url)
            await self.browser.random_scroll_read(page)
            content = await page.content()
            await page.close()
            return self.extractor.extract_from_html(content, url=url, keywords=keywords)
        except Exception as e:
            logger.error(f"Playwright scrape error on {url}: {e}")
            return None
