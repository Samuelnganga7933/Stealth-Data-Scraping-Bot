"""
scrapers/google.py — Google search scraper
Scrapes search results for any keyword
Returns titles, URLs, descriptions, dates
"""

import asyncio
import random
from urllib.parse import quote_plus, urljoin
from typing import Optional
from bs4 import BeautifulSoup
from loguru import logger

from core.fetcher import Fetcher
from core.browser import StealthBrowser
from core.extractor import ExtractedData


class GoogleScraper:
    """
    Scrapes Google search results.
    Uses httpx first (fast), falls back to Playwright if blocked.
    """

    BASE_URL = "https://www.google.com/search"

    def __init__(self, fetcher: Fetcher, browser: Optional[StealthBrowser] = None):
        self.fetcher = fetcher
        self.browser = browser

    async def search(
        self,
        query: str,
        pages: int = 3,
        site: Optional[str] = None,
    ) -> list[dict]:
        """
        Search Google for a query.
        Returns list of {title, url, description, date} dicts.
        """
        results = []
        full_query = f"site:{site} {query}" if site else query

        for page in range(pages):
            start = page * 10
            url   = f"{self.BASE_URL}?q={quote_plus(full_query)}&start={start}&hl=en&num=10"
            logger.info(f"Google search page {page+1}: {full_query}")

            soup = await self.fetcher.get_soup(url)
            if not soup:
                logger.warning("Google blocked httpx, trying Playwright...")
                soup = await self._playwright_search(url)

            if not soup:
                break

            page_results = self._parse_results(soup)
            if not page_results:
                break

            results.extend(page_results)
            await asyncio.sleep(random.uniform(2, 5))

        logger.success(f"Google: found {len(results)} results for '{query}'")
        return results

    async def search_news(self, query: str, pages: int = 2) -> list[dict]:
        """Search Google News tab."""
        results = []
        for page in range(pages):
            start = page * 10
            url   = f"{self.BASE_URL}?q={quote_plus(query)}&tbm=nws&start={start}&hl=en"
            soup  = await self.fetcher.get_soup(url)
            if soup:
                results.extend(self._parse_news(soup))
            await asyncio.sleep(random.uniform(2, 4))
        return results

    async def search_jobs(self, query: str, location: str = "") -> list[dict]:
        """Search Google Jobs."""
        job_query = f"{query} jobs {location}".strip()
        return await self.search(job_query, pages=2)

    def _parse_results(self, soup: BeautifulSoup) -> list[dict]:
        results = []
        for g in soup.select("div.g, div[data-sokoban-container]"):
            try:
                a    = g.find("a", href=True)
                h3   = g.find("h3")
                desc = g.find("div", {"data-sncf": True}) or g.find("span", class_="aCOpRe")

                if not a or not h3:
                    continue

                href = a["href"]
                if not href.startswith("http"):
                    continue

                results.append({
                    "title":       h3.get_text(strip=True),
                    "url":         href,
                    "description": desc.get_text(strip=True) if desc else "",
                    "source":      "google",
                })
            except Exception:
                continue
        return results

    def _parse_news(self, soup: BeautifulSoup) -> list[dict]:
        results = []
        for item in soup.select("div.SoaBEf, div.WlydOe"):
            try:
                a     = item.find("a", href=True)
                title = item.find("div", class_="mCBkyc") or item.find("h3")
                date  = item.find("span", class_="OSrXXb")
                src   = item.find("div", class_="CEMjEf")

                if not a or not title:
                    continue

                results.append({
                    "title":  title.get_text(strip=True),
                    "url":    a["href"],
                    "date":   date.get_text(strip=True) if date else "",
                    "outlet": src.get_text(strip=True) if src else "",
                    "source": "google_news",
                })
            except Exception:
                continue
        return results

    async def _playwright_search(self, url: str) -> Optional[BeautifulSoup]:
        if not self.browser:
            return None
        try:
            page = await self.browser.new_page()
            await self.browser.goto(page, url)
            await self.browser.random_scroll_read(page)
            content = await page.content()
            await page.close()
            return BeautifulSoup(content, "html.parser")
        except Exception as e:
            logger.error(f"Playwright Google fallback failed: {e}")
            return None
